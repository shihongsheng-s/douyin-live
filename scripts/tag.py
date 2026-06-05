#!/usr/bin/env python3
"""
内容标注系统 — P1

在直播过程中或结束后，快速标记直播间发生的关键事件。
系统自动关联当时在线人数，分析"什么动作最有效"。
"""

import sys
import json
import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from douyin_livestream import get_db, format_duration


def get_running_session(streamer_name=None):
    """Get the current running session, optionally filtered by name."""
    conn = get_db()
    if streamer_name:
        row = conn.execute(
            "SELECT id, streamer_name FROM monitoring_sessions WHERE status='running' AND streamer_name LIKE ? ORDER BY id DESC LIMIT 1",
            (f"%{streamer_name}%",),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id, streamer_name FROM monitoring_sessions WHERE status='running' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    conn.close()
    return row


def add_event(session_id, content, event_type="note"):
    """
    Add an event marker. Automatically captures the latest online count.
    """
    conn = get_db()

    # Get latest online count
    snap = conn.execute(
        "SELECT user_count_num, user_count_str FROM snapshots "
        "WHERE session_id=? AND error IS NULL AND user_count_num IS NOT NULL "
        "ORDER BY id DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    online = snap["user_count_num"] if snap else 0
    online_str = snap["user_count_str"] if snap else "?"

    # Get previous online to calculate change
    prev = conn.execute(
        "SELECT user_count_num FROM snapshots "
        "WHERE session_id=? AND error IS NULL AND user_count_num IS NOT NULL "
        "ORDER BY id DESC LIMIT 1 OFFSET 1",
        (session_id,),
    ).fetchone()
    change = online - prev["user_count_num"] if prev and online and prev["user_count_num"] else 0
    change_str = f"+{change}" if change > 0 else str(change) if change < 0 else "→"

    conn.execute(
        "INSERT INTO stream_events (session_id, content, event_type, online_at_event, online_change) VALUES (?, ?, ?, ?, ?)",
        (session_id, content, event_type, online, change),
    )
    conn.commit()

    # Get event id
    eid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()

    return eid, online_str, change_str


def list_events(session_id=None, limit=20):
    """List events for a session."""
    conn = get_db()

    if session_id:
        rows = conn.execute(
            "SELECT e.*, ms.streamer_name FROM stream_events e "
            "JOIN monitoring_sessions ms ON e.session_id = ms.id "
            "WHERE e.session_id = ? ORDER BY e.id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT e.*, ms.streamer_name FROM stream_events e "
            "JOIN monitoring_sessions ms ON e.session_id = ms.id "
            "WHERE ms.status IN ('running', 'completed') "
            "ORDER BY e.id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    conn.close()

    if not rows:
        print("📭 暂无事件记录")
        return []

    print(f"{'ID':>4}  {'直播间':<14} {'时间':<20} {'在线':<6} {'变化':<6} {'内容'}")
    print("─" * 100)
    for r in rows:
        arrow = "📈" if r["online_change"] > 0 else "📉" if r["online_change"] < 0 else "➡️"
        print(f"{r['id']:>4}  {r['streamer_name']:<14} {r['timestamp']:<20} {r['online_at_event']:<6} {arrow} {r['content']}")

    return rows


def analyze_events(session_id):
    """
    Analyze events for a session: which actions drove the most viewers.
    Returns structured data.
    """
    conn = get_db()
    events = conn.execute(
        "SELECT * FROM stream_events WHERE session_id=? ORDER BY id",
        (session_id,),
    ).fetchall()
    conn.close()

    if not events:
        return {"best": [], "worst": [], "count": 0}

    by_change = sorted(events, key=lambda e: -(e["online_change"] or 0))
    positive = [e for e in by_change if e["online_change"] and e["online_change"] > 0]
    negative = [e for e in by_change if e["online_change"] and e["online_change"] < 0]

    return {
        "count": len(events),
        "best": [{"content": e["content"], "change": e["online_change"], "online": e["online_at_event"], "time": e["timestamp"]} for e in positive[:5]],
        "worst": [{"content": e["content"], "change": e["online_change"], "online": e["online_at_event"], "time": e["timestamp"]} for e in negative[:5]],
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="内容标注系统 P1")
    sub = parser.add_subparsers(dest="action", help="add / list / analyze")

    # add
    p_add = sub.add_parser("add", help="添加事件标记")
    p_add.add_argument("--session", "-s", type=int, help="会话ID（缺省用最新的）")
    p_add.add_argument("--name", "-n", help="主播名（模糊匹配）")
    p_add.add_argument("content", help="事件描述")

    # list
    p_list = sub.add_parser("list", help="列出事件")
    p_list.add_argument("--session", "-s", type=int, help="会话ID")

    # analyze
    p_ana = sub.add_parser("analyze", help="分析事件效果")
    p_ana.add_argument("--session", "-s", type=int, help="会话ID（缺省用最新的）")

    args = parser.parse_args()

    if args.action == "add":
        session = None
        if args.session:
            session = {"id": args.session}
        elif args.name:
            session = get_running_session(args.name)
        else:
            session = get_running_session()

        if not session:
            print("❌ 找不到正在监控的直播间")
            sys.exit(1)

        eid, online, change = add_event(session["id"], args.content)
        print(f"✅ 已标记 [{session['streamer_name']}] {args.content}")
        print(f"   当前在线: {online} 人 | 变化: {change}")
        print(f"   事件ID: {eid}")

    elif args.action == "list":
        list_events(args.session)

    elif args.action == "analyze":
        sid = args.session
        if not sid:
            s = get_running_session()
            sid = s["id"] if s else None
        if not sid:
            print("❌ 找不到会话")
            sys.exit(1)

        result = analyze_events(sid)
        if result["count"] == 0:
            print(f"📭 没有事件记录")
            sys.exit(0)

        print(f"\n📊 共 {result['count']} 个事件标记\n")
        print("🥇 拉在线效果最好的动作:")
        for e in result.get("best", []):
            print(f"  📈 +{e['change']}人  → {e['content']} (在线{e['online']}人 @ {e['time']})")
        print()
        print("😢 掉在线最多的动作:")
        for e in result.get("worst", []):
            print(f"  📉 {e['change']}人  → {e['content']} (在线{e['online']}人 @ {e['time']})")
