#!/usr/bin/env python3
"""
混合情感分析引擎：BERT细分类 + 规则词典修正 + LLM困难样本兜底

用法:
    from sentiment_analyzer import HybridSentimentAnalyzer
    
    analyzer = HybridSentimentAnalyzer(use_llm=True, llm_max_calls=50)
    score, label, method = analyzer.analyze("女皇大人太美了！！")
    # score: 0.85, label: "正面", method: "BERT+dict+intensity"
"""

# ========== 环境变量加载 ==========
import os
# 在项目根目录加载 .env（sentiment_analyzer.py 在 src/ 下，.env 在 bilibili_sentiment_project/ 下）
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_dotenv_path = os.path.join(_project_root, '.env')
try:
    from dotenv import load_dotenv
    load_dotenv(_dotenv_path)
except ImportError:
    with open(_dotenv_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('\'"'))

import re
import json
import requests
from typing import Tuple, Optional, Dict, List

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

try:
    from dictionary import (
        clean_noise, has_meaningful_content, detect_irony,
        calc_game_term_ratio, apply_intensity_modifiers,
        score_to_label, GAME_SENTIMENT_DICT, JIEBA_CUSTOM_WORDS,
    )
except ImportError:
    clean_noise = lambda text: text
    has_meaningful_content = lambda text: bool(text and text.strip())
    detect_irony = lambda text: (False, 'neutral', 0.0)
    calc_game_term_ratio = lambda text: 0.0
    apply_intensity_modifiers = lambda text, score: score
    score_to_label = lambda score: '中性' if abs(score - 0.5) < 0.05 else ('正面' if score > 0.5 else '负面')
    GAME_SENTIMENT_DICT = set()
    JIEBA_CUSTOM_WORDS = []


