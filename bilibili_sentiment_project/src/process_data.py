#!/usr/bin/env python3
"""
主处理脚本：读取Excel数据 → 混合情感分析 → 输出结果+对比

用法:
    # 基础用法（只用BERT+规则）
    python process_data.py --input data.xlsx --output results.xlsx

    # 启用LLM兜底（最多50次LLM调用）
    python process_data.py --input data.xlsx --output results.xlsx --use-llm --llm-calls 50

    # 指定BERT批大小和设备
    python process_data.py --input data.xlsx --output results.xlsx --batch-size 32 --device cuda
"""

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd
import numpy as np

# 确保能导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 在项目根目录加载 .env（process_data.py 在 src/ 下，.env 在 bilibili_sentiment_project/ 下）
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
from sentiment_analyzer import HybridSentimentAnalyzer


def load_data(filepath: str):
    """从Excel加载弹幕和评论数据"""
    print(f"[Load] 读取数据: {filepath}")
    df_dm = pd.read_excel(filepath, sheet_name='弹幕')
    df_root = pd.read_excel(filepath, sheet_name='根评论')
    df_replies = pd.read_excel(filepath, sheet_name='追评')
    all_comments = pd.concat([df_root, df_replies], ignore_index=True)

    print(f"  弹幕: {len(df_dm)} 条")
    print(f"  根评论: {len(df_root)} 条")
    print(f"  追评: {len(df_replies)} 条")
    print(f"  评论合计: {len(all_comments)} 条")

    return df_dm, df_root, df_replies, all_comments


def process_danmaku(df_dm: pd.DataFrame, analyzer: HybridSentimentAnalyzer, args) -> pd.DataFrame:
    """处理弹幕情感分析"""
    print("\n[Process] 弹幕混合情感分析...")

    texts = df_dm['弹幕内容'].astype(str).tolist()

    if args.fast:
        # 快速模式：批量BERT + 规则
        results = analyzer.analyze_batch(texts, use_llm_for_difficult=False)
    else:
        # 完整模式：逐条处理（含LLM兜底）
        results = []
        for i, text in enumerate(texts):
            score, label, method = analyzer.analyze(text)
            results.append({'score': score, 'label': label, 'method': method})
            if (i + 1) % 200 == 0:
                print(f"  ...已处理 {i+1}/{len(texts)}")

    df_dm['情感分数_混合'] = [r['score'] for r in results]
    df_dm['情感倾向_混合'] = [r['label'] for r in results]
    df_dm['分析方法'] = [r['method'] for r in results]

    return df_dm


def process_comments(all_comments: pd.DataFrame, analyzer: HybridSentimentAnalyzer, args) -> pd.DataFrame:
    """处理评论情感分析"""
    print("\n[Process] 评论混合情感分析...")

    texts = all_comments['内容'].astype(str).tolist()

    # 评论用批量模式（更快）
    results = analyzer.analyze_batch(
            texts,
            use_llm_for_difficult=args.use_llm and not args.fast,
            progress_interval=500,
        )

    all_comments['情感分数_混合'] = [r['score'] for r in results]
    all_comments['情感倾向_混合'] = [r['label'] for r in results]
    all_comments['分析方法'] = [r['method'] for r in results]

    return all_comments


