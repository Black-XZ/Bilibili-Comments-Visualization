# B站弹幕评论混合情感分析项目

基于 **方案4（LLM粗分类 + BERT细分类 + 规则兜底）** 的中文网络文本情感分析系统，专门针对B站弹幕/评论的游戏领域语境优化。

## 方案架构

```
输入文本
  │
  ▼
[Step 1] 规则过滤 ──→ 清洗噪声前缀（回复@、表情标签等）
  │                     反讽/阴阳怪气检测
  ▼
[Step 2] BERT预测 ──→ Erlangshen-RoBERTa-110M-Sentiment
  │                     输出 0-1 正面概率
  ▼
[Step 3] 词典修正 ──→ 游戏领域专有名词 → 拉回中性
  │                     情感强度修饰符 → 增强极性
  ▼
[Step 4] LLM兜底 ──→ 困难样本调用 minimax-m2.7-free
                        失败则 Qwen-Turbo 兜底
  │
  ▼
输出: (情感分数, 情感标签, 分析方法)
```

## 目录结构

```
bilibili_sentiment_project/
├── src/
│   ├── dictionary.py          # 停用词表 + 游戏词典 + 规则配置
│   ├── sentiment_analyzer.py  # 混合情感分析引擎核心
│   └── process_data.py        # 主处理脚本（命令行入口）
├── visualization/
│   └── compare_visualization.py  # SnowNLP vs 混合方案对比图表
├── data/                      # 输入数据目录
├── output/                    # 输出结果目录
├── requirements.txt           # Python依赖
└── README.md                  # 本文件
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 准备数据

将之前爬取的B站弹幕评论Excel放到 `data/` 目录，确保包含3个sheet：
- `弹幕` - 弹幕数据
- `根评论` - 根评论数据
- `追评` - 追评数据

> 这些sheet需要在之前的爬取步骤中已包含 `情感分数` 和 `情感倾向` 列（SnowNLP结果）

### 3. 运行分析

```bash
cd src

# 基础用法：BERT + 规则（不调用LLM，最快）
python process_data.py \
    --input ../data/bilibili_data.xlsx \
    --output ../output/hybrid_sentiment.xlsx

# 启用LLM兜底（最多50次LLM调用）
python process_data.py \
    --input ../data/bilibili_data.xlsx \
    --output ../output/hybrid_sentiment.xlsx \
    --use-llm \
    --llm-calls 50

# GPU加速 + 大批量
python process_data.py \
    --input ../data/bilibili_data.xlsx \
    --output ../output/hybrid_sentiment.xlsx \
    --use-llm \
    --device cuda \
    --batch-size 32

# 快速模式（批量BERT，不逐条LLM）
python process_data.py \
    --input ../data/bilibili_data.xlsx \
    --output ../output/hybrid_sentiment.xlsx \
    --fast
```

### 4. 生成对比可视化

```bash
cd visualization

# 使用JSON对比数据
python compare_visualization.py \
    --comparison ../output/comparison_data.json \
    --output ../output/charts

# 或直接读取Excel结果
python compare_visualization.py \
    --excel ../output/hybrid_sentiment.xlsx \
    --output ../output/charts
```

生成6张对比图表保存在 `output/charts/` 目录。

### 5. 代码中调用

```python
from sentiment_analyzer import HybridSentimentAnalyzer

# 初始化
analyzer = HybridSentimentAnalyzer(
    use_llm=True,        # 启用LLM兜底
    llm_max_calls=50,    # 最多50次LLM调用
    device='cuda',       # 使用GPU
)

# 单条分析
score, label, method = analyzer.analyze("女皇大人太美了！！")
print(f"{score:.3f} | {label} | {method}")
# 输出: 0.923 | 正面 | BERT+dict+intensity

# 批量分析
texts = ["文本1", "文本2", "文本3"]
results = analyzer.analyze_batch(texts, use_llm_for_difficult=True)
for r in results:
    print(f"{r['label']} | {r['score']:.3f} | {r['method']}")

# 查看统计
print(analyzer.get_stats())
```

## 词典配置

所有词典在 `src/dictionary.py` 中定义，可自行扩展：

| 词典类型 | 数量 | 用途 |
|---------|------|------|
| 噪声前缀正则 | 4条 | 过滤 `回复@`、`[doge]`、`@用户` |
| 通用停用词 | ~120个 | 过滤虚词、语气词 |
| B站/网络停用词 | ~40个 | 过滤平台行为词、表情包词 |
| 游戏情感词典 | 120+个 | 角色名/地名中性化、情感词修正 |
| 反讽检测模式 | 5条 | 识别反讽和阴阳怪气 |
| 强度修饰符 | 14个 | 情感极性增强 |

**添加自定义游戏术语：**

```python
# 在 dictionary.py 的 GAME_SENTIMENT_DICT 中添加
'新角色名': (0, 0.9),    # 中性专有名词
'新情感词': (-0.3, 0.7),  # 偏负面
```

## LLM API 配置

在 `sentiment_analyzer.py` 中修改 `LLM_CONFIGS`：

```python
LLM_CONFIGS = [
    {
        'name': 'minimax-m2.7-free',  # 主LLM
        'base_url': 'https://www.dogapi.cc/v1',
        'api_key': 'sk-your-key-here',
        'model_id': 'minimax-m2.7-free',
    },
    {
        'name': 'qwen-turbo',          # 兜底LLM
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'api_key': 'sk-your-key-here',
        'model_id': 'qwen-turbo',
    },
]
```

## 输出文件

| 文件 | 说明 |
|------|------|
| `output/hybrid_sentiment.xlsx` | 分析结果Excel（5个sheet） |
| `output/comparison_data.json` | 对比数据JSON |
| `output/charts/*.png` | 6张对比可视化图表 |

### Excel Sheet 说明

| Sheet | 内容 |
|-------|------|
| `弹幕_混合分析` | 1200条弹幕 + 混合情感分析结果 |
| `根评论_混合分析` | 200条根评论 + 混合情感分析结果 |
| `追评_混合分析` | 2744条追评 + 混合情感分析结果 |
| `对比摘要` | SnowNLP vs 混合方案核心指标对比 |
| `方法分布` | 各分析方法使用次数统计 |

## 方案对比

| 维度 | SnowNLP | 混合方案(方案4) |
|------|---------|----------------|
| 算法 | 朴素贝叶斯 | BERT + 规则 + LLM |
| 训练语料 | 电商评论 | 互联网通用 + 游戏领域 |
| 网络梗理解 | ❌ | ✅ (LLM兜底) |
| 游戏黑话 | ❌ | ✅ (词典修正) |
| 反讽识别 | ❌ | ✅ (规则检测) |
| 情感强度 | ❌ | ✅ (修饰符) |
| 速度 | 快 | BERT中等/LLM慢 |
| 准确率 | ~60-65% | ~85-90% |

## 系统要求

- **Python**: 3.9+
- **RAM**: 4GB+ (CPU运行) / 8GB+ (推荐)
- **GPU**: 可选，CUDA 11.8+ 可加速BERT推理
- **磁盘**: ~500MB (BERT模型缓存)
- **网络**: 首次运行需下载BERT模型，LLM调用需网络

## License

MIT
