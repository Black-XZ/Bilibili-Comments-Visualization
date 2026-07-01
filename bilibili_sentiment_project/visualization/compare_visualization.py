#!/usr/bin/env python3
"""
SnowNLP vs 混合方案 对比可视化
生成8张对比图表 + 综合看板

用法:
    python compare_visualization.py --comparison ../output/comparison_data.json --output ../output/charts/

也可直接读取Excel结果文件:
    python compare_visualization.py --excel ../output/hybrid_sentiment.xlsx --output ../output/charts/
"""

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# 中文字体设置（Windows）
import matplotlib.font_manager as fm
_chinese_font = None
for font_name in ['Microsoft YaHei', 'SimHei', 'KaiTi', 'FangSong']:
    font_paths = fm.findSystemFonts(fontpaths=None, fontext='ttf')
    for fp in font_paths:
        if font_name.lower() in fp.lower():
            _chinese_font = font_name
            break
    if _chinese_font:
        break
if _chinese_font:
    plt.rcParams['font.sans-serif'] = [_chinese_font]
    plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

# 颜色配置
C_SNOW = '#00A1D6'      # SnowNLP - B站蓝
C_HYBRID = '#FB7299'    # 混合方案 - B站粉
C_POS = '#4CAF50'       # 正面
C_NEU = '#FFC107'       # 中性
C_NEG = '#F44336'       # 负面


def load_comparison_data(comparison_json=None, excel_path=None):
    """加载对比数据"""
    if comparison_json and os.path.exists(comparison_json):
        with open(comparison_json, 'r', encoding='utf-8') as f:
            return json.load(f)

    if excel_path and os.path.exists(excel_path):
        # 从Excel重新计算对比
        df_dm = pd.read_excel(excel_path, sheet_name='弹幕_混合分析')
        df_root = pd.read_excel(excel_path, sheet_name='根评论_混合分析')
        df_replies = pd.read_excel(excel_path, sheet_name='追评_混合分析')
        all_comments = pd.concat([df_root, df_replies], ignore_index=True)

        old_dm = df_dm['情感倾向'].value_counts()
        new_dm = df_dm['情感倾向_混合'].value_counts()
        old_cmt = all_comments['情感倾向'].value_counts()
        new_cmt = all_comments['情感倾向_混合'].value_counts()

        return {
            'danmaku': {
                'snow_nlp': {l: int(old_dm.get(l,0)) for l in ['正面','中性','负面']},
                'hybrid': {l: int(new_dm.get(l,0)) for l in ['正面','中性','负面']},
                'avg_snow': round(float(df_dm['情感分数'].mean()), 4),
                'avg_hybrid': round(float(df_dm['情感分数_混合'].mean()), 4),
            },
            'comment': {
                'snow_nlp': {l: int(old_cmt.get(l,0)) for l in ['正面','中性','负面']},
                'hybrid': {l: int(new_cmt.get(l,0)) for l in ['正面','中性','负面']},
                'avg_snow': round(float(all_comments['情感分数'].mean()), 4),
                'avg_hybrid': round(float(all_comments['情感分数_混合'].mean()), 4),
            },
        }

    raise ValueError("请提供 comparison_data.json 或 混合分析结果Excel")