def generate_comparison(df_dm, all_comments, output_dir):
    """生成SnowNLP vs 混合方案的对比数据"""
    print("\n[Compare] 生成对比统计...")

    has_old = '情感倾向' in df_dm.columns and '情感分数' in df_dm.columns
    if has_old:
        old_dm = df_dm['情感倾向'].value_counts()
        old_cmt = all_comments['情感倾向'].value_counts()
        avg_snow_dm = df_dm['情感分数'].mean()
        avg_snow_cmt = all_comments['情感分数'].mean()
    else:
        print("  ⚠️  未检测到SnowNLP结果列，跳过对比统计")
        old_dm = {}
        old_cmt = {}
        avg_snow_dm = None
        avg_snow_cmt = None

    new_dm = df_dm['情感倾向_混合'].value_counts()
    new_cmt = all_comments['情感倾向_混合'].value_counts()

    comparison = {
        'danmaku': {
            'snow_nlp': {
                'positive': int(old_dm.get('正面', 0)) if has_old else 0,
                'neutral': int(old_dm.get('中性', 0)) if has_old else 0,
                'negative': int(old_dm.get('负面', 0)) if has_old else 0,
            },
            'hybrid': {
                'positive': int(new_dm.get('正面', 0)),
                'neutral': int(new_dm.get('中性', 0)),
                'negative': int(new_dm.get('负面', 0)),
            },
            'avg_snow': round(float(avg_snow_dm), 4) if avg_snow_dm is not None else None,
            'avg_hybrid': round(float(df_dm['情感分数_混合'].mean()), 4),
        },
        'comment': {
            'snow_nlp': {
                'positive': int(old_cmt.get('正面', 0)) if has_old else 0,
                'neutral': int(old_cmt.get('中性', 0)) if has_old else 0,
                'negative': int(old_cmt.get('负面', 0)) if has_old else 0,
            },
            'hybrid': {
                'positive': int(new_cmt.get('正面', 0)),
                'neutral': int(new_cmt.get('中性', 0)),
                'negative': int(new_cmt.get('负面', 0)),
            },
            'avg_snow': round(float(avg_snow_cmt), 4) if avg_snow_cmt is not None else None,
            'avg_hybrid': round(float(all_comments['情感分数_混合'].mean()), 4),
        },
    }

    json_path = os.path.join(output_dir, 'comparison_data.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)
    print(f"  对比JSON: {json_path}")

    print("\n" + "=" * 65)
    print("【混合方案 情感分析结果】")
    print("=" * 65)

    def print_dist(name, old_d, new_d, old_avg, new_avg, has_old):
        print(f"\n  {name}情感分布:")
        for label in ['正面', '中性', '负面']:
            new_c = new_d.get(label, 0)
            old_c = old_d.get(label, 0) if has_old else 0
            delta = new_c - old_c
            prefix = f"  {old_c:4d} → " if has_old else "       "
            print(f"    {prefix}{new_c:4d}  ({delta:+4d})  {label}")
        new_avg_str = f"{new_avg:.4f}"
        old_avg_str = f"{old_avg:.4f} → " if has_old else ""
        print(f"    {old_avg_str}{new_avg_str}  平均分")

    print_dist("弹幕", old_dm, new_dm, avg_snow_dm, df_dm['情感分数_混合'].mean(), has_old)
    print_dist("评论", old_cmt, new_cmt, avg_snow_cmt, all_comments['情感分数_混合'].mean(), has_old)

    return comparison


def save_results(df_dm, all_comments, output_path, analyzer):
    """保存结果到Excel"""
    print(f"\n[Save] 保存结果: {output_path}")

    has_old = '情感倾向' in df_dm.columns and '情感分数' in df_dm.columns

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_dm.to_excel(writer, sheet_name='弹幕_混合分析', index=False)

        root_mask = all_comments['是否为追评'] == '否' if '是否为追评' in all_comments.columns else pd.Series(True, index=all_comments.index)
        all_comments[root_mask].to_excel(writer, sheet_name='根评论_混合分析', index=False)
        all_comments[~root_mask].to_excel(writer, sheet_name='追评_混合分析', index=False)

        new_dm = df_dm['情感倾向_混合'].value_counts()
        new_cmt = all_comments['情感倾向_混合'].value_counts()

        rows = [
            '弹幕-正面', '弹幕-中性', '弹幕-负面', '弹幕-平均分',
            '评论-正面', '评论-中性', '评论-负面', '评论-平均分',
            'LLM调用次数', 'LLM最大调用', '分析设备',
        ]
        snow_vals = [
            0, 0, 0, 0.0,
            0, 0, 0, 0.0,
            0, 0, 'N/A',
        ]
        if has_old:
            old_dm = df_dm['情感倾向'].value_counts()
            old_cmt = all_comments['情感倾向'].value_counts()
            snow_vals = [
                int(old_dm.get('正面', 0)), int(old_dm.get('中性', 0)),
                int(old_dm.get('负面', 0)), round(df_dm['情感分数'].mean(), 4),
                int(old_cmt.get('正面', 0)), int(old_cmt.get('中性', 0)),
                int(old_cmt.get('负面', 0)), round(all_comments['情感分数'].mean(), 4),
                0, 0, 'CPU',
            ]
        hybrid_vals = [
            int(new_dm.get('正面', 0)), int(new_dm.get('中性', 0)),
            int(new_dm.get('负面', 0)), round(df_dm['情感分数_混合'].mean(), 4),
            int(new_cmt.get('正面', 0)), int(new_cmt.get('中性', 0)),
            int(new_cmt.get('负面', 0)), round(all_comments['情感分数_混合'].mean(), 4),
            analyzer.llm_call_count, analyzer.llm_max_calls, analyzer.device,
        ]

        pd.DataFrame({'指标': rows, 'SnowNLP': snow_vals, '混合方案': hybrid_vals}
                    ).to_excel(writer, sheet_name='对比摘要', index=False)

        method_dist = all_comments['分析方法'].value_counts().head(20)
        pd.DataFrame({
            '分析方法': method_dist.index.tolist(),
            '数量': method_dist.values.tolist(),
        }).to_excel(writer, sheet_name='方法分布', index=False)

    print(f"  ✅ 已保存: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='B站视频混合情感分析')
    parser.add_argument('--input', '-i', default='../data/bilibili_data.xlsx',
                        help='输入Excel文件路径（含弹幕、根评论、追评三个sheet）')
    parser.add_argument('--output', '-o', default='../output/hybrid_sentiment.xlsx',
                        help='输出Excel文件路径')
    parser.add_argument('--use-llm', action='store_true',
                        help='启用LLM兜底（默认关闭，开启后会调用API）')
    parser.add_argument('--llm-calls', type=int, default=50,
                        help='LLM最大调用次数（默认50）')
    parser.add_argument('--batch-size', type=int, default=16,
                        help='BERT批大小（默认16）')
    parser.add_argument('--device', default=None,
                        help='计算设备: cuda / cpu / auto')
    parser.add_argument('--fast', action='store_true',
                        help='快速模式：只用BERT+规则，不逐条LLM兜底')

    args = parser.parse_args()

    print("=" * 65)
    print("B站视频混合情感分析 - 方案4")
    print("BERT + 规则词典 + LLM兜底")
    print("=" * 65)
    print(f"输入: {args.input}")
    print(f"输出: {args.output}")
    print(f"LLM: {'启用' if args.use_llm else '禁用'} (max_calls={args.llm_calls})")
    print(f"快速模式: {'是' if args.fast else '否'}")

    # 1. 加载数据
    df_dm, df_root, df_replies, all_comments = load_data(args.input)

    # 2. 初始化分析器
    print("\n[Init] 初始化混合情感分析器...")
    analyzer = HybridSentimentAnalyzer(
        use_llm=args.use_llm,
        llm_max_calls=args.llm_calls,
        device=args.device,
    )
    print(f"  状态: {analyzer.get_stats()}")

    # 3. 处理弹幕
    df_dm = process_danmaku(df_dm, analyzer, args)

    # 4. 处理评论
    all_comments = process_comments(all_comments, analyzer, args)

    # 5. 生成对比
    output_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(output_dir, exist_ok=True)
    generate_comparison(df_dm, all_comments, output_dir)

    # 6. 保存结果
    save_results(df_dm, all_comments, args.output, analyzer)

    # 7. 最终统计
    print("\n" + "=" * 65)
    print("分析完成!")
    print("=" * 65)
    print(f"总处理: {len(df_dm)}条弹幕 + {len(all_comments)}条评论")
    print(f"LLM调用: {analyzer.llm_call_count}/{analyzer.llm_max_calls}")
    print(f"输出文件: {args.output}")


if __name__ == '__main__':
    main()
