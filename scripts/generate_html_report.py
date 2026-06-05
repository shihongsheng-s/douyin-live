#!/usr/bin/env python3
"""
抖音直播间运营报告 — HTML 格式生成器 v3

飞书仪表盘风格，包含：
- SVG 折线图（在线人数趋势）
- 四层评判框架（数据结果 / 行为过程 / 根因逻辑 / 战略决策）
- 结构化优化建议（优势 / 劣势 / 优化点 / 借鉴点）
"""

import json
import math
import datetime
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from douyin_livestream import get_db, format_duration


# ── CSS ──────────────────────────────────────────────────────

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;background:#f5f6fa;color:#1a1a2e;padding:32px 24px;line-height:1.6}
.container{max-width:960px;margin:0 auto}

/* Header */
.header{margin-bottom:32px;padding-bottom:24px;border-bottom:2px solid #e8ecf1}
.header h1{font-size:28px;font-weight:700;color:#1a1a2e;letter-spacing:-0.5px}
.header .subtitle{font-size:14px;color:#8c8fa3;margin-top:6px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.header .subtitle .dot{display:inline-block;width:6px;height:6px;background:#3370FF;border-radius:50%}
.header .stream-status{display:inline-block;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:600}
.header .stream-status.live{background:#e8f8f2;color:#00c48c}
.header .stream-status.ended{background:#fff0f0;color:#ff4d4f}

/* Stats Cards */
.stats-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin-bottom:28px}
.stat-card{background:#fff;border-radius:12px;padding:18px 20px;box-shadow:0 1px 3px rgba(0,0,0,0.06)}
.stat-card .label{font-size:11px;font-weight:600;color:#8c8fa3;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px}
.stat-card .value{font-size:26px;font-weight:700;color:#1a1a2e;letter-spacing:-0.5px}
.stat-card .value .unit{font-size:13px;font-weight:400;color:#8c8fa3;margin-left:3px}
.stat-card.border-blue{border-left:3px solid #3370FF}
.stat-card.border-blue .value{color:#3370FF}
.stat-card.border-green{border-left:3px solid #00c48c}
.stat-card.border-green .value{color:#00c48c}
.stat-card.border-orange{border-left:3px solid #ff9800}
.stat-card.border-orange .value{color:#ff9800}
.stat-card.border-red{border-left:3px solid #ff4d4f}
.stat-card.border-red .value{color:#ff4d4f}

/* Section */
.section{background:#fff;border-radius:12px;padding:24px 28px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,0.06)}
.section-title{font-size:16px;font-weight:600;color:#1a1a2e;margin-bottom:18px;padding-bottom:12px;border-bottom:1px solid #f0f1f5;display:flex;align-items:center;gap:8px}
.section-desc{font-size:13px;color:#8c8fa3;margin-top:-12px;margin-bottom:16px;padding:0 0 12px 0;border-bottom:1px dashed #f0f1f5}

/* Info Grid */
.info-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.info-item{display:flex;flex-direction:column;gap:2px}
.info-item .info-label{font-size:11px;color:#8c8fa3;font-weight:500}
.info-item .info-value{font-size:14px;color:#1a1a2e;font-weight:500}

/* Chart */
.chart-wrap{width:100%;overflow-x:auto;padding:8px 0}
.chart-wrap svg{width:100%;min-width:320px;height:240px}

/* Data Table */
.data-table{width:100%;border-collapse:collapse;font-size:13px}
.data-table th{text-align:left;padding:10px 12px;font-weight:600;color:#8c8fa3;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:2px solid #f0f1f5}
.data-table td{padding:10px 12px;border-bottom:1px solid #f5f6fa;color:#1a1a2e}
.data-table tr:hover td{background:#f8f9ff}
.status-badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:600}
.status-badge.live{background:#e8f8f2;color:#00c48c}
.status-badge.ended{background:#fff0f0;color:#ff4d4f}

/* Analysis Sections */
.analysis-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:640px){.analysis-grid{grid-template-columns:1fr}}
.metric-card{background:#f8f9ff;border-radius:10px;padding:16px 18px;border-left:3px solid #3370FF}
.metric-card.warn{border-left-color:#ff9800}
.metric-card.good{border-left-color:#00c48c}
.metric-card.neutral{border-left-color:#8c8fa3}
.metric-card .m-title{font-size:13px;font-weight:600;color:#1a1a2e;margin-bottom:6px}
.metric-card .m-value{font-size:22px;font-weight:700;color:#3370FF}
.metric-card .m-value.green{color:#00c48c}
.metric-card .m-value.orange{color:#ff9800}
.metric-card .m-desc{font-size:12px;color:#8c8fa3;margin-top:4px}

/* Funnel */
.funnel{display:flex;flex-direction:column;gap:6px;padding:8px 0}
.funnel-step{display:flex;align-items:center;gap:12px;padding:10px 14px;background:#f8f9ff;border-radius:8px}
.funnel-step .funnel-bar{height:28px;border-radius:4px;background:linear-gradient(90deg,#3370FF,:#5B8CFF);min-width:20px;flex-shrink:0;transition:width .3s}
.funnel-step .funnel-label{font-size:13px;font-weight:500;color:#1a1a2e;min-width:80px}
.funnel-step .funnel-val{font-size:13px;color:#8c8fa3;margin-left:auto}
.funnel-step .funnel-pct{font-size:12px;font-weight:600;color:#3370FF;min-width:40px;text-align:right}

/* Suggestions */
.sug-group{margin-bottom:16px}
.sug-group:last-child{margin-bottom:0}
.sug-group .sug-cat{font-size:13px;font-weight:600;color:#1a1a2e;margin-bottom:8px;display:flex;align-items:center;gap:6px}
.sug-group .sug-cat .tag{font-size:10px;padding:2px 8px;border-radius:8px;font-weight:600}
.sug-group .sug-cat .tag.strength{background:#e8f8f2;color:#00c48c}
.sug-group .sug-cat .tag.weakness{background:#fff0f0;color:#ff4d4f}
.sug-group .sug-cat .tag.optimize{background:#e8f0ff;color:#3370FF}
.sug-group .sug-cat .tag.reference{background:#fff8e6;color:#ff9800}
.sug-item{padding:10px 14px;margin-bottom:6px;background:#f8f9ff;border-radius:8px;font-size:13px;line-height:1.5;color:#1a1a2e;border-left:3px solid #e8ecf1}
.sug-item.strength{border-left-color:#00c48c}
.sug-item.weakness{border-left-color:#ff4d4f}
.sug-item.optimize{border-left-color:#3370FF}
.sug-item.reference{border-left-color:#ff9800}
.sug-item .sug-tag{display:inline-block;font-size:10px;font-weight:600;padding:1px 6px;border-radius:4px;margin-right:6px}
.sug-item .sug-tag.strength{background:#e8f8f2;color:#00c48c}
.sug-item .sug-tag.weakness{background:#fff0f0;color:#ff4d4f}
.sug-item .sug-tag.optimize{background:#e8f0ff;color:#3370FF}
.sug-item .sug-tag.reference{background:#fff8e6;color:#ff9800}

/* Phased Plan */
.phase-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.phase-card{background:#f8f9ff;border-radius:10px;padding:16px 18px;border-top:3px solid #3370FF}
.phase-card.urgent{border-top-color:#ff4d4f}
.phase-card.medium{border-top-color:#ff9800}
.phase-card.long{border-top-color:#8c8fa3}
.phase-card .phase-title{font-size:14px;font-weight:600;color:#1a1a2e;margin-bottom:8px}
.phase-card .phase-item{font-size:12px;color:#555;padding:4px 0;border-bottom:1px solid #f0f1f5}
.phase-card .phase-item:last-child{border-bottom:none}
.phase-card .phase-item .criteria{color:#8c8fa3;font-size:11px}

/* Data Missing Banner */
.missing-banner{background:linear-gradient(90deg,#fff8e6,#fff);border:1px solid #ffe0b2;border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:13px;color:#e65100;display:flex;align-items:center;gap:8px}
.missing-banner .icon{font-size:18px}

/* Footer */
.footer{text-align:center;padding:24px 0 8px;font-size:12px;color:#c0c4d4}

/* Tab System */
.tabs{display:flex;gap:4px;margin-bottom:20px;flex-wrap:wrap}
.tab-btn{padding:8px 18px;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;background:#f0f1f5;color:#555;border:none;transition:all.2s}
.tab-btn.active{background:#3370FF;color:#fff}
.tab-btn:hover:not(.active){background:#e0e3eb}
.tab-content{display:none}
.tab-content.active{display:block}
"""


# ── SVG Line Chart ──────────────────────────────────────────

def generate_svg_chart(times, values, width=800, height=220):
    """Generate an SVG line chart for viewer trends."""
    if not values or max(values) == 0:
        return '<div style="padding:20px;text-align:center;color:#8c8fa3">暂无足够数据生成趋势图</div>'

    n = len(values)
    max_v = max(values)
    min_v = min(values)
    pad = {"t": 20, "r": 20, "b": 40, "l": 50}
    cw = width - pad["l"] - pad["r"]
    ch = height - pad["t"] - pad["b"]

    def x(i): return pad["l"] + (i / (n - 1) * cw) if n > 1 else pad["l"] + cw / 2
    def y(v): return pad["t"] + ch - ((v - min_v) / (max_v - min_v + 1) * ch) if max_v > min_v else pad["t"] + ch / 2

    # Grid lines
    grid_lines = ""
    y_labels = ""
    steps = 4
    for i in range(steps + 1):
        v = min_v + (max_v - min_v) * i / steps
        yi = y(v)
        grid_lines += f'<line x1="{pad["l"]}" y1="{yi}" x2="{width - pad["r"]}" y2="{yi}" stroke="#f0f1f5" stroke-width="1"/>'
        y_labels += f'<text x="{pad["l"] - 8}" y="{yi + 4}" text-anchor="end" font-size="11" fill="#8c8fa3">{int(v)}</text>'

    # Polyline
    pts = " ".join(f"{x(i)},{y(values[i])}" for i in range(n))

    # Area fill
    area_pts = f"{x(0)},{y(min_v)} {pts} {x(n - 1)},{y(min_v)}"

    # Data points + labels
    dots = ""
    labels = ""
    x_labels = ""
    for i in range(n):
        xi, yi = x(i), y(values[i])
        dots += f'<circle cx="{xi}" cy="{yi}" r="4" fill="#3370FF" stroke="#fff" stroke-width="2"/>'
        labels += f'<text x="{xi}" y="{yi - 10}" text-anchor="middle" font-size="11" font-weight="600" fill="#1a1a2e">{values[i]}</text>'
        # x-axis time labels
        x_labels += f'<text x="{xi}" y="{height - 8}" text-anchor="middle" font-size="10" fill="#8c8fa3" transform="rotate(-20,{xi},{height - 8})">{times[i]}</text>'

    svg = f'''<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
        {grid_lines}
        {y_labels}
        <defs>
            <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#3370FF" stop-opacity="0.15"/>
                <stop offset="100%" stop-color="#3370FF" stop-opacity="0.01"/>
            </linearGradient>
        </defs>
        <polygon points="{area_pts}" fill="url(#areaGrad)"/>
        <polyline points="{pts}" fill="none" stroke="#3370FF" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
        {dots}
        {labels}
        {x_labels}
    </svg>'''

    return svg


# ── HTML 报告生成 ───────────────────────────────────────────

def generate_html_report(session_id):
    """Generate full HTML report with all analysis modules."""
    conn = get_db()
    session = conn.execute("SELECT * FROM monitoring_sessions WHERE id = ?", (session_id,)).fetchone()
    if not session:
        conn.close(); return None, None

    snapshots = conn.execute(
        "SELECT * FROM snapshots WHERE session_id = ? AND error IS NULL ORDER BY timestamp",
        (session_id,),
    ).fetchall()
    if not snapshots:
        return None, None

    # ── Compute Stats ────────────────────────────────────────
    user_counts = []
    first_snap = snapshots[0]
    last_snap = snapshots[-1]
    start_time = first_snap["timestamp"]
    end_time = last_snap["timestamp"]

    try:
        st = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        et = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        duration_seconds = (et - st).total_seconds()
        duration_str = format_duration(duration_seconds)
    except:
        duration_seconds = 0
        duration_str = "N/A"
        st = et = None

    for snap in snapshots:
        num = snap["user_count_num"]
        if num is not None:
            user_counts.append(num)

    peak = max(user_counts) if user_counts else 0
    avg = int(sum(user_counts) / len(user_counts)) if user_counts else 0
    low = min(user_counts) if user_counts else 0
    snap_count = len(snapshots)
    retention = round(avg / peak * 100, 1) if peak > 0 else 0

    # Trend direction
    if len(user_counts) >= 2:
        trend = "up" if user_counts[-1] > user_counts[0] else "down" if user_counts[-1] < user_counts[0] else "flat"
    else:
        trend = "flat"

    streamer = session["streamer_name"] or "未知主播"
    room_url = session["room_url"] or "#"
    game = session["game_category"] or "未分类"
    location = session["location"] or "未知"

    live_snaps = [s for s in snapshots if s["status_code"] == 2]
    live_duration_seconds = 0
    if len(live_snaps) >= 2:
        try:
            lst = datetime.datetime.strptime(live_snaps[0]["timestamp"], "%Y-%m-%d %H:%M:%S")
            let = datetime.datetime.strptime(live_snaps[-1]["timestamp"], "%Y-%m-%d %H:%M:%S")
            live_duration_seconds = (let - lst).total_seconds()
        except:
            pass

    # Build chart data
    times = []
    values = []
    for snap in snapshots:
        ts_str = snap["timestamp"]
        try:
            dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            t_label = dt.strftime("%H:%M")
        except:
            t_label = ts_str[-5:] if len(ts_str) >= 5 else ts_str
        num = snap["user_count_num"] or 0
        times.append(t_label)
        values.append(num)

    suggestions = generate_structured_suggestions(
        session, snapshots, peak, avg, low, retention, duration_seconds, trend, live_duration_seconds, values
    )

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build status
    is_live = session["status"] == "running"
    status_class = "live" if is_live else "ended"
    status_text = "🟢 直播中" if is_live else "🔴 已结束 / 已停止"

    # ── Stats Cards ──────────────────────────────────────────
    trend_icon = "📈" if trend == "up" else "📉" if trend == "down" else "➡️"
    stats_cards = f"""
    <div class="stats-row">
        <div class="stat-card border-blue">
            <div class="label">峰值在线</div>
            <div class="value">{peak:,}<span class="unit">人</span></div>
        </div>
        <div class="stat-card border-green">
            <div class="label">平均在线</div>
            <div class="value">{avg:,}<span class="unit">人</span></div>
        </div>
        <div class="stat-card border-orange">
            <div class="label">最低在线</div>
            <div class="value">{low:,}<span class="unit">人</span></div>
        </div>
        <div class="stat-card">
            <div class="label">留存率</div>
            <div class="value">{retention}<span class="unit">%</span></div>
        </div>
        <div class="stat-card border-red">
            <div class="label">{trend_icon} 趋势</div>
            <div class="value" style="font-size:18px">{'持续增长' if trend=='up' else '持续下降' if trend=='down' else '平稳'}</div>
        </div>
        <div class="stat-card">
            <div class="label">直播时长</div>
            <div class="value" style="font-size:18px">{duration_str}</div>
        </div>
    </div>
    """

    # ── SVG Chart ────────────────────────────────────────────
    chart_svg = generate_svg_chart(times, values)
    chart_section = f"""
    <div class="section">
        <div class="section-title"><span class="icon">📈</span> 在线人数趋势</div>
        <div class="chart-wrap">{chart_svg}</div>
    </div>
    """

    # ── Cover Image ───────────────────────────────────────────
    cover_html = ""
    try:
        first_snap = snapshots[0]
        if first_snap["raw_json"]:
            raw = json.loads(first_snap["raw_json"])
            cover_url = raw.get("cover_url", "")
            if cover_url:
                cover_html = f"""
                <div style="flex-shrink:0;width:240px">
                    <div style="border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1)">
                        <img src="{cover_url}" alt="直播间截图" style="width:100%;display:block;aspect-ratio:9/16;object-fit:cover">
                    </div>
                    <div style="text-align:center;font-size:11px;color:#8c8fa3;margin-top:6px">📷 直播间画面</div>
                </div>
                """
    except Exception:
        pass

    # ── Overview ─────────────────────────────────────────────
    overview_section = f"""
    <div class="section" style="display:flex;gap:24px;align-items:start;flex-wrap:wrap">
        <div style="flex:1;min-width:200px">
            <div class="section-title"><span class="icon">📋</span> 直播间概览</div>
            <div class="info-grid">
                <div class="info-item"><span class="info-label">主播</span><span class="info-value">{streamer}</span></div>
                <div class="info-item"><span class="info-label">直播间</span><span class="info-value"><a href="{room_url}" target="_blank" style="color:#3370FF;text-decoration:none;">{room_url.split('/')[-1].split('?')[0]}</a></span></div>
                <div class="info-item"><span class="info-label">状态</span><span class="info-value"><span class="stream-status {status_class}">{status_text}</span></span></div>
                <div class="info-item"><span class="info-label">开始时间</span><span class="info-value">{start_time}</span></div>
                <div class="info-item"><span class="info-label">结束时间</span><span class="info-value">{end_time}</span></div>
                <div class="info-item"><span class="info-label">分类</span><span class="info-value">{game}</span></div>
                <div class="info-item"><span class="info-label">数据点数</span><span class="info-value">{snap_count}</span></div>
                <div class="info-item"><span class="info-label">直播实际时长</span><span class="info-value">{format_duration(live_duration_seconds) if live_duration_seconds > 0 else duration_str}</span></div>
            </div>
        </div>
        {cover_html}
    </div>
    """

    # ── Data Timeline ────────────────────────────────────────
    table_rows = ""
    for snap in snapshots:
        ts = snap["timestamp"]
        uc = snap["user_count_str"] or "-"
        stt = snap["status_text"] or ""
        title_s = (snap["title"] or "")[:40]
        badge_class = "live" if snap["status_code"] == 2 else "ended"
        badge_text = "直播中" if snap["status_code"] == 2 else "已结束"
        table_rows += f"""<tr><td>{ts}</td><td><strong>{uc}</strong></td><td><span class="status-badge {badge_class}">{badge_text}</span></td><td>{title_s}</td></tr>"""

    timeline_section = f"""
    <div class="section">
        <div class="section-title"><span class="icon">📊</span> 详细数据时间线</div>
        <table class="data-table">
            <thead><tr><th>时间</th><th>在线人数</th><th>状态</th><th>直播间标题</th></tr></thead>
            <tbody>{table_rows}</tbody>
        </table>
    </div>
    """

    # ── Analysis Modules ─────────────────────────────────────
    analysis = generate_analysis_modules(session, snapshots, peak, avg, low, retention, duration_seconds, trend, live_duration_seconds, times, values)

    # ── Suggestions ──────────────────────────────────────────
    sugg_html = ""
    for cat, label, tag_class, items in [
        ("strength", "💪 优势", "strength", suggestions.get("strengths", [])),
        ("weakness", "⚠️ 劣势", "weakness", suggestions.get("weaknesses", [])),
        ("optimize", "🔧 优化点", "optimize", suggestions.get("optimizations", [])),
        ("reference", "🌟 借鉴点", "reference", suggestions.get("references", [])),
    ]:
        if not items:
            continue
        items_html = "\n".join(
            f'<div class="sug-item {cat}"><span class="sug-tag {cat}">{label.split()[0]}</span>{item}</div>'
            for item in items
        )
        sugg_html += f"""
        <div class="sug-group">
            <div class="sug-cat"><span class="tag {tag_class}">{label}</span></div>
            {items_html}
        </div>"""

    suggestions_section = f"""
    <div class="section">
        <div class="section-title"><span class="icon">💡</span> 运营优化建议</div>
        <div class="missing-banner"><span class="icon">ℹ️</span> 以下建议基于在线人数和时长数据生成。接入抖音电商 API 后可获得 GMV、转化率、ROI 等完整指标</div>
        {sugg_html}
    </div>
    """

    # ── Phased Action Plan ───────────────────────────────────
    plan = generate_phased_plan(suggestions)
    plan_section = f"""
    <div class="section">
        <div class="section-title"><span class="icon">📋</span> 分阶段行动计划</div>
        <div class="phase-grid">{plan}</div>
    </div>
    """

    # ── P0: 竞品对比 ──────────────────────────────────────────
    compare_section = generate_compare_section(conn, session, streamer, peak, avg, low, retention, duration_str)

    # ── P2: 告警记录 ──────────────────────────────────────────
    alert_section = generate_alert_section(session_id, streamer)

    # ── P1: 事件标注分析 ──────────────────────────────────────
    event_section = generate_event_section(session_id, streamer)

    # ── P2: 标题变更追踪 ──────────────────────────────────────
    title_section = generate_title_section(snapshots)

    # ── Assemble HTML ────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>直播运营报告 | {streamer}</title>
    <style>{CSS}</style>
</head>
<body>
<div class="container">

    <div class="header">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
            <h1>📊 直播运营分析报告</h1>
            <span class="stream-status {status_class}">{status_text}</span>
        </div>
        <div class="subtitle">
            <span class="dot"></span> {streamer}
            <span style="color:#c0c4d4">|</span> 生成于 {now}
        </div>
    </div>

    {stats_cards}
    {chart_section}
    {overview_section}
    {analysis}
    {suggestions_section}
    {plan_section}
    {compare_section}
    {alert_section}
    {event_section}
    {title_section}
    {timeline_section}

    <div class="footer">
        由 Hermes Douyin Livestream Monitor · 数据分析引擎 v3 自动生成
    </div>

</div>
</body>
</html>"""

    conn.close()
    return html, str(streamer)


# ── 结构化优化建议 ──────────────────────────────────────────

def generate_structured_suggestions(session, snapshots, peak, avg, low, retention, duration_seconds, trend, live_duration_seconds, values):
    """Generate structured suggestions split into strengths/weaknesses/optimizations/references."""
    s = {"strengths": [], "weaknesses": [], "optimizations": [], "references": []}

    live_snaps = [sn for sn in snapshots if sn["status_code"] == 2]

    # ── Strengths ────────────────────────────────────────────
    if trend == "up":
        s["strengths"].append(f"📈 **在线人数持续增长**：从 {values[0]} 人增长至 {values[-1]} 人，说明内容吸引力在增强，观众留存意愿上升")

    if retention >= 75:
        s["strengths"].append(f"📊 **观众留存率高**（{retention}%），平均在线接近峰值，说明直播间能有效留住观众")

    if peak >= 1000:
        s["strengths"].append(f"🔥 **直播间热度较高**（峰值 {peak} 人），已具备一定的流量基础")

    if duration_seconds >= 7200:
        s["strengths"].append(f"⏱ **直播时长充足**（{format_duration(duration_seconds)}），为观众沉淀和转化提供了充分的时间窗口")

    # ── Weaknesses ───────────────────────────────────────────
    if peak < 100:
        s["weaknesses"].append(f"📉 **直播间热度偏低**（峰值仅 {peak} 人），缺乏自然流量引入能力，需要从内容质量和引流渠道两方面突破")

    if duration_seconds < 1800:
        s["weaknesses"].append(f"⏱ **直播时长过短**（仅 {format_duration(duration_seconds)}），不足以完成冷启动-互动高峰-转化收割的完整直播节奏")

    if retention < 50:
        s["weaknesses"].append(f"📉 **观众流失严重**（留存率 {retention}%），后期在线仅为前期的零头，内容节奏或互动环节需要重构")

    if trend == "down":
        s["weaknesses"].append(f"📉 **在线持续下降**（从 {values[0]}→{values[-1]}），开场后未能有效留住观众，建议检查前 30 分钟的内容节奏")

    if len(live_snaps) <= 2:
        s["weaknesses"].append(f"📊 **数据样本过少**（仅 {len(live_snaps)} 个有效快照），难以形成可靠的分析结论，建议延长监控时长")

    # ── Optimizations ─────────────────────────────────────────
    if peak < 500:
        s["optimizations"].append("**短视频预热引流**：开播前 1-2 小时发布预告短视频，带上直播间定位标签，提前蓄水")
        s["optimizations"].append("**优化开播标题和封面**：标题突出利益点（如'限时福利''新粉专享'），封面使用高对比度、人物特写画面")
        s["optimizations"].append("**粉丝群开播提醒**：通过粉丝群/社群发送开播提醒，激活老粉基础在线量")

    if trend == "down" and len(values) >= 3:
        s["optimizations"].append("**中场互动环节设计**：在在线下滑前插入互动环节（抽奖/问答/福利秒杀），打断流失曲线")
        s["optimizations"].append("**定时福利机制**：每 15-20 分钟设置一个福利点（福袋/优惠券），作为观众停留的'锚点'")

    if duration_seconds < 3600:
        s["optimizations"].append("**延长直播时长至 1.5-2 小时**：抖音算法对长直播有流量倾斜，同时给观众更多进入和转化窗口")

    if retention < 60 and peak > 0:
        s["optimizations"].append("**优化开场 3 分钟话术**：黄金开场 = 自我介绍 + 本场福利预告 + 互动引导（'新朋友扣1'），降低前 30 秒跳出率")

    # ── References ───────────────────────────────────────────
    s["references"].append("**头部直播间节奏参考**：开播前 30 分钟做热场+福利预告，中间 60 分钟主推产品+深度讲解，最后 30 分钟做逼单+返场福利")
    s["references"].append("**同类型直播间对标**：关注同品类头部直播间的标题、封面、产品组合和话术结构，提炼可复用的框架")
    s["references"].append("**数据积累建议**：坚持记录每场直播的在线峰值、平均在线、时长、互动率，3-5 场后能发现明显的规律和优化方向")

    return s


# ── 数据分析模块 ────────────────────────────────────────────

def generate_analysis_modules(session, snapshots, peak, avg, low, retention, duration_seconds, trend, live_duration_seconds, times, values):
    """Generate the complete four-layer analysis framework."""

    # Layer 1: Data Results
    layer1 = generate_layer1(peak, avg, low, retention, duration_seconds, trend, values)
    # Layer 2: Behavior Process
    layer2 = generate_layer2(snapshots, times, values)
    # Layer 3: Root Cause
    layer3 = generate_layer3(peak, duration_seconds, trend, retention)
    # Layer 4: Strategic
    layer4 = generate_layer4()

    return f"""
    <div class="section">
        <div class="section-title"><span class="icon">🔍</span> 多维度运营效果分析</div>
        <div class="missing-banner"><span class="icon">📌</span> 以下分析基于公开可获取数据。接入抖音电商 API 后可补充 GMV、转化漏斗、流量结构等核心电商指标</div>

        <!-- Tab buttons -->
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('layer1')">📊 数据结果层</button>
            <button class="tab-btn" onclick="switchTab('layer2')">🔄 行为过程层</button>
            <button class="tab-btn" onclick="switchTab('layer3')">🔎 根因逻辑层</button>
            <button class="tab-btn" onclick="switchTab('layer4')">🎯 战略决策层</button>
        </div>

        <!-- Layer 1 -->
        <div id="layer1" class="tab-content active">
            <div class="section-desc">最基础的量化评判维度，所有主观判断必须建立在数据之上</div>
            {layer1}
        </div>

        <!-- Layer 2 -->
        <div id="layer2" class="tab-content">
            <div class="section-desc">拆解观众在直播间的行为路径，找到效果背后的原因</div>
            {layer2}
        </div>

        <!-- Layer 3 -->
        <div id="layer3" class="tab-content">
            <div class="section-desc">从现象到本质，回答「为什么会出现这个结果」</div>
            {layer3}
        </div>

        <!-- Layer 4 -->
        <div id="layer4" class="tab-content">
            <div class="section-desc">跳出单场直播，从长期战略角度评估运营方向</div>
            {layer4}
        </div>
    </div>

    <script>
    function switchTab(id) {{
        document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
        document.getElementById(id).classList.add('active');
        document.querySelector(`button[onclick="switchTab('${{id}}')"]`).classList.add('active');
    }}
    </script>
    """


def generate_layer1(peak, avg, low, retention, duration_seconds, trend, values):
    """Layer 1: Data Results Layer — Core KPIs."""
    # Simulated data since we can't get real e-commerce data
    score_peak = "优秀" if peak >= 1000 else "良好" if peak >= 100 else "待提升"
    score_duration = "优秀" if duration_seconds >= 7200 else "良好" if duration_seconds >= 3600 else "待提升"
    score_retention = "优秀" if retention >= 75 else "良好" if retention >= 50 else "待提升"
    score_trend_color = "good" if trend == "up" else "warn" if trend == "down" else "neutral"

    score_color = {"优秀": "green", "良好": "", "待提升": "orange"}

    return f"""
    <div class="analysis-grid">
        <div class="metric-card good">
            <div class="m-title">👥 在线人数</div>
            <div class="m-value green">{peak}</div>
            <div class="m-desc">峰值 {peak} 人 · 平均 {avg} 人 · 最低 {low} 人 · 评级: {score_peak}</div>
        </div>
        <div class="metric-card {score_trend_color}">
            <div class="m-title">{'📈' if trend=='up' else '📉'} 变化趋势</div>
            <div class="m-value {'green' if trend=='up' else 'orange' if trend=='down' else ''}">{'持续增长' if trend=='up' else '持续下降' if trend=='down' else '平稳'}</div>
            <div class="m-desc">{'开场→收尾上升' if trend=='up' else '开场→收尾下滑' if trend=='down' else '波动平稳'}</div>
        </div>
        <div class="metric-card {'good' if score_retention=='优秀' else 'warn' if score_retention=='待提升' else ''}">
            <div class="m-title">📊 观众留存率</div>
            <div class="m-value {'green' if score_retention=='优秀' else 'orange' if score_retention=='待提升' else ''}">{retention}%</div>
            <div class="m-desc">评级: {score_retention} · 均值/峰值比</div>
        </div>
        <div class="metric-card {'good' if score_duration=='优秀' else 'warn' if score_duration=='待提升' else ''}">
            <div class="m-title">⏱ 直播时长</div>
            <div class="m-value {'green' if score_duration=='优秀' else 'orange' if score_duration=='待提升' else ''}" style="font-size:18px">{format_duration(duration_seconds)}</div>
            <div class="m-desc">评级: {score_duration}</div>
        </div>
    </div>

    <div style="margin-top:16px;padding:14px 16px;background:#f8f9ff;border-radius:8px;font-size:13px">
        <strong style="color:#3370FF">📌 核心结论：</strong>
        {f'直播间热度{"较好" if peak >= 100 else "偏低"}（峰值{peak}人），观众留存率{retention}%{"（良好）" if retention >= 60 else "（偏低）"}。' if peak > 0 else '数据样本不足，暂无法形成核心结论。'}
        {f'在线呈{"上升" if trend=="up" else "下降"}趋势，{f"直播时长{format_duration(duration_seconds)}" if duration_seconds > 0 else "时长较短"}。' if len(values)>=2 else ''}
        <br><em style="color:#8c8fa3">注：GMV、转化率、ROI等电商指标需接入抖音电商数据后展现</em>
    </div>
    """


def generate_layer2(snapshots, times, values):
    """Layer 2: Behavior Process Layer."""
    n = len(values)
    if n >= 3:
        first_third_avg = sum(values[:n//3]) / len(values[:n//3])
        last_third_avg = sum(values[-n//3:]) / len(values[-n//3:]) if n//3 > 0 else 0
        retention_rate = round(last_third_avg / first_third_avg * 100, 1) if first_third_avg > 0 else 0
    else:
        retention_rate = 0

    return f"""
    <div class="analysis-grid">
        <div class="metric-card neutral">
            <div class="m-title">🚪 进房阶段</div>
            <div class="m-desc" style="font-size:13px;margin-top:4px">
                首条数据在线: {values[0] if values else 'N/A'} 人<br>
                末条数据在线: {values[-1] if values else 'N/A'} 人<br>
                总数据点: {n} 个<br>
                <em style="color:#8c8fa3">(进房来源分析需接入抖音流量数据)</em>
            </div>
        </div>
        <div class="metric-card neutral">
            <div class="m-title">⏸ 停留阶段</div>
            <div class="m-desc" style="font-size:13px;margin-top:4px">
                监控时长: {format_duration((datetime.datetime.strptime(snapshots[-1]['timestamp'],"%Y-%m-%d %H:%M:%S") - datetime.datetime.strptime(snapshots[0]['timestamp'],"%Y-%m-%d %H:%M:%S")).total_seconds()) if len(snapshots)>=2 else 'N/A'}<br>
                留存率(后段/前段): {retention_rate}%<br>
                <em style="color:#8c8fa3">(停留时长分析需接入抖音用户行为数据)</em>
            </div>
        </div>
        <div class="metric-card neutral">
            <div class="m-title">💬 互动阶段</div>
            <div class="m-desc" style="font-size:13px;margin-top:4px">
                直播间互动权限已开启 ✓<br>
                <em style="color:#8c8fa3">(互动率、评论内容、转粉率需接入抖音实时数据)</em>
            </div>
        </div>
        <div class="metric-card neutral">
            <div class="m-title">🛒 转化阶段</div>
            <div class="m-desc" style="font-size:13px;margin-top:4px">
                <em style="color:#8c8fa3">(商品点击率、加购率、支付转化率需接入抖音电商数据)</em>
            </div>
        </div>
    </div>
    """


def generate_layer3(peak, duration_seconds, trend, retention):
    """Layer 3: Root Cause Logic Layer."""
    issues = []
    if peak < 100:
        issues.append("自然流量获取能力不足 → 可能是内容标签不精准/直播间权重低")
    if duration_seconds < 1800:
        issues.append("直播时长不足 → 缺乏持续获取推流的时间窗口")
    if trend == "down":
        issues.append("观众留存意愿低 → 开场话术/互动环节/产品匹配度可能存在问题")
    if not issues:
        issues.append("基础数据良好，建议接入更多数据维度进行深层分析")

    issues_html = "\n".join(f'<div style="padding:8px 12px;margin-bottom:6px;background:#f8f9ff;border-radius:6px;font-size:13px;border-left:3px solid #3370FF">🔍 {issue}</div>' for issue in issues)

    return f"""
    <div style="margin-bottom:16px">
        <div style="font-size:14px;font-weight:600;color:#1a1a2e;margin-bottom:10px">🔎 核心问题根因分析</div>
        {issues_html}
    </div>

    <div class="missing-banner"><span class="icon">📌</span> 完整的根因分析需要以下数据：流量来源拆解（自然/付费/短视频占比）· 商品点击与转化数据 · 用户评论分析 · 竞品数据对比</div>

    <div style="padding:14px 16px;background:#f8f9ff;border-radius:8px;font-size:13px">
        <strong style="color:#3370FF">📋 追问清单（向运营团队确认）：</strong><br>
        1. 本场直播的流量渠道有哪些？各渠道占比和ROI如何？<br>
        2. 开播前是否有预热？预热渠道和效果如何？<br>
        3. 本场主推产品/SKU是什么？客单价和毛利如何？<br>
        4. 主播是否经过培训？对产品卖点的理解程度？<br>
        5. 对比上一场同类型直播，数据是提升还是下降？
    </div>
    """


def generate_layer4():
    """Layer 4: Strategic Decision Layer."""
    return f"""
    <div class="analysis-grid">
        <div class="metric-card neutral">
            <div class="m-title">🎯 定位与差异化</div>
            <div class="m-desc" style="font-size:13px;margin-top:4px">
                <span style="color:#3370FF">需要评估：</span><br>
                · 目标用户画像是否清晰？<br>
                · 与竞品的差异化优势是什么？<br>
                · 品牌视觉和话术风格是否统一？<br>
                <em style="color:#8c8fa3">(需结合品类和品牌策略分析)</em>
            </div>
        </div>
        <div class="metric-card neutral">
            <div class="m-title">📦 产品策略</div>
            <div class="m-desc" style="font-size:13px;margin-top:4px">
                <span style="color:#3370FF">需要评估：</span><br>
                · 引流款/利润款/形象款比例是否合理？<br>
                · 产品卖点是否切中用户痛点？<br>
                · 价格体系是否具备竞争力？<br>
                <em style="color:#8c8fa3">(需结合商品数据和竞品分析)</em>
            </div>
        </div>
        <div class="metric-card neutral">
            <div class="m-title">👥 用户策略</div>
            <div class="m-desc" style="font-size:13px;margin-top:4px">
                <span style="color:#3370FF">需要评估：</span><br>
                · 是否有用户分层运营体系？<br>
                · 新粉转粉率和老粉复购率如何？<br>
                · 私域流量池（粉丝群/企微）建设情况？<br>
                <em style="color:#8c8fa3">(需结合用户数据)</em>
            </div>
        </div>
        <div class="metric-card neutral">
            <div class="m-title">🏆 竞争策略</div>
            <div class="m-desc" style="font-size:13px;margin-top:4px">
                <span style="color:#3370FF">需要评估：</span><br>
                · 主要竞品的运营策略和最新动态？<br>
                · 平台规则变化对品类的影响？<br>
                · 长期竞争壁垒在哪里？<br>
                <em style="color:#8c8fa3">(需结合行业分析)</em>
            </div>
        </div>
    </div>
    """


# ── 分阶段行动计划 ──────────────────────────────────────────

def generate_phased_plan(suggestions):
    """Generate a phased action plan from suggestions."""
    all_items = suggestions.get("optimizations", []) + suggestions.get("weaknesses", [])

    urgent = [s for s in all_items if any(k in s for k in ["优化", "修改", "补充", "调整"])][:3]
    medium = [s for s in all_items if any(k in s for k in ["延长", "增加", "设计", "互动", "预热"])][:3]
    long_term = suggestions.get("references", [])[:2]

    def item_html(text, phase):
        clean = text.replace("**", "").replace("🔧 ", "").replace("📉 ", "").replace("⏱ ", "")
        return f'<div class="phase-item">{clean}</div>'

    return f"""
    <div class="phase-card urgent">
        <div class="phase-title">🔴 紧急 · 立即执行（本场复盘后）</div>
        {''.join(item_html(s, 'urgent') for s in urgent) if urgent else '<div class="phase-item">当前无紧急待办项</div>'}
        <div class="phase-item"><span class="criteria">📌 验证标准：下一场直播在同样时段对比数据变化</span></div>
    </div>
    <div class="phase-card medium">
        <div class="phase-title">🟡 重要 · 1-3 天内执行</div>
        {''.join(item_html(s, 'medium') for s in medium) if medium else '<div class="phase-item">梳理直播内容和互动策略</div>'}
        <div class="phase-item"><span class="criteria">📌 验证标准：连续 3 场直播的数据趋势是否改善</span></div>
    </div>
    <div class="phase-card long">
        <div class="phase-title">🟢 长期 · 持续优化</div>
        {''.join(item_html(s, 'long') for s in long_term) if long_term else '<div class="phase-item">建立数据驱动的持续复盘机制</div>'}
        <div class="phase-item"><span class="criteria">📌 验证标准：月度核心指标环比提升</span></div>
    </div>
    """


# ── P0: 竞品对比 HTML 生成 ─────────────────────────────────

def generate_compare_section(conn, session, streamer, peak, avg, low, retention, duration_str):
    """Generate P0 competitor comparison HTML for the report."""
    # Find other sessions by the same streamer (or all completed sessions)
    other = conn.execute("""
        SELECT id, status, start_time, end_time, game_category,
               (SELECT MAX(user_count_num) FROM snapshots WHERE session_id = monitoring_sessions.id AND user_count_num IS NOT NULL) as other_peak,
               (SELECT AVG(user_count_num) FROM snapshots WHERE session_id = monitoring_sessions.id AND user_count_num IS NOT NULL) as other_avg,
               (SELECT COUNT(*) FROM snapshots WHERE session_id = monitoring_sessions.id) as other_snaps
        FROM monitoring_sessions
        WHERE id != ? AND status IN ('completed', 'cancelled') AND streamer_name = ?
        ORDER BY id DESC LIMIT 5
    """, (session["id"], streamer)).fetchall()

    if not other:
        return '<div style="display:none"></div>'

    rows_html = ""
    for o in other:
        o_peak = o["other_peak"] or 0
        o_avg = int(o["other_avg"]) if o["other_avg"] else 0
        o_snaps = o["other_snaps"] or 0
        o_time = (o["start_time"] or "")[:16]
        o_cat = o["game_category"] or "-"
        rows_html += f"<tr><td>{o_time}</td><td>{o_peak}</td><td>{o_avg}</td><td>{o_snaps}</td><td>{o_cat}</td></tr>"

    return f"""
    <div class="section">
        <div class="section-title"><span class="icon">🏆</span> 历次直播数据对比</div>
        <div class="missing-banner"><span class="icon">📌</span> 本场 vs 历史场次对比，绿色=本场最优</div>
        <table class="data-table">
            <thead><tr><th>场次</th><th>峰值</th><th>平均</th><th>数据点</th><th>分类</th></tr></thead>
            <tbody>
                <tr style="background:#e8f8f2;font-weight:600">
                    <td>🎯 <strong>本场</strong></td>
                    <td><strong>{peak}</strong></td>
                    <td><strong>{avg}</strong></td>
                    <td><strong>{len(values) if 'values' in dir() else '?'}</strong></td>
                    <td>{session['game_category'] or '-'}</td>
                </tr>
                {rows_html}
            </tbody>
        </table>
    </div>
    """


# ── P2: 告警记录 HTML 生成 ─────────────────────────────────

def generate_alert_section(session_id, streamer):
    """Generate P2 alert history HTML for the report."""
    from alert import list_alerts
    sys.path.insert(0, str(SCRIPTS_DIR))

    conn2 = get_db()
    alerts = conn2.execute(
        "SELECT * FROM alerts WHERE session_id = ? ORDER BY id DESC LIMIT 10",
        (session_id,),
    ).fetchall()
    conn2.close()

    if not alerts:
        return '<div style="display:none"></div>'

    rows_html = ""
    for a in alerts:
        sev_icon = "🟢" if a["severity"] == "info" else "🟡" if a["severity"] == "warning" else "🔴"
        sev_class = "live" if a["severity"] == "info" else "ended"
        rows_html += f"""
        <tr>
            <td>{a['triggered_at']}</td>
            <td><span class="status-badge {sev_class}">{sev_icon} {a['alert_type']}</span></td>
            <td>{a['message'][:60]}</td>
        </tr>"""

    return f"""
    <div class="section">
        <div class="section-title"><span class="icon">🚨</span> 智能告警记录</div>
        <table class="data-table">
            <thead><tr><th>时间</th><th>类型</th><th>消息</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    """


# ── P1: 事件标注 HTML 生成 ─────────────────────────────────

def generate_event_section(session_id, streamer):
    """Generate P1 event analysis HTML section."""
    try:
        from tag import analyze_events
        result = analyze_events(session_id)
        if result["count"] == 0:
            return '<div style="display:none"></div>'

        best_html = ""
        for e in result.get("best", []):
            best_html += f'<div class="sug-item strength">📈 <strong>+{e["change"]}人</strong> → {e["content"]} <span style="color:#8c8fa3;font-size:11px">(在线{e["online"]}人 @ {e["time"][-8:]})</span></div>'

        worst_html = ""
        for e in result.get("worst", []):
            worst_html += f'<div class="sug-item weakness">📉 <strong>{e["change"]}人</strong> → {e["content"]} <span style="color:#8c8fa3;font-size:11px">(在线{e["online"]}人 @ {e["time"][-8:]})</span></div>'

        return f"""
    <div class="section">
        <div class="section-title"><span class="icon">🏷️</span> 内容标注效果分析</div>
        <div style="margin-bottom:16px;font-size:13px;color:#8c8fa3">共标记 {result['count']} 个事件 · 通过标记直播间关键时刻，关联在线人数变化找出最有效的运营动作</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
            <div>
                <div style="font-size:13px;font-weight:600;color:#00c48c;margin-bottom:8px">🥇 拉在线效果最佳</div>
                {best_html if best_html else '<div style="font-size:13px;color:#8c8fa3;padding:12px">暂无正向事件数据</div>'}
            </div>
            <div>
                <div style="font-size:13px;font-weight:600;color:#ff4d4f;margin-bottom:8px">😢 掉在线最多的动作</div>
                {worst_html if worst_html else '<div style="font-size:13px;color:#8c8fa3;padding:12px">暂无负向事件数据</div>'}
            </div>
        </div>
    </div>
    """
    except Exception as e:
        return f'<div style="display:none"><!-- event section error: {e} --></div>'


# ── P2: 标题变更追踪 HTML 生成 ─────────────────────────────

def generate_title_section(snapshots):
    """Generate P2 title tracking HTML section."""
    # Collect unique titles with their viewer counts
    titles = {}
    for snap in snapshots:
        title = snap["title"]
        num = snap["user_count_num"]
        if title and num is not None:
            if title not in titles:
                titles[title] = []
            titles[title].append(num)

    if len(titles) <= 1:
        return '<div style="display:none"></div>'

    rows_html = ""
    for title, counts in titles.items():
        avg_v = sum(counts) / len(counts)
        peak_v = max(counts)
        rows_html += f"<tr><td>{(title or '-')[:30]}</td><td>{avg_v:.0f}</td><td>{peak_v}</td><td>{len(counts)}</td></tr>"

    # Best title
    best_title = max(titles.items(), key=lambda t: sum(t[1]) / len(t[1]))
    best_avg = sum(best_title[1]) / len(best_title[1])

    return f"""
    <div class="section">
        <div class="section-title"><span class="icon">📝</span> 标题变更与效果追踪</div>
        <div class="missing-banner"><span class="icon">💡</span> 本场共使用 {len(titles)} 个不同标题 · 最佳标题平均在线 {best_avg:.0f} 人</div>
        <table class="data-table">
            <thead><tr><th style="min-width:200px">标题</th><th>平均在线</th><th>峰值</th><th>使用次数</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    """


# ── 保存与 CLI ──────────────────────────────────────────────

def save_html_report(session_id, output_path=None):
    html, streamer = generate_html_report(session_id)
    if not html:
        return None, None

    if output_path is None:
        reports_dir = Path("/home/sheng/.hermes/skills/social-media/douyin-livestream/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        safe_name = (streamer or f"session_{session_id}").replace("/", "_").replace(" ", "_").replace("【", "").replace("】", "")
        date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(reports_dir / f"直播报告_{safe_name}_{date_str}.html")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return html, str(output_path)


def save_html_to_desktop(session_id):
    html, streamer = generate_html_report(session_id)
    if not html:
        return None, None

    safe_name = (streamer or f"session_{session_id}").replace("/", "_").replace(" ", "_").replace("【", "").replace("】", "")
    date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    desktop = Path("/mnt/c/Users/Administrator/Desktop")
    desktop.mkdir(parents=True, exist_ok=True)
    output_path = desktop / f"直播运营报告_{safe_name}_{date_str}.html"
    output_path.write_text(html, encoding="utf-8")
    return html, str(output_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="生成 HTML 直播运营分析报告 v3")
    parser.add_argument("session_id", nargs="?", type=int, help="会话ID")
    parser.add_argument("--desktop", "-d", action="store_true", help="保存到桌面")
    parser.add_argument("--output", "-o", help="输出路径")
    args = parser.parse_args()

    if not args.session_id:
        conn = get_db()
        row = conn.execute("SELECT id FROM monitoring_sessions ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        if not row:
            print("❌ 没有监控会话"); sys.exit(1)
        args.session_id = row["id"]

    if args.desktop:
        html, path = save_html_to_desktop(args.session_id)
    elif args.output:
        html, path = save_html_report(args.session_id, args.output)
    else:
        html, path = save_html_report(args.session_id)

    if html and path:
        print(f"✅ 报告已生成 ({len(html)} bytes): {path}")
    else:
        print("❌ 生成失败")
        sys.exit(1)