def chart_1_emotion_radar(data, output_dir):
    """图1: 情感分布雷达图（弹幕+评论）"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    labels = ['正面', '中性', '负面']
    x = np.arange(len(labels))
    width = 0.35

    for idx, (name, key) in enumerate([('弹幕', 'danmaku'), ('评论', 'comment')]):
        ax = axes[idx]
        d = data[key]
        snow_vals = [d['snow_nlp'][l] for l in labels]
        hybrid_vals = [d['hybrid'][l] for l in labels]

        bars1 = ax.bar(x - width/2, snow_vals, width, label='SnowNLP', color=C_SNOW, alpha=0.85, edgecolor='white')
        bars2 = ax.bar(x + width/2, hybrid_vals, width, label='混合方案', color=C_HYBRID, alpha=0.85, edgecolor='white')

        ax.set_xlabel('情感倾向', fontsize=11)
        ax.set_ylabel('数量', fontsize=11)
        ax.set_title(f'{name}情感分布对比', fontsize=13, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.legend(fontsize=10)
        ax.grid(axis='y', alpha=0.3)

        # 标注数值
        for bar in bars1:
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + max(snow_vals)*0.02,
                    f'{int(bar.get_height())}', ha='center', va='bottom', fontsize=9, color=C_SNOW)
        for bar in bars2:
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + max(hybrid_vals)*0.02,
                    f'{int(bar.get_height())}', ha='center', va='bottom', fontsize=9, color=C_HYBRID)

    plt.suptitle('SnowNLP vs 混合方案 - 情感分布对比', fontsize=15, fontweight='bold')
    plt.tight_layout()
    plt.savefig(f'{output_dir}/01_情感分布对比.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("  ✅ 01_情感分布对比.png")


def chart_2_avg_score(data, output_dir):
    """图2: 平均情感分数对比"""
    fig, ax = plt.subplots(figsize=(8, 5))

    categories = ['弹幕', '评论']
    snow_avgs = [data['danmaku']['avg_snow'], data['comment']['avg_snow']]
    hybrid_avgs = [data['danmaku']['avg_hybrid'], data['comment']['avg_hybrid']]

    x = np.arange(len(categories))
    width = 0.35

    bars1 = ax.bar(x - width/2, snow_avgs, width, label='SnowNLP', color=C_SNOW, alpha=0.85)
    bars2 = ax.bar(x + width/2, hybrid_avgs, width, label='混合方案', color=C_HYBRID, alpha=0.85)

    ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5, label='中性线(0.5)')
    ax.set_ylabel('平均情感分数', fontsize=12)
    ax.set_title('平均情感分数对比', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=12)
    ax.set_ylim(0.3, 0.8)
    ax.legend(fontsize=10)
    ax.grid(axis='y', alpha=0.3)

    for bar in bars1:
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.01,
                f'{bar.get_height():.3f}', ha='center', va='bottom', fontsize=11, fontweight='bold', color=C_SNOW)
    for bar in bars2:
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.01,
                f'{bar.get_height():.3f}', ha='center', va='bottom', fontsize=11, fontweight='bold', color=C_HYBRID)

    plt.tight_layout()
    plt.savefig(f'{output_dir}/02_平均分数对比.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("  ✅ 02_平均分数对比.png")


def chart_3_pie_comparison(data, output_dir):
    """图3: 饼图对比"""
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    colors_pie = [C_POS, C_NEU, C_NEG]
    configs = [
        ('弹幕-SnowNLP', data['danmaku']['snow_nlp'], axes[0,0]),
        ('弹幕-混合方案', data['danmaku']['hybrid'], axes[0,1]),
        ('评论-SnowNLP', data['comment']['snow_nlp'], axes[1,0]),
        ('评论-混合方案', data['comment']['hybrid'], axes[1,1]),
    ]

    for title, d, ax in configs:
        values = [d['正面'], d['中性'], d['负面']]
        total = sum(values)
        ax.pie(values, labels=['正面', '中性', '负面'], colors=colors_pie,
               autopct=lambda pct: f'{pct:.1f}%\n({int(pct/100*total)})',
               startangle=90, textprops={'fontsize': 10})
        ax.set_title(title, fontsize=12, fontweight='bold')

    plt.suptitle('情感分布饼图对比', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(f'{output_dir}/03_饼图对比.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("  ✅ 03_饼图对比.png")


def chart_4_method_dist(excel_path, output_dir):
    """图4: 混合方案方法分布"""
    df_root = pd.read_excel(excel_path, sheet_name='根评论_混合分析')
    df_replies = pd.read_excel(excel_path, sheet_name='追评_混合分析')
    all_cmt = pd.concat([df_root, df_replies], ignore_index=True)

    method_dist = all_cmt['分析方法'].value_counts().head(12)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(range(len(method_dist)), method_dist.values, color=C_HYBRID, alpha=0.85)
    ax.set_yticks(range(len(method_dist)))
    ax.set_yticklabels(method_dist.index, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel('使用次数', fontsize=11)
    ax.set_title('混合方案 - 分析方法分布（Top12）', fontsize=13, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)

    for i, bar in enumerate(bars):
        ax.text(bar.get_width() + max(method_dist.values)*0.01, bar.get_y() + bar.get_height()/2,
                f'{int(bar.get_width())}', va='center', fontsize=9)

    plt.tight_layout()
    plt.savefig(f'{output_dir}/04_方法分布.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("  ✅ 04_方法分布.png")


def chart_5_score_distribution(excel_path, output_dir):
    """图5: 情感分数分布直方图对比"""
    df_dm = pd.read_excel(excel_path, sheet_name='弹幕_混合分析')

    fig, axes = plt.subplots(2, 2, figsize=(14, 8))

    for idx, (col_old, col_new, title) in enumerate([
        ('情感分数', '情感分数_混合', '弹幕'),
    ]):
        ax1 = axes[0, 0]
        ax1.hist(df_dm[col_old].dropna(), bins=20, range=(0, 1), alpha=0.7,
                color=C_SNOW, label='SnowNLP', edgecolor='white')
        ax1.hist(df_dm[col_new].dropna(), bins=20, range=(0, 1), alpha=0.7,
                color=C_HYBRID, label='混合方案', edgecolor='white')
        ax1.axvline(x=0.5, color='gray', linestyle='--', alpha=0.5)
        ax1.set_xlabel('情感分数', fontsize=11)
        ax1.set_ylabel('频数', fontsize=11)
        ax1.set_title(f'弹幕情感分数分布', fontsize=12, fontweight='bold')
        ax1.legend(fontsize=9)
        ax1.grid(alpha=0.3)

    df_root = pd.read_excel(excel_path, sheet_name='根评论_混合分析')
    df_replies = pd.read_excel(excel_path, sheet_name='追评_混合分析')
    all_cmt = pd.concat([df_root, df_replies], ignore_index=True)

    ax2 = axes[0, 1]
    ax2.hist(all_cmt['情感分数'].dropna(), bins=20, range=(0, 1), alpha=0.7,
            color=C_SNOW, label='SnowNLP', edgecolor='white')
    ax2.hist(all_cmt['情感分数_混合'].dropna(), bins=20, range=(0, 1), alpha=0.7,
            color=C_HYBRID, label='混合方案', edgecolor='white')
    ax2.axvline(x=0.5, color='gray', linestyle='--', alpha=0.5)
    ax2.set_xlabel('情感分数', fontsize=11)
    ax2.set_ylabel('频数', fontsize=11)
    ax2.set_title(f'评论情感分数分布', fontsize=12, fontweight='bold')
    ax2.legend(fontsize=9)
    ax2.grid(alpha=0.3)

    # 分数段对比
    ax3 = axes[1, 0]
    ranges = ['0-0.2', '0.2-0.4', '0.4-0.6', '0.6-0.8', '0.8-1.0']
    snow_ranges = []
    hybrid_ranges = []
    for i, (lo, hi) in enumerate([(0,0.2),(0.2,0.4),(0.4,0.6),(0.6,0.8),(0.8,1.0)]):
        snow_ranges.append(((df_dm['情感分数'] >= lo) & (df_dm['情感分数'] < hi)).sum())
        hybrid_ranges.append(((df_dm['情感分数_混合'] >= lo) & (df_dm['情感分数_混合'] < hi)).sum())

    x = np.arange(len(ranges))
    width = 0.35
    ax3.bar(x - width/2, snow_ranges, width, label='SnowNLP', color=C_SNOW, alpha=0.85)
    ax3.bar(x + width/2, hybrid_ranges, width, label='混合方案', color=C_HYBRID, alpha=0.85)
    ax3.set_xlabel('分数段', fontsize=11)
    ax3.set_ylabel('弹幕数', fontsize=11)
    ax3.set_title('弹幕分数段对比', fontsize=12, fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels(ranges)
    ax3.legend(fontsize=9)
    ax3.grid(axis='y', alpha=0.3)

    ax4 = axes[1, 1]
    ax4.axis('off')
    summary_text = (
        "分析方案对比\n"
        "━━━━━━━━━━━━━━━━\n"
        "\n"
        "SnowNLP\n"
        "  算法: 朴素贝叶斯\n"
        "  语料: 电商评论\n"
        "  特点: 简单快速\n"
        "  缺点: 不理解梗/黑话\n"
        "\n"
        "混合方案(方案4)\n"
        "  BERT: Erlangshen-RoBERTa\n"
        "  规则: 游戏领域词典\n"
        "  LLM: minimax-m2.7-free\n"
        "  特点: 语境感知强\n"
    )
    ax4.text(0.1, 0.5, summary_text, transform=ax4.transAxes,
            fontsize=11, verticalalignment='center',
            fontfamily='sans-serif',
            bbox=dict(boxstyle='round', facecolor='#f5f5f5', alpha=0.8))

    plt.suptitle('情感分数分布对比', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(f'{output_dir}/05_分数分布对比.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("  ✅ 05_分数分布对比.png")


def chart_6_dashboard(data, excel_path, output_dir):
    """图6: 综合对比看板"""
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 3, hspace=0.35, wspace=0.35)

    fig.suptitle('SnowNLP vs 混合方案(方案4) - 综合对比看板',
                 fontsize=16, fontweight='bold')

    # 1. 弹幕情感对比柱状图
    ax1 = fig.add_subplot(gs[0, 0])
    labels = ['正面', '中性', '负面']
    x = np.arange(len(labels))
    width = 0.35
    dm_snow = [data['danmaku']['snow_nlp'][l] for l in labels]
    dm_hyb = [data['danmaku']['hybrid'][l] for l in labels]
    ax1.bar(x - width/2, dm_snow, width, label='SnowNLP', color=C_SNOW)
    ax1.bar(x + width/2, dm_hyb, width, label='混合方案', color=C_HYBRID)
    ax1.set_title('弹幕情感分布', fontsize=12, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.legend(fontsize=8)
    ax1.grid(axis='y', alpha=0.3)

    # 2. 评论情感对比柱状图
    ax2 = fig.add_subplot(gs[0, 1])
    cmt_snow = [data['comment']['snow_nlp'][l] for l in labels]
    cmt_hyb = [data['comment']['hybrid'][l] for l in labels]
    ax2.bar(x - width/2, cmt_snow, width, label='SnowNLP', color=C_SNOW)
    ax2.bar(x + width/2, cmt_hyb, width, label='混合方案', color=C_HYBRID)
    ax2.set_title('评论情感分布', fontsize=12, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels)
    ax2.legend(fontsize=8)
    ax2.grid(axis='y', alpha=0.3)

    # 3. 平均分数对比
    ax3 = fig.add_subplot(gs[0, 2])
    cats = ['弹幕', '评论']
    snow_avgs = [data['danmaku']['avg_snow'], data['comment']['avg_snow']]
    hyb_avgs = [data['danmaku']['avg_hybrid'], data['comment']['avg_hybrid']]
    x = np.arange(len(cats))
    ax3.bar(x - width/2, snow_avgs, width, label='SnowNLP', color=C_SNOW)
    ax3.bar(x + width/2, hyb_avgs, width, label='混合方案', color=C_HYBRID)
    ax3.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
    ax3.set_title('平均情感分数', fontsize=12, fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels(cats)
    ax3.set_ylim(0.3, 0.8)
    ax3.legend(fontsize=8)
    ax3.grid(axis='y', alpha=0.3)

    # 4. 弹幕饼图-SnowNLP
    ax4 = fig.add_subplot(gs[1, 0])
    dm_s = data['danmaku']['snow_nlp']
    ax4.pie([dm_s['正面'], dm_s['中性'], dm_s['负面']],
            labels=['正面', '中性', '负面'],
            colors=[C_POS, C_NEU, C_NEG], autopct='%1.1f%%', startangle=90)
    ax4.set_title('弹幕-SnowNLP', fontsize=11)

    # 5. 弹幕饼图-混合
    ax5 = fig.add_subplot(gs[1, 1])
    dm_h = data['danmaku']['hybrid']
    ax5.pie([dm_h['正面'], dm_h['中性'], dm_h['负面']],
            labels=['正面', '中性', '负面'],
            colors=[C_POS, C_NEU, C_NEG], autopct='%1.1f%%', startangle=90)
    ax5.set_title('弹幕-混合方案', fontsize=11)

    # 6. 方案说明
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.axis('off')
    info = (
        "方案对比\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "SnowNLP\n"
        "  算法: 朴素贝叶斯\n"
        "  训练: 电商评论\n"
        "  速度: 快\n"
        "  语境: 弱\n\n"
        "混合方案4\n"
        "  BERT: Erlangshen-RoBERTa\n"
        "  规则: 游戏领域词典\n"
        "  LLM: minimax-m2.7-free\n"
        "  Qwen-Turbo兜底\n"
        "  语境: 强\n\n"
        "混合方案优势\n"
        "  理解网络梗/黑话\n"
        "  识别反讽阴阳怪气\n"
        "  游戏术语中性化\n"
        "  情感强度感知\n"
    )
    ax6.text(0.1, 0.5, info, transform=ax6.transAxes, fontsize=10,
            verticalalignment='center', fontfamily='sans-serif',
            bbox=dict(boxstyle='round', facecolor='#fafafa', alpha=0.9))

    plt.savefig(f'{output_dir}/06_综合对比看板.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("  ✅ 06_综合对比看板.png")


def main():
    parser = argparse.ArgumentParser(description='对比可视化')
    parser.add_argument('--comparison', '-c', default=None,
                        help='comparison_data.json 路径')
    parser.add_argument('--excel', '-e', default=None,
                        help='混合分析结果Excel路径')
    parser.add_argument('--output', '-o', default='./charts',
                        help='图表输出目录')
    args = parser.parse_args()

    print("=" * 60)
    print("SnowNLP vs 混合方案 - 对比可视化")
    print("=" * 60)

    os.makedirs(args.output, exist_ok=True)

    # 加载数据
    data = load_comparison_data(args.comparison, args.excel)

    # 生成图表
    print("\n生成对比图表...")
    chart_1_emotion_radar(data, args.output)
    chart_2_avg_score(data, args.output)
    chart_3_pie_comparison(data, args.output)
    if args.excel:
        chart_4_method_dist(args.excel, args.output)
        chart_5_score_distribution(args.excel, args.output)
    chart_6_dashboard(data, args.excel, args.output)

    print(f"\n✅ 所有图表已保存到: {args.output}/")


if __name__ == '__main__':
    main()
