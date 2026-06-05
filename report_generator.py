import os
import pandas as pd
from datetime import datetime
from data_processor import (
    load_all_records,
    compute_service_hours_summary,
    compute_personnel_load,
    compute_region_coverage,
    compute_warnings,
    compute_review_stats,
    compute_rejection_reasons,
)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")


def generate_html_report(hours_threshold=30.0, load_threshold=20.0, coverage_threshold=3) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    df = load_all_records()

    daily = compute_service_hours_summary(df)
    personnel = compute_personnel_load(df)
    region = compute_region_coverage(df)
    warnings = compute_warnings(df, hours_threshold, load_threshold, coverage_threshold)
    review_stats = compute_review_stats(df)
    rejection_df = compute_rejection_reasons(df)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"report_{timestamp}.html"
    filepath = os.path.join(REPORTS_DIR, filename)

    html = _build_html(df, daily, personnel, region, warnings, hours_threshold, load_threshold, coverage_threshold, review_stats, rejection_df)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    return filepath


def _build_html(df, daily, personnel, region, warnings, hours_th, load_th, cov_th, review_stats, rejection_df):
    total_hours = df["服务时长_小时"].sum() if not df.empty else 0
    total_records = len(df)
    total_persons = df["人员姓名"].nunique() if not df.empty else 0
    total_regions = df["区域"].nunique() if not df.empty else 0

    warning_count = sum(len(v) for v in warnings.values())

    rows = ""
    for category, items in warnings.items():
        for item in items:
            rows += f"<tr><td>{category}</td><td>{item.get('详情', '')}</td><td>{item.get('当前值', '')}</td><td>{item.get('阈值', '')}</td></tr>"

    daily_rows = ""
    for _, r in daily.iterrows():
        daily_rows += f"<tr><td>{r['日期']}</td><td>{r['总服务时长']:.1f}</td><td>{r['记录数']}</td><td>{r['平均服务时长']:.1f}</td></tr>"

    personnel_rows = ""
    for _, r in personnel.iterrows():
        personnel_rows += f"<tr><td>{r['人员姓名']}</td><td>{r['人员角色']}</td><td>{r['总服务时长']:.1f}</td><td>{r['活动次数']}</td><td>{r['平均单次时长']:.1f}</td></tr>"

    region_rows = ""
    for _, r in region.iterrows():
        region_rows += f"<tr><td>{r['区域']}</td><td>{r['服务时长']:.1f}</td><td>{r['活动次数']}</td><td>{int(r['覆盖人数'])}</td></tr>"

    rejection_rows = ""
    if not rejection_df.empty:
        for _, r in rejection_df.iterrows():
            rejection_rows += f"<tr><td>{r['记录ID']}</td><td>{r['人员姓名']}</td><td>{r['驳回原因']}</td><td>{r['日期']}</td></tr>"
    else:
        rejection_rows = '<tr><td colspan="4" style="text-align:center;color:#636e72;">暂无待补充记录</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>公益服务报表 - {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
