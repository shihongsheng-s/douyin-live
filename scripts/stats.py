#!/usr/bin/env python3
"""
跨场次统计分析 — P1

分析所有已完成直播场次的数据规律，输出运营策略建议。

功能：
- 最佳开播时段分析
- 最佳直播时长分析
- 标题模式分析
- 在线趋势规律
- 跨场次对比表
"""

import sys
import os
import json
import math
import datetime
from pathlib import Path
from collections import defaultdict

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from douyin_livestream import get_db, format_duration


def analyze_all():
    """Run full cross-session analysis and return dict of insights."""
    conn = get_db()

    # Get all completed + cancelled sessions with at least 2 snapshots
    sessions = conn.execute("""
        SELECT ms.*,
               (SELECT COUNT(*) FROM snapshots WHERE session_id = ms.id) as snap_count,
               (SELECT MIN(user_count_num) FROM snapshots WHERE session_id = ms.id AND user_count_num IS NOT NULL) as min_viewers,
               (SELECT MAX(user_count_num) FROM snapshots WHERE session_id = ms.id AND user_count_num IS NOT NULL) as max_viewers,
               (SELECT AVG(user_count_num) FROM snapshots WHERE session_id = ms.id AND user_count_num IS NOT NULL) as avg_viewers
        FROM monitoring_sessions ms
        WHERE ms.status IN ('completed', 'cancelled')
        AND (SELECT COUNT(*) FROM snapshots WHERE session_id = ms.id AND user_count_num IS NOT NULL) >= 2
        ORDER BY ms.id
    """).fetchall()

    if not sessions:
        conn.close()
        return {"error": "没有足够的已完成场次数据（至少需要2个有效快照）"}

    insights = {
        "total_sessions": len(sessions),
        "sessions": [],
        "peak_hours": defaultdict(list),
        "weekday_performance": defaultdict(list),
        "duration_buckets": defaultdict(list),
        "best_practices": [],
        "recommendations": [],
    }

    for s in sessions:
        sid = s["id"]
        name = s["streamer_name"] or "?"
        snap_count = s["snap_count"] or 0
        peak = s["max_viewers"] or 0
        avg_v = int(s["avg_viewers"]) if s["avg_viewers"] else 0
        low = s["min_viewers"] or 0
        retention = round(avg_v / peak * 100, 1) if peak > 0 else 0

        # Duration
        duration_sec = 0
        start_str = s["start_time"]
        end_str = s["end_time"]
        try:
            st = datetime.datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
            et = datetime.datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S") if end_str else datetime.datetime.now()
            duration_sec = (et - st).total_seconds()
            hour = st.hour
            weekday = st.weekday()
            insights["peak_hours"][hour].append(peak)
            insights["weekday_performance"][weekday].append({
                "peak": peak, "avg": avg_v, "duration": duration_sec, "retention": retention
            })
        except (ValueError, TypeError):
            hour = -1
            weekday = -1

        # Duration bucketing
        if duration_sec > 0:
            bucket = "short" if duration_sec < 1800 else "medium" if duration_sec < 7200 else "long"
            insights["duration_buckets"][bucket].append({
                "peak": peak, "avg": avg_v, "retention": retention, "duration": duration_sec
            })

        # Trend detection
        snaps = conn.execute(
            "SELECT user_count_num, timestamp FROM snapshots "
            "WHERE session_id=? AND user_count_num IS NOT NULL ORDER BY id",
            (sid,),
        ).fetchall()
        values = [s["user_count_num"] for s in snaps if s["user_count_num"] is not None]
        trend = "up" if len(values) >= 2 and values[-1] > values[0] else "down" if len(values) >= 2 and values[-1] < values[0] else "flat"

        insights["sessions"].append({
            "id": sid,
            "name": name,
            "peak": peak,
            "avg": avg_v,
            "low": low,
            "retention": retention,
            "duration_sec": duration_sec,
            "duration_str": format_duration(duration_sec),
            "hour": hour,
            "weekday": weekday,
            "trend": trend,
            "snap_count": snap_count,
            "time": start_str[:16] if start_str else "?",
        })

    conn.close()

    # ── Generate Best Practices ───────────────────────────────

    # Best hour
    if insights["peak_hours"]:
        best_hour = max(insights["peak_hours"], key=lambda h: sum(insights["peak_hours"][h]) / len(insights["peak_hours"][h]) if insights["peak_hours"][h] else 0)
        avg_peak_best = sum(insights["peak_hours"][best_hour]) / len(insights["peak_hours"][best_hour]) if insights["peak_hours"][best_hour] else 0
        insights["best_practices"].append(f"⏰ **最佳开播时段**: {best_hour}:00 左右（平均峰值 {avg_peak_best:.0f} 人）")

    # Best weekday (Chinese weekday names)
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    if insights["weekday_performance"]:
        best_wd = max(insights["weekday_performance"], key=lambda w: sum(d["peak"] for d in insights["weekday_performance"][w]) / len(insights["weekday_performance"][w]) if insights["weekday_performance"][w] else 0)
        avg_peak_wd = sum(d["peak"] for d in insights["weekday_performance"][best_wd]) / len(insights["weekday_performance"][best_wd]) if insights["weekday_performance"][best_wd] else 0
        insights["best_practices"].append(f"📅 **最佳直播日**: {weekday_names[best_wd]}（平均峰值 {avg_peak_wd:.0f} 人）")

    # Best duration
    for bucket, label in [("long", "长直播(>2h)"), ("medium", "中直播(1-2h)"), ("short", "短直播(<30min)")]:
        items = insights["duration_buckets"].get(bucket, [])
        if items:
            avg_p = sum(d["peak"] for d in items) / len(items)
            avg_r = sum(d["retention"] for d in items) / len(items)
            insights["best_practices"].append(f"⏱ **{label}**: 场均峰值 {avg_p:.0f} 人，留存率 {avg_r:.1f}%")

    # Best duration comparison
    if len(insights["duration_buckets"]) >= 2:
        best_bucket = max(insights["duration_buckets"], key=lambda b: sum(d["peak"] for d in insights["duration_buckets"][b]) / len(insights["duration_buckets"][b]) if insights["duration_buckets"][b] else 0)
        bucket_labels = {"short": "短直播(<30min)", "medium": "中直播(1-2h)", "long": "长直播(>2h)"}
        insights["best_practices"].append(f"🏆 **推荐直播时长**: {bucket_labels.get(best_bucket, best_bucket)}（该时长段表现最佳）")

    # ── Generate Recommendations ──────────────────────────────

    if insights["sessions"]:
        avg_all_peak = sum(s["peak"] for s in insights["sessions"]) / len(insights["sessions"])
        avg_all_ret = sum(s["retention"] for s in insights["sessions"]) / len(insights["sessions"])
        insights["recommendations"].append(f"📊 **场均数据**: 峰值 {avg_all_peak:.0f} 人，留存率 {avg_all_ret:.1f}%")

        up_count = sum(1 for s in insights["sessions"] if s["trend"] == "up")
        down_count = sum(1 for s in insights["sessions"] if s["trend"] == "down")
        total_trend = len([s for s in insights["sessions"] if s["trend"] in ("up", "down")])
        if total_trend > 0:
            insights["recommendations"].append(f"📈 **趋势统计**: {up_count}/{total_trend} 场在线呈上升趋势，{down_count}/{total_trend} 场呈下降趋势")

        # Retention insight
        high_ret = sum(1 for s in insights["sessions"] if s["retention"] >= 70)
        low_ret = sum(1 for s in insights["sessions"] if s["retention"] < 50)
        if high_ret > 0:
            insights["recommendations"].append(f"💪 **高留存率场次**: {high_ret} 场（留存率≥70%），建议复盘这些场次的内容策略")
        if low_ret > 0:
            insights["recommendations"].append(f"⚠️ **低留存率场次**: {low_ret} 场（留存率<50%），需要重点关注开场和互动环节")

    return insights