class HybridSentimentAnalyzer:
    """
    混合情感分析器
    
    分析流程:
        1. 规则过滤: 清洗噪声前缀、反讽检测
        2. BERT预测: Erlangshen-RoBERTa-110M-Sentiment 输出0-1概率
        3. 词典修正: 游戏领域专有名词 → 拉回中性；强度修饰符 → 增强极性
        4. LLM兜底: 对BERT低置信度/含梗样本调用大模型
    """

    # 支持的LLM配置
    LLM_CONFIGS = [
        {
            'name': 'qwen-flash',
            'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            'api_key': os.environ.get('DASHSCOPE_API_KEY', ''),
            'model_id': 'qwen-flash',
        },
        {
            'name': 'minimax-m2.7-free',
            'base_url': 'https://www.dogapi.cc/v1',
            'api_key': os.environ.get('MINIMAX_API_KEY', ''),
            'model_id': 'minimax-m2.7-free',
        },
    ]

    # LLM系统提示词
    SYSTEM_PROMPT = (
        "你是一个专精于B站弹幕/评论的中文网络文本情感分析专家。"
        "请分析用户提供的文本的情感倾向，只输出0-1之间的一个数字（保留3位小数），"
        "0表示极度负面，1表示极度正面，0.5表示中性。"
        "注意以下特殊情况：\n"
        "1. 'doge'、[doge]等表情包文字通常表示调侃或中性态度，不要误判为负面\n"
        "2. '刀了'、'太刀了'在游戏/动画语境中表示情感冲击（感动/悲伤），不一定是负面\n"
        "3. '蚌埠住了'、'绷不住'表示忍耐不住（笑或哭），视上下文判断\n"
        "4. 'xswl'表示笑死，通常是正面\n"
        "5. 纯角色名（如'钟离'、'女皇'）或地名（如'至冬'）视为中性\n"
        "6. 注意识别反讽和阴阳怪气语气\n"
        "7. 啊啊啊、！！！等强烈表达应提高情感强度\n"
        "不要输出任何解释，只输出数字。"
    )

    def __init__(
        self,
        model_name: str = "IDEA-CCNL/Erlangshen-RoBERTa-110M-Sentiment",
        use_llm: bool = True,
        llm_max_calls: int = 50,
        device: Optional[str] = None,
    ):
        """
        初始化混合情感分析器
        
        Args:
            model_name: HuggingFace模型名
            use_llm: 是否启用LLM兜底
            llm_max_calls: LLM最大调用次数（防止费用过高）
            device: 计算设备 ('cuda' / 'cpu' / None自动)
        """
        self.use_llm = use_llm
        self.llm_max_calls = llm_max_calls
        self.llm_call_count = 0
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')

        # 加载BERT模型
        print(f"[Analyzer] 加载BERT模型: {model_name}")
        print(f"[Analyzer] 使用设备: {self.device}")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name, trust_remote_code=True, local_files_only=True
            )
            self.model = AutoModelForSequenceClassification.from_pretrained(
                model_name, trust_remote_code=True, local_files_only=True
            ).to(self.device)
            print("[Analyzer] 模型已从本地缓存加载，未发起网络请求")
        except (OSError,):
            print("[Analyzer] 本地未找到完整缓存，尝试联网下载模型...")
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                model_name, trust_remote_code=True
            ).to(self.device)
        self.model.eval()
        print(f"[Analyzer] 模型就绪: {self.model.config.id2label}")

        # jieba自定义词
        if JIEBA_AVAILABLE:
            for word in JIEBA_CUSTOM_WORDS:
                jieba.add_word(word, freq=1000)

    # ==================== BERT推理 ====================

    def bert_predict(self, text: str) -> float:
        """BERT单条推理，返回正面概率0-1"""
        if not text or len(text.strip()) < 2:
            return 0.5

        inputs = self.tokenizer(
            text, return_tensors="pt", truncation=True, max_length=512
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.softmax(outputs.logits, dim=1)
            pos_prob = probs[0][1].item()

        return pos_prob

    def bert_predict_batch(self, texts: List[str], batch_size: int = 16) -> List[float]:
        """BERT批量推理，加速处理"""
        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            # 过滤空文本
            valid_indices = []
            valid_texts = []
            for j, t in enumerate(batch):
                if t and len(t.strip()) >= 2:
                    valid_indices.append(j)
                    valid_texts.append(t.strip())

            if not valid_texts:
                results.extend([0.5] * len(batch))
                continue

            inputs = self.tokenizer(
                valid_texts, return_tensors="pt", truncation=True,
                max_length=256, padding=True,
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.softmax(outputs.logits, dim=1)[:, 1].cpu().numpy()

            batch_scores = [0.5] * len(batch)
            for k, orig_idx in enumerate(valid_indices):
                batch_scores[orig_idx] = float(probs[k])

            results.extend(batch_scores)

        return results

    # ==================== 规则引擎 ====================

    def apply_game_dict_rules(self, text: str, bert_score: float) -> Tuple[float, str]:
        """
        游戏领域词典修正BERT结果
        返回: (修正后分数, 应用了哪些规则)
        """
        rules_applied = []
        score = bert_score

        # 1. 游戏术语高比例 → 拉回中性
        ratio = calc_game_term_ratio(text)
        if ratio > 0.4 and len(text) < 20:
            score = 0.4 + (score - 0.5) * 0.3
            rules_applied.append(f'game_term_ratio_{ratio:.2f}')

        # 2. 纯游戏术语+无情感词 → 中性化
        if JIEBA_AVAILABLE:
            words = list(jieba.cut(text))
            game_words = [w for w in words if w in GAME_SENTIMENT_DICT]
            non_game_meaningful = [
                w for w in words
                if len(w) > 1 and w not in GAME_SENTIMENT_DICT
                and not w.isspace()
            ]
            if game_words and len(non_game_meaningful) <= 2:
                score = 0.45 + (score - 0.5) * 0.4
                rules_applied.append('pure_game_terms')

        return score, '+'.join(rules_applied) if rules_applied else 'none'

    # ==================== LLM兜底 ====================

    def llm_predict(self, text: str) -> Optional[float]:
        """
        调用LLM API进行情感分析
        依次尝试配置的LLM，直到成功
        返回: 0-1情感分数，失败返回None
        """
        if not self.use_llm or self.llm_call_count >= self.llm_max_calls:
            return None

        for cfg in self.LLM_CONFIGS:
            try:
                payload = {
                    "model": cfg['model_id'],
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": f'文本:"{text[:150]}"\n情感分数:'}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 10,
                }

                resp = requests.post(
                    f"{cfg['base_url']}/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {cfg['api_key']}",
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                result = resp.json()
                content = result["choices"][0]["message"]["content"].strip()

                match = re.search(r'(0?\.\d{1,3})', content)
                if match:
                    score = float(match.group(1))
                    score = max(0.0, min(1.0, score))
                    self.llm_call_count += 1
                    print(f"    [LLM-{cfg['name']}] \"{text[:30]}...\" → {score:.3f}")
                    return score

            except Exception as e:
                print(f"    [LLM-{cfg['name']}] 失败: {str(e)[:80]}")
                continue

        return None

    # ==================== 困难样本检测 ====================

    def is_difficult_sample(self, text: str, bert_score: float) -> Tuple[bool, str]:
        """
        判断是否为BERT难以处理的样本
        返回: (是否困难, 原因)
        """
        text_lower = text.lower()

        # 1. BERT置信度极低
        if abs(bert_score - 0.5) < 0.1:
            return True, 'low_confidence'

        # 2. 含网络梗/表情包
        meme_keywords = ['doge', '蚌埠', '绷不住', 'xswl', 'yyds', 'awsl',
                         'hgr', 'nsdd', '破防', '离谱', '逆天']
        for kw in meme_keywords:
            if kw in text_lower:
                return True, f'meme_{kw}'

        # 3. 含游戏特殊情感词
        special_terms = ['刀了', '太刀', '意难平', '心梗', '高血压']
        for term in special_terms:
            if term in text:
                return True, f'special_term_{term}'

        # 4. 可能的反讽
        is_irony, _, conf = detect_irony(text)
        if is_irony and conf > 0.6:
            return True, 'irony_detected'

        # 5. 纯表情符号+少量文字
        emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF]')
        if emoji_pattern.search(text) and len(text) < 15:
            return True, 'emoji_short'

        # 6. 中英混合无明确主语
        if re.search(r'[a-zA-Z]+.*[\u4e00-\u9fff]+', text) and len(text) < 20:
            if abs(bert_score - 0.5) < 0.25:
                return True, 'mixed_lang_uncertain'

        return False, 'bert_ok'

    # ==================== 主分析函数 ====================

    def analyze(self, text: str) -> Tuple[float, str, str]:
        """
        单条文本情感分析主入口
        
        Returns:
            (sentiment_score, sentiment_label, method)
            - sentiment_score: 0-1 浮点数
            - sentiment_label: "正面" / "中性" / "负面"
            - method: 使用的分析方法描述
        """
        # Step 1: 清洗噪声
        cleaned = clean_noise(text)
        if not has_meaningful_content(cleaned):
            return 0.5, '中性', 'rule-noise-filtered'

        # Step 2: 反讽检测
        is_irony, irony_sentiment, irony_conf = detect_irony(cleaned)
        if is_irony and irony_conf > 0.8:
            score = 0.2 if irony_sentiment == 'negative' else 0.8
            return score, score_to_label(score), f'rule-irony({irony_conf:.1f})'

        # Step 3: BERT预测
        bert_score = self.bert_predict(cleaned)
        method = 'BERT'

        # Step 4: 游戏词典修正
        bert_score, dict_rules = self.apply_game_dict_rules(cleaned, bert_score)
        if dict_rules != 'none':
            method = f'BERT+dict[{dict_rules}]'

        # Step 5: 强度修饰符
        final_score = apply_intensity_modifiers(cleaned, bert_score)
        method += '+intensity'

        # Step 6: LLM困难样本兜底
        is_difficult, diff_reason = self.is_difficult_sample(text, final_score)
        if is_difficult and self.use_llm:
            llm_score = self.llm_predict(text)
            if llm_score is not None:
                # BERT(0.4) + LLM(0.6) 加权融合
                final_score = llm_score * 0.6 + final_score * 0.4
                method = f'LLM[{diff_reason}]+BERT-blend'

        final_score = round(max(0.0, min(1.0, final_score)), 4)
        label = score_to_label(final_score)

        return final_score, label, method

    def analyze_batch(
        self,
        texts: List[str],
        use_llm_for_difficult: bool = True,
        progress_interval: int = 500,
    ) -> List[Dict]:
        """
        批量分析
        
        Args:
            texts: 文本列表
            use_llm_for_difficult: 是否对困难样本启用LLM
            progress_interval: 进度打印间隔
        
        Returns:
            [{score, label, method, text}, ...]
        """
        # 1. 批量BERT
        print(f"[Batch] BERT批量推理 {len(texts)} 条...")
        cleaned_texts = [clean_noise(t) for t in texts]
        bert_scores = self.bert_predict_batch(cleaned_texts)

        results = []
        for i, (orig_text, cleaned, bert_s) in enumerate(zip(texts, cleaned_texts, bert_scores)):
            # 规则修正
            if not has_meaningful_content(cleaned):
                results.append({
                    'score': 0.5, 'label': '中性',
                    'method': 'rule-noise', 'text': orig_text[:100],
                })
                continue

            # 词典修正 + 强度
            score, _ = self.apply_game_dict_rules(cleaned, bert_s)
            score = apply_intensity_modifiers(cleaned, score)
            method = 'BERT+dict+intensity'

            # LLM兜底
            if use_llm_for_difficult and self.llm_call_count < self.llm_max_calls:
                is_difficult, diff_reason = self.is_difficult_sample(orig_text, score)
                if is_difficult:
                    llm_s = self.llm_predict(orig_text)
                    if llm_s is not None:
                        score = llm_s * 0.6 + score * 0.4
                        method = f'LLM[{diff_reason}]+BERT-blend'

            score = round(max(0.0, min(1.0, score)), 4)
            results.append({
                'score': score,
                'label': score_to_label(score),
                'method': method,
                'text': orig_text[:100],
            })

            if (i + 1) % progress_interval == 0:
                print(f"  ...已处理 {i+1}/{len(texts)} (LLM调用: {self.llm_call_count}次)")

        return results

    def get_stats(self) -> Dict:
        """获取分析器统计信息"""
        return {
            'device': self.device,
            'use_llm': self.use_llm,
            'llm_max_calls': self.llm_max_calls,
            'llm_calls_used': self.llm_call_count,
            'llm_calls_remaining': self.llm_max_calls - self.llm_call_count,
            'model': str(self.model.config._name_or_path),
        }


# ==================== 测试 ====================
if __name__ == '__main__':
    print("=" * 70)
    print("混合情感分析器 - 单条测试")
    print("=" * 70)

    analyzer = HybridSentimentAnalyzer(use_llm=False)  # 测试时不调用LLM

    test_cases = [
        # 正面
        ("女皇大人真的太美了，这PV质量绝了！", "正面"),
        ("啊啊啊冰神好好看！！！", "正面"),
        ("原神越来越好，期待新版本", "正面"),
        # 负面
        ("这是什么垃圾剧情，完全看不懂", "负面"),
        ("xswl，这pv也太敷衍了吧", "负面/中性"),
        # 中性/困难
        ("doge", "中性"),
        ("[doge] 至冬剧情太刀了", "中性/正面"),
        ("蚌埠住了，执行官太强", "中性"),
        ("回复 @某某: 你说的对", "中性"),
        # 反讽
        ("太厉害了（反讽）", "负面"),
        # 纯游戏术语
        ("钟离 至冬 天理", "中性"),
        # 空/噪声
        ("", "中性"),
        ("回复 @用户: ", "中性"),
    ]

    print(f"\n{'文本':<35} {'分数':>6} {'标签':>4} {'方法':<25}")
    print("-" * 80)
    for text, expected in test_cases:
        score, label, method = analyzer.analyze(text)
        method_short = method[:22]
        print(f"{text[:32]:<35} {score:>6.3f} {label:>4} {method_short:<25}")

    print(f"\n分析器状态: {analyzer.get_stats()}")