<style>
body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; margin: 0; padding: 20px; background: #f5f6fa; color: #2d3436; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ text-align: center; color: #2d3436; border-bottom: 3px solid #0984e3; padding-bottom: 15px; }}
h2 {{ color: #0984e3; margin-top: 30px; }}
.stats {{ display: flex; gap: 20px; margin: 20px 0; flex-wrap: wrap; }}
.stat-card {{ background: white; border-radius: 10px; padding: 20px; flex: 1; min-width: 200px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center; }}
.stat-card .number {{ font-size: 32px; font-weight: bold; color: #0984e3; }}
.stat-card .label {{ color: #636e72; margin-top: 5px; }}
.stat-card.warning {{ border-left: 4px solid #d63031; }}
.stat-card.warning .number {{ color: #d63031; }}
.stat-card.review {{ border-left: 4px solid #e17055; }}
.stat-card.review .number {{ color: #e17055; }}
.stat-card.review-green {{ border-left: 4px solid #00b894; }}
.stat-card.review-green .number {{ color: #00b894; }}
.stat-card.review-yellow {{ border-left: 4px solid #fdcb6e; }}
.stat-card.review-yellow .number {{ color: #fdcb6e; }}
table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin: 15px 0; }}
th {{ background: #0984e3; color: white; padding: 12px 15px; text-align: left; }}
td {{ padding: 10px 15px; border-bottom: 1px solid #dfe6e9; }}
tr:hover {{ background: #f0f7ff; }}
.thresholds {{ background: #ffeaa7; padding: 15px; border-radius: 8px; margin: 15px 0; }}
.thresholds span {{ margin-right: 25px; font-weight: bold; }}
.review-section {{ background: #fff5f5; padding: 20px; border-radius: 10px; margin: 20px 0; border-left: 4px solid #e17055; }}
footer {{ text-align: center; color: #b2bec3; margin-top: 40px; padding: 20px; border-top: 1px solid #dfe6e9; }}
</style>
</head>
<body>
<div class="container">
<h1>公益服务日报表</h1>
<p style="text-align:center;color:#636e72;">生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

<div class="thresholds">
<strong>当前预警阈值：</strong>
<span>服务时长下限：{hours_th}h</span>
<span>人员负载上限：{load_th}h</span>
<span>区域覆盖人数下限：{int(cov_th)}人</span>
</div>

<div class="stats">
<div class="stat-card"><div class="number">{total_hours:.1f}</div><div class="label">总服务时长(h)</div></div>
<div class="stat-card"><div class="number">{total_records}</div><div class="label">总记录数</div></div>
<div class="stat-card"><div class="number">{total_persons}</div><div class="label">参与人数</div></div>
<div class="stat-card"><div class="number">{total_regions}</div><div class="label">覆盖区域</div></div>
<div class="stat-card warning"><div class="number">{warning_count}</div><div class="label">预警条数</div></div>
</div>

<div class="review-section">
<h2 style="color:#e17055;margin-top:0;">🔄 复核结果统计</h2>
<div class="stats">
<div class="stat-card review-yellow"><div class="number">{review_stats['待复核']}</div><div class="label">待复核</div></div>
<div class="stat-card review-green"><div class="number">{review_stats['已复核']}</div><div class="label">已复核</div></div>
<div class="stat-card review"><div class="number">{review_stats['待补充']}</div><div class="label">待补充（被驳回）</div></div>
<div class="stat-card"><div class="number">{review_stats['总计']}</div><div class="label">总计</div></div>
</div>
<h3 style="color:#d63031;">驳回原因汇总</h3>
<table><thead><tr><th>记录ID</th><th>人员姓名</th><th>驳回原因</th><th>日期</th></tr></thead><tbody>{rejection_rows}</tbody></table>
</div>

<h2>⚠ 预警清单</h2>
<table><thead><tr><th>预警类别</th><th>详情</th><th>当前值</th><th>阈值</th></tr></thead><tbody>{rows or '<tr><td colspan="4" style="text-align:center;color:#636e72;">暂无预警</td></tr>'}</tbody></table>

<h2>📊 每日服务时长汇总</h2>
<table><thead><tr><th>日期</th><th>总服务时长(h)</th><th>记录数</th><th>平均服务时长(h)</th></tr></thead><tbody>{daily_rows}</tbody></table>

<h2>👥 人员负载统计</h2>
<table><thead><tr><th>姓名</th><th>角色</th><th>总服务时长(h)</th><th>活动次数</th><th>平均单次时长(h)</th></tr></thead><tbody>{personnel_rows}</tbody></table>

<h2>🗺 区域覆盖统计</h2>
<table><thead><tr><th>区域</th><th>服务时长(h)</th><th>活动次数</th><th>覆盖人数</th></tr></thead><tbody>{region_rows}</tbody></table>

<footer>公益服务报表生成系统 · 自动生成</footer>
</div>
</body>
</html>"""