def format_insights(insights, format="text"):
    """Format insights for display."""
    if "error" in insights:
        return insights["error"]

    lines = []
    lines.append("📊 **跨场次运营分析报告**")
    lines.append(f"分析场次: {insights['total_sessions']} 场直播\n")

    # Best Practices
    lines.append("### ✅ 数据发现\n")
    for bp in insights.get("best_practices", []):
        lines.append(f"- {bp}")

    if not insights.get("best_practices"):
        lines.append("（数据不足以生成建议，建议积累更多场次）")

    lines.append("")
    lines.append("### 💡 优化建议\n")
    for rec in insights.get("recommendations", []):
        lines.append(f"- {rec}")

    if not insights.get("recommendations"):
        lines.append("（数据不足以生成建议）")

    # Session table
    lines.append("")
    lines.append("### 📋 各场次数据对比\n")
    lines.append(f"{'ID':>4}  {'主播':<14} {'峰值':<8} {'平均':<8} {'留存':<8} {'时长':<14} {'趋势':<6} {'时段'}")
    lines.append("─" * 80)
    for s in insights["sessions"]:
        trend_icon = "📈" if s["trend"] == "up" else "📉" if s["trend"] == "down" else "➡️"
        hour_str = f"{s['hour']}:00" if s["hour"] >= 0 else "?"
        lines.append(f"{s['id']:>4}  {s['name']:<14} {s['peak']:<8} {s['avg']:<8} {s['retention']:<7.1f}% {s['duration_str']:<14} {trend_icon:<6} {hour_str}")

    return "\n".join(lines)


def show_stats():
    """CLI entry point."""
    insights = analyze_all()
    output = format_insights(insights)
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(show_stats())
