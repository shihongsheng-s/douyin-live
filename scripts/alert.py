#!/usr/bin/env python3
"""
智能告警系统 — P2

监控直播间异常/里程碑事件，通过对话推送通知。

告警规则：
- 🔴 在线暴跌：连续2个快照下降超过 30%
- 🟢 峰值新高：在线超过历史所有记录的峰值
- 🟡 竞品开播：竞品标签的直播间开始直播
- 🔵 留存优异：留存率 > 80%
"""

import sys
import os
import json
import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from douyin_livestream import get_db, format_duration


def check_alerts(session_id=None, silent=False):
    """
    Run all alert checks for a session (or all running sessions).
    Returns list of alert dicts.
    """
    conn = get_db()

    if session_id:
        sessions = conn.execute(
            "SELECT * FROM monitoring_sessions WHERE id = ?", (session_id,)
        ).fetchall()
    else:
        sessions = conn.execute(
            "SELECT * FROM monitoring_sessions WHERE status = 'running'"
        ).fetchall()

    if not sessions:
        if not silent:
            print("📭 没有正在监控的直播间")
        conn.close()
        return []

    alerts = []

    for session in sessions:
        sid = session["id"]
        name = session["streamer_name"] or "?"
        tags = (session["tags"] or "").split(",")

        # Get latest 3 snapshots
        snaps = conn.execute(
            "SELECT * FROM snapshots WHERE session_id = ? AND error IS NULL "
            "AND user_count_num IS NOT NULL ORDER BY id DESC LIMIT 3",
            (sid,),
        ).fetchall()

        if len(snaps) < 2:
            continue  # Not enough data

        # ── Rule 1: 在线暴跌 ──────────────────────────────────
        counts = [s["user_count_num"] for s in snaps if s["user_count_num"] is not None]
        if len(counts) >= 2 and counts[0] > 0:
            drop_pct = (counts[0] - counts[1]) / counts[0] * 100
            if drop_pct > 30:
                already = conn.execute(
                    "SELECT id FROM alerts WHERE session_id=? AND alert_type='sharp_drop' "
                    "AND triggered_at > datetime('now','-30 minutes')",
                    (sid,),
                ).fetchone()
                if not already:
                    alerts.append({
                        "session_id": sid,
                        "alert_type": "sharp_drop",
                        "severity": "warning",
                        "message": f"🔴 **{name}** 在线人数骤降 {drop_pct:.0f}%（{counts[0]}→{counts[1]}人），建议检查直播间状态",
                    })

        # ── Rule 2: 峰值新高 ──────────────────────────────────
        current = counts[0] if counts else 0
        historical_peak = conn.execute(
            "SELECT MAX(user_count_num) FROM snapshots WHERE session_id=? AND id < ?",
            (sid, snaps[0]["id"]),
        ).fetchone()[0] or 0
        if current > 0 and current > historical_peak and historical_peak > 0:
            already = conn.execute(
                "SELECT id FROM alerts WHERE session_id=? AND alert_type='new_peak' "
                "AND triggered_at > datetime('now','-30 minutes')",
                (sid,),
            ).fetchone()
            if not already:
                alerts.append({
                    "session_id": sid,
                    "alert_type": "new_peak",
                    "severity": "info",
                    "message": f"🟢 **{name}** 在线人数创历史新高！当前 {current} 人（此前峰值 {historical_peak} 人）",
                })

        # ── Rule 3: 留存优异 ──────────────────────────────────
        if len(counts) >= 3:
            first = sum(counts[2:]) / max(len(counts[2:]), 1) if len(counts) >= 3 else counts[0]
            last = counts[0]
            if first > 0:
                retention = last / first * 100
                if retention > 80:
                    already = conn.execute(
                        "SELECT id FROM alerts WHERE session_id=? AND alert_type='great_retention' "
                        "AND triggered_at > datetime('now','-30 minutes')",
                        (sid,),
                    ).fetchone()
                    if not already:
                        alerts.append({
                            "session_id": sid,
                            "alert_type": "great_retention",
                            "severity": "info",
                            "message": f"🔵 **{name}** 留存率优异（{retention:.0f}%），观众粘性强，可以尝试推高客单价产品",
                        })

        # ── Rule 4: 竞品开播检测 ──────────────────────────────
        if "competitor" in tags:
            # Check if this competitor just started (first snapshot is recent)
            first_snap_time = conn.execute(
                "SELECT timestamp FROM snapshots WHERE session_id=? ORDER BY id LIMIT 1",
                (sid,),
            ).fetchone()
            if first_snap_time:
                try:
                    snap_dt = datetime.datetime.strptime(first_snap_time[0], "%Y-%m-%d %H:%M:%S")
                    now = datetime.datetime.now()
                    delta_min = (now - snap_dt).total_seconds() / 60
                    if delta_min < 10:  # Started within last 10 min
                        already = conn.execute(
                            "SELECT id FROM alerts WHERE session_id=? AND alert_type='competitor_live' "
                            "AND triggered_at > datetime('now','-30 minutes')",
                            (sid,),
                        ).fetchone()
                        if not already:
                            alerts.append({
                                "session_id": sid,
                                "alert_type": "competitor_live",
                                "severity": "warning",
                                "message": f"🟡 **竞品 {name}** 刚开播！建议跟进策略调整",
                            })
                except ValueError:
                    pass

        # Save alerts to DB
        for a in alerts:
            conn.execute(
                "INSERT INTO alerts (session_id, alert_type, message, severity) VALUES (?, ?, ?, ?)",
                (a["session_id"], a["alert_type"], a["message"], a["severity"]),
            )

    conn.commit()
    conn.close()
    return alerts


def list_alerts(session_id=None, limit=10):
    """List recent alerts."""
    conn = get_db()

    if session_id:
        rows = conn.execute(
            "SELECT a.*, ms.streamer_name FROM alerts a "
            "JOIN monitoring_sessions ms ON a.session_id = ms.id "
            "WHERE a.session_id = ? ORDER BY a.id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT a.*, ms.streamer_name FROM alerts a "
            "JOIN monitoring_sessions ms ON a.session_id = ms.id "
            "WHERE a.acknowledged = 0 ORDER BY a.id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    conn.close()

    if not rows:
        print("📭 暂无告警记录")
        return []

    print(f"{'ID':>4}  {'直播间':<16} {'类型':<14} {'严重程度':<8} {'时间':<20}")
    print("─" * 70)
    for r in rows:
        icon = "🟢" if r["severity"] == "info" else "🟡" if r["severity"] == "warning" else "🔴"
        print(f"{r['id']:>4}  {r['streamer_name']:<16} {r['alert_type']:<14} {icon:<8} {r['triggered_at']}")

    return rows


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="智能告警系统")
    parser.add_argument("action", nargs="?", default="check", choices=["check", "list"])
    parser.add_argument("--session", "-s", type=int, help="指定会话ID")
    args = parser.parse_args()

    if args.action == "check":
        alerts = check_alerts(args.session)
        if alerts:
            print(f"\n🚨 {len(alerts)} 条新告警:\n")
            for a in alerts:
                sev_icon = "🟢" if a["severity"] == "info" else "🟡" if a["severity"] == "warning" else "🔴"
                print(f"  {sev_icon} {a['message']}")
        else:
            print("\n✅ 无新告警")
    elif args.action == "list":
        list_alerts(args.session)
