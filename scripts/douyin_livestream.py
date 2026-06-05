#!/usr/bin/env python3
"""
Douyin Livestream — CLI Entry Point

Usage:
    hermes skill run douyin-livestream monitor <room_id> [--interval SECONDS]
    hermes skill run douyin-livestream list
    hermes skill run douyin-livestream report <room_id_or_session_id>

Subcommands:
    monitor     Start monitoring a douyin livestream
    list        List all monitoring sessions
    report      Generate a Markdown report for a completed session
"""

import sys
import os
import time
import json
import sqlite3
import argparse
import datetime
from pathlib import Path

# Add scripts dir to path for imports
SCRIPTS_DIR = Path(__file__).parent
SKILL_DIR = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from extract import (
    fetch_page,
    extract_snapshot,
    parse_user_count,
    status_name,
    MAX_RETRIES,
)

# ── Paths ─────────────────────────────────────────────────────

DATA_DIR = SKILL_DIR / "data"
DB_PATH = DATA_DIR / "monitoring.db"
CONFIG_PATH = SKILL_DIR / "config.yaml"
REPORT_DIR = SKILL_DIR / "reports"

# ── Default Config ────────────────────────────────────────────

DEFAULT_CONFIG = {
    "interval": 300,           # polling interval in seconds
    "report_path": str(REPORT_DIR),
    "save_reports_to_skill_dir": True,
    "max_retries": MAX_RETRIES,
}


def load_config():
    """Load config from config.yaml, falling back to defaults."""
    try:
        import yaml
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                cfg = yaml.safe_load(f) or {}
                return {**DEFAULT_CONFIG, **cfg}
    except Exception:
        pass
    return dict(DEFAULT_CONFIG)


# ── Database ──────────────────────────────────────────────────

def get_db():
    """Get a SQLite connection, creating tables if needed."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_db(conn)
    return conn


def _init_db(conn):
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS monitoring_sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            room_url        TEXT NOT NULL,
            room_id         TEXT,
            streamer_uid    TEXT,
            streamer_name   TEXT,
            game_category   TEXT,
            location        TEXT,
            start_time      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            end_time        TEXT,
            status          TEXT NOT NULL DEFAULT 'running'
                CHECK(status IN ('running', 'completed', 'error', 'cancelled')),
            note            TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER NOT NULL REFERENCES monitoring_sessions(id),
            timestamp       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            status_code     INTEGER,
            status_text     TEXT,
            title           TEXT,
            user_count_str  TEXT,
            user_count_num  INTEGER,
            nickname        TEXT,
            game_category   TEXT,
            raw_json        TEXT,
            fetch_duration_ms INTEGER,
            error           TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_session
            ON snapshots(session_id, timestamp);

        CREATE INDEX IF NOT EXISTS idx_sessions_status
            ON monitoring_sessions(status);

        CREATE TABLE IF NOT EXISTS skill_config (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()


# ── Monitoring ────────────────────────────────────────────────

def cmd_monitor(args):
    """
    Monitor a douyin livestream until it ends.

    Polls the room page every `interval` seconds, records snapshots
    to SQLite, and auto-generates a report when the stream ends.
    """
    room_id = args.room_id
    interval = args.interval

    print(f"🎯 开始监控抖音直播间: https://live.douyin.com/{room_id}")
    print(f"⏱  抓取间隔: {interval}s")
    print(f"📁 数据存储: {DB_PATH}")
    print("─" * 55)

    # Initial fetch to validate and get streamer info
    html = fetch_page(room_id)
    if html is None:
        print("❌ 无法获取直播间页面，所有重试均已耗尽")
        return 1

    snapshot = extract_snapshot(html)
    if not snapshot["success"]:
        print(f"❌ 数据提取失败: {snapshot['error']}")
        return 1

    if snapshot["status"] != 2:
        print(f"⏹  直播间当前状态: {snapshot.get('status_text', '未知')}，非直播中")
        print("   请确认直播间正在直播后再试")
        return 1

    # Create session in DB
    conn = get_db()
    try:
        cursor = conn.execute(
            """INSERT INTO monitoring_sessions
               (room_url, room_id, streamer_uid, streamer_name,
                game_category, location, start_time)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now','localtime'))""",
            (
                f"https://live.douyin.com/{room_id}",
                snapshot.get("room_id"),
                snapshot.get("streamer_uid"),
                snapshot.get("nickname"),
                snapshot.get("game_category"),
                snapshot.get("location"),
            ),
        )
        session_id = cursor.lastrowid
        conn.commit()
    except Exception as e:
        print(f"❌ 数据库写入失败: {e}")
        conn.close()
        return 1

    print(f"\n📺 直播间: {snapshot.get('title', 'N/A')}")
    print(f"👤 主播:   {snapshot.get('nickname', 'N/A')}")
    if snapshot.get("streamer_uid"):
        print(f"🆔 UID:    {snapshot['streamer_uid']}")
    if snapshot.get("game_category"):
        print(f"🎮 分类:   {snapshot['game_category']}")
    if snapshot.get("location"):
        print(f"📍 位置:   {snapshot['location']}")
    print(f"👥 当前在线: {snapshot.get('user_count_str', '未知')}")
    print(f"📋 会话ID:  {session_id}")
    print("─" * 55)

    # ── Monitoring Loop ───────────────────────────────────────
    last_status = 2
    consecutive_errors = 0
    snapshot_count = 0

    try:
        while True:
            tick_start = time.time()

            # Fetch
            fetch_start = time.time()
            html = fetch_page(room_id)
            fetch_duration = int((time.time() - fetch_start) * 1000)

            if html is None:
                consecutive_errors += 1
                print(f"⚠️  抓取失败 ({consecutive_errors}/{MAX_RETRIES})")
                _save_snapshot_error(conn, session_id,
                                     "Fetch failed after retries", fetch_duration)
                if consecutive_errors >= 3:
                    print("❌ 连续失败3次，终止监控")
                    conn.execute(
                        "UPDATE monitoring_sessions SET status='error', "
                        "end_time=datetime('now','localtime') WHERE id=?",
                        (session_id,),
                    )
                    conn.commit()
                conn.close()
                return 1

            consecutive_errors = 0
            snapshot_data = extract_snapshot(html)
            snapshot_count += 1

            # Store snapshot
            user_count_num = parse_user_count(
                snapshot_data.get("user_count_str")
            )
            now_str = datetime.datetime.now().strftime("%H:%M:%S")

            conn.execute(
                """INSERT INTO snapshots
                   (session_id, status_code, status_text, title,
                    user_count_str, user_count_num, nickname,
                    game_category, raw_json, fetch_duration_ms, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    snapshot_data.get("status"),
                    snapshot_data.get("status_text"),
                    snapshot_data.get("title"),
                    snapshot_data.get("user_count_str"),
                    user_count_num,
                    snapshot_data.get("nickname"),
                    snapshot_data.get("game_category"),
                    json.dumps(snapshot_data, ensure_ascii=False),
                    fetch_duration,
                    snapshot_data.get("error"),
                ),
            )
            conn.commit()

            # Display status
            current_status = snapshot_data.get("status")
            if current_status != last_status:
                print(f"\n{'─' * 55}")
                if current_status != 2:
                    print(f"🔴 直播状态变更: {snapshot_data.get('status_text', '未知')}")
                else:
                    print(f"🟢 直播状态恢复: 直播中")
                print(f"{'─' * 55}")

            count_display = snapshot_data.get("user_count_str", "?")
            status_display = "🟢" if current_status == 2 else "🔴"
            ts = datetime.datetime.now().strftime("%m-%d %H:%M:%S")
            print(f"  [{ts}] {status_display} 在线:{count_display:>8}  "
                  f"({fetch_duration}ms) [#{snapshot_count}]")

            # Check if stream ended
            if current_status != 2:
                print(f"\n{'=' * 55}")
                print(f"📌 直播已结束 ({snapshot_data.get('status_text', '未知')})")
                print(f"{'=' * 55}")
                conn.execute(
                    "UPDATE monitoring_sessions SET status='completed', "
                    "end_time=datetime('now','localtime') WHERE id=?",
                    (session_id,),
                )
                conn.commit()
                conn.close()

                # Generate report
                report_path = generate_report(session_id)
                if report_path:
                    print(f"\n📊 运营报告已生成: {report_path}")
                print(f"📋 共采集 {snapshot_count} 个数据点")
                return 0

            last_status = current_status

            # Wait for next interval
            elapsed = time.time() - tick_start
            sleep_time = max(1, interval - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print(f"\n\n⏹  用户中断监控")
        conn.execute(
            "UPDATE monitoring_sessions SET status='cancelled', "
            "end_time=datetime('now','localtime') WHERE id=?",
            (session_id,),
        )
        conn.commit()
        conn.close()
        print(f"📋 共采集 {snapshot_count} 个数据点")
        return 0


def _save_snapshot_error(conn, session_id, error_msg, duration_ms):
    """Record a failed snapshot in the database."""
    conn.execute(
        """INSERT INTO snapshots
           (session_id, status_code, status_text, title,
            user_count_str, user_count_num, nickname,
            game_category, raw_json, fetch_duration_ms, error)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, None, "error", None,
         None, None, None,
         None, None, duration_ms, error_msg),
    )
    conn.commit()


# ── List Sessions ─────────────────────────────────────────────

def cmd_list(args):
    """List currently active monitoring sessions."""
    conn = get_db()
    rows = conn.execute(
        """SELECT id, streamer_name, room_url, start_time, end_time, status,
                  (SELECT COUNT(*) FROM snapshots WHERE session_id = ms.id) as snap_count,
                  (SELECT MAX(user_count_num) FROM snapshots WHERE session_id = ms.id) as peak_viewers,
                  (SELECT user_count_str FROM snapshots WHERE session_id = ms.id AND error IS NULL ORDER BY id DESC LIMIT 1) as last_online
           FROM monitoring_sessions ms
           WHERE ms.status = 'running'
           ORDER BY id DESC
           LIMIT 50"""
    ).fetchall()
    conn.close()

    if not rows:
        print("📭 当前没有正在监控的直播间")
        return 0

    print(f"{'ID':>4}  {'主播':<14} {'在线':<8} {'数据点':<6} {'峰值':<8} {'开始时间':<20}")
    print("─" * 70)
    for r in rows:
        sid = r["id"]
        name = (r["streamer_name"] or "?")[:14]
        online = r["last_online"] or "?"
        snaps = r["snap_count"] or 0
        peak = f"{r['peak_viewers'] or '?'}"
        start = (r["start_time"] or "")[:19]
        print(f"{sid:>4}  🟢 {name:<14} {online:<8} {snaps:<6} {peak:<8} {start:<20}")

    return 0


# ── Report Generation ─────────────────────────────────────────

def generate_report(session_id, output_path=None):
    """
    Generate a Markdown report for a completed monitoring session.

    Args:
        session_id: The session ID from the database
        output_path: Optional output file path (default: auto-generated)

    Returns:
        Path to the generated report, or None on failure
    """
    conn = get_db()

    # Get session info
    session = conn.execute(
        "SELECT * FROM monitoring_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if not session:
        print(f"❌ 会话 #{session_id} 不存在")
        conn.close()
        return None

    # Get all snapshots
    snapshots = conn.execute(
        "SELECT * FROM snapshots WHERE session_id = ? "
        "AND error IS NULL ORDER BY timestamp",
        (session_id,),
    ).fetchall()
    conn.close()

    if not snapshots:
        print(f"❌ 会话 #{session_id} 没有数据点")
        return None

    # ── Compute Statistics ────────────────────────────────────

    user_counts = []
    first_snap = snapshots[0]
    last_snap = snapshots[-1]
    start_time = first_snap["timestamp"]
    end_time = last_snap["timestamp"]

    # Parse start/end times
    try:
        st = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        et = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        duration_seconds = (et - st).total_seconds()
        duration_str = format_duration(duration_seconds)
    except ValueError:
        st = et = None
        duration_seconds = 0
        duration_str = "N/A"

    # Collect numeric user counts
    for snap in snapshots:
        num = snap["user_count_num"]
        if num is not None:
            user_counts.append(num)

    peak_viewers = max(user_counts) if user_counts else 0
    avg_viewers = int(sum(user_counts) / len(user_counts)) if user_counts else 0
    min_viewers = min(user_counts) if user_counts else 0
    snapshot_count = len(snapshots)

    # Build time series for trend chart
    times = []
    values = []
    for snap in snapshots:
        ts_str = snap["timestamp"]
        try:
            dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            if st:
                offset_min = int((dt - st).total_seconds() / 60)
            else:
                offset_min = 0
        except ValueError:
            offset_min = 0

        num = snap["user_count_num"] if snap["user_count_num"] is not None else 0
        times.append(offset_min)
        values.append(num)

    # Generate simple ASCII trend chart
    trend_chart = generate_trend_chart(times, values, width=50, height=12)

    # ── Build Report ──────────────────────────────────────────

    streamer = session["streamer_name"] or "未知"
    room_url = session["room_url"] or "N/A"

    report_lines = []
    report_lines.append(f"# 📊 抖音直播间运营报告\n")
    report_lines.append(f"**生成时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report_lines.append(f"---\n")

    report_lines.append("## 📋 直播间概览\n")
    report_lines.append(f"| 维度 | 数据 |")
    report_lines.append(f"|------|------|")
    report_lines.append(f"| **主播** | {streamer} |")
    if session["streamer_uid"]:
        report_lines.append(f"| **主播UID** | `{session['streamer_uid']}` |")
    report_lines.append(f"| **直播间链接** | [{room_url}]({room_url}) |")
    if session["game_category"]:
        report_lines.append(f"| **直播分类** | {session['game_category']} |")
    if session["location"]:
        report_lines.append(f"| **地理位置** | {session['location']} |")
    if session["room_id"]:
        report_lines.append(f"| **内部RoomID** | `{session['room_id']}` |")
    report_lines.append("")

    report_lines.append("## ⏱ 直播时间统计\n")
    report_lines.append(f"| 指标 | 数值 |")
    report_lines.append(f"|------|------|")
    report_lines.append(f"| **开始时间** | {start_time} |")
    report_lines.append(f"| **结束时间** | {end_time} |")
    report_lines.append(f"| **直播时长** | {duration_str} |")
    report_lines.append(f"| **采集数据点** | {snapshot_count} |")
    report_lines.append("")

    report_lines.append("## 👥 在线人数分析\n")
    report_lines.append(f"| 指标 | 数值 |")
    report_lines.append(f"|------|------|")
    report_lines.append(f"| **峰值在线** | {peak_viewers} 人 |")
    report_lines.append(f"| **平均在线** | {avg_viewers} 人 |")
    report_lines.append(f"| **最低在线** | {min_viewers} 人 |")
    if peak_viewers > 0 and avg_viewers > 0:
        retention_rate = round(avg_viewers / peak_viewers * 100, 1)
        report_lines.append(f"| **留存率(均/峰)** | {retention_rate}% |")
    report_lines.append("")

    if trend_chart:
        report_lines.append("## 📈 在线人数趋势图\n")
        report_lines.append("```text")
        report_lines.append(trend_chart)
        report_lines.append("```")
        report_lines.append("")

    report_lines.append("## 📊 详细数据时间线\n")
    report_lines.append("| 时间 | 在线人数 | 状态 | 直播间标题 |")
    report_lines.append("|------|---------|------|-----------|")
    for snap in snapshots:
        ts = snap["timestamp"]
        uc = snap["user_count_str"] or "?"
        st = snap["status_text"] or "?"
        title = (snap["title"] or "")[:30]
        report_lines.append(f"| {ts} | {uc} | {st} | {title} |")
    report_lines.append("")

    # ── Optimization Suggestions ──────────────────────────────

    report_lines.append("## 💡 运营优化建议\n")

    suggestions = generate_suggestions(
        session, snapshots, peak_viewers, avg_viewers, duration_seconds
    )
    if suggestions:
        for s in suggestions:
            report_lines.append(f"- {s}")
    else:
        report_lines.append("- 数据量不足以生成针对性建议，建议增加监控时长获取更多数据。")
    report_lines.append("")

    report_lines.append("---\n")
    report_lines.append(f"*报告由 Hermes Douyin Livestream Monitor 自动生成*\n")

    report_content = "\n".join(report_lines)

    # ── Save Report ───────────────────────────────────────────

    if output_path is None:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = streamer.replace("/", "_").replace(" ", "_")
        date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = REPORT_DIR / f"直播报告_{safe_name}_{date_str}.md"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_content, encoding="utf-8")
    return str(output_path)


def format_duration(seconds):
    """Format seconds into human-readable duration."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    parts = []
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}分钟")
    parts.append(f"{secs}秒")
    return "".join(parts)


def generate_trend_chart(times, values, width=50, height=12):
    """
    Generate a simple vertical ASCII bar chart for time-series data.

    Returns a string suitable for a code block.
    """
    if not values or max(values) == 0:
        return None

    min_val = min(values)
    max_val = max(values)
    val_range = max_val - min_val or 1

    lines = []
    y_label_width = len(str(max_val)) + 1

    for row in range(height - 1, -1, -1):
        threshold = min_val + (val_range * row / (height - 1)) if height > 1 else max_val
        label = f"{int(threshold):>{y_label_width}} |"
        bar = ""
        for v in values:
            if v >= threshold:
                bar += "█"
            elif v >= threshold * 0.7:
                bar += "▄"
            else:
                bar += " "
        lines.append(f"{label}{bar}")

    # X-axis
    x_axis = " " * (y_label_width + 1) + "─" * len(values)
    lines.append(x_axis)

    # X-axis labels (show start, middle, end times in minutes)
    if len(times) >= 3:
        time_label = " " * (y_label_width + 1)
        first = f"{times[0]}m"
        mid = f"{times[len(times)//2]}m"
        last = f"{times[-1]}m"
        spacing = len(values) - len(first) - len(mid) - len(last)
        spacing = max(0, spacing // 2)
        time_label += first + " " * spacing + mid + " " * spacing + last
        lines.append(time_label)
    elif len(times) >= 1:
        time_label = " " * (y_label_width + 1)
        for t in times[::max(1, len(times)//5)]:
            time_label += f"{t}m "
        lines.append(time_label)

    return "\n".join(lines)


def generate_suggestions(session, snapshots, peak_viewers, avg_viewers, duration_seconds):
    """
    Generate data-driven optimization suggestions.

    Returns a list of suggestion strings.
    """
    suggestions = []

    # 1. Duration analysis
    if duration_seconds > 0:
        if duration_seconds < 1800:  # < 30 min
            suggestions.append("⏱ **直播时长偏短**：仅 {}，建议延长至1-2小时以获得更多观众沉淀。".format(
                format_duration(duration_seconds)
            ))
        elif duration_seconds > 14400:  # > 4 hours
            suggestions.append("⏱ **直播时长较长**（{}），注意主播疲劳度，建议中间安排休息环节。".format(
                format_duration(duration_seconds)
            ))

    # 2. Viewer engagement
    live_snapshots = [s for s in snapshots if s["status_code"] == 2]
    if len(live_snapshots) >= 3:
        first_third = live_snapshots[:len(live_snapshots)//3]
        last_third = live_snapshots[-len(live_snapshots)//3:]

        first_avg = 0
        last_avg = 0
        first_count = 0
        last_count = 0
        for s in first_third:
            if s["user_count_num"]:
                first_avg += s["user_count_num"]
                first_count += 1
        for s in last_third:
            if s["user_count_num"]:
                last_avg += s["user_count_num"]
                last_count += 1

        if first_count > 0 and last_count > 0:
            first_avg /= first_count
            last_avg /= last_count
            if first_avg > 0:
                retention = last_avg / first_avg * 100
                if retention < 50:
                    suggestions.append(
                        f"📉 **观众流失严重**：后期在线仅为前期的 {retention:.0f}%，"
                        f"建议检查内容节奏和后段是否有足够的互动/福利环节。"
                    )
                elif retention > 120:
                    suggestions.append(
                        f"📈 **观众持续增长**：后期在线较前期增长 {retention-100:.0f}%，"
                        f"说明内容吸引力在持续增强，建议总结该时段的内容策略复用。"
                    )

    # 3. Peak analysis
    if peak_viewers > 0 and peak_viewers == avg_viewers and peak_viewers > 100:
        suggestions.append("📊 **在线人数稳定**：峰值与均值接近，直播表现稳定，可以考虑增加推广引流突破在线天花板。")

    # 4. Data quality
    data_errors = sum(1 for s in snapshots if s["error"] is not None)
    total = len(snapshots)
    if total > 0 and data_errors / total > 0.3:
        suggestions.append("⚠️ **数据采集成功率偏低**（{:.0f}% 失败），建议检查网络稳定性或降低抓取频率。".format(
            data_errors / total * 100
        ))

    # 5. General suggestions
    if not suggestions:
        if peak_viewers < 100:
            suggestions.append("📢 **直播间热度偏低**（峰值<100人），建议通过短视频预热、粉丝群通知等方式增加开播预约。")
        elif peak_viewers < 1000:
            suggestions.append("📢 **中小规模直播间**（峰值{:,}人），建议加强评论区互动和引导关注，提升粉丝转化。".format(peak_viewers))
        else:
            suggestions.append("📢 **直播间表现良好**（峰值{:,}人），可尝试增加互动环节（抽奖、问答）进一步提升热度。".format(peak_viewers))

    suggestions.append("📋 **建议记录每次直播的标题、分类、开播时间**，长期积累数据后可分析出最佳的直播时段和内容方向。")

    return suggestions


# ── Report CLI Handler ────────────────────────────────────────

def cmd_report(args):
    """Generate a Markdown report for a completed session."""
    session_id_or_uid = args.session_id

    # Try as numeric session ID first, then as streamer UID
    conn = get_db()
    try:
        session_id = int(session_id_or_uid)
        session = conn.execute(
            "SELECT id FROM monitoring_sessions WHERE id = ?", (session_id,)
        ).fetchone()
    except ValueError:
        session_id = None
        session = None

    if session is None:
        # Try as streamer UID
        sessions = conn.execute(
            "SELECT id, streamer_uid, streamer_name, start_time "
            "FROM monitoring_sessions "
            "WHERE streamer_uid = ? OR room_url LIKE ? "
            "ORDER BY id DESC LIMIT 10",
            (session_id_or_uid, f"%{session_id_or_uid}%"),
        ).fetchall()
        conn.close()

        if not sessions:
            print(f"❌ 未找到匹配的会话: {session_id_or_uid}")
            print("   使用 'list' 命令查看所有会话")
            return 1
        if len(sessions) > 1:
            print(f"📋 找到多个匹配会话:")
            for s in sessions:
                print(f"  #{s['id']} — {s['streamer_name']} ({s['start_time']})")
            print("\n请指定具体会话ID: hermes skill run douyin-livestream report <ID>")
            return 0

        session_id = sessions[0]["id"]

    conn.close()

    report_path = generate_report(session_id, output_path=args.output)
    if report_path:
        print(f"✅ 运营报告已生成: {report_path}")

        # Print summary
        try:
            with open(report_path) as f:
                content = f.read()
            # Extract key stats for quick view
            for line in content.split("\n"):
                if "**峰值在线**" in line:
                    print(f"\n📊 快速摘要: {line.strip()}")
                elif "**平均在线**" in line:
                    print(f"            {line.strip()}")
                elif "**直播时长**" in line:
                    print(f"            {line.strip()}")
        except Exception:
            pass

        return 0
    return 1


# ── Main Entry ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="抖音直播间监控与分析工具",
        usage="hermes skill run douyin-livestream <command> [<args>]",
    )
    parser.add_argument("command", nargs="?", help="子命令: monitor|list|report")
    parser.add_argument("args", nargs=argparse.REMAINDER,
                        help="子命令参数")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        print("\n子命令:")
        print("  monitor <room_id>    开始监控一个直播间")
        print("                       可选: --interval 秒 (默认300)")
        print("  list                 查看正在监控的直播间")
        print("  dashboard            多直播间监控看板")
        print("                       可选: --watch 实时刷新 | --compare 竞品对比")
        print("  stats                跨场次统计分析（分析所有已完成场次）")
        print("  alert                智能告警系统")
        print("                       可选: check (默认) 检查新告警 | list 查看历史告警")
        print("  tag                  内容标注（直播中标记关键事件）")
        print("                       add <内容> 添加事件 | list 查看 | analyze 分析效果")
        print("  report <id>          生成运营报告")
        print("                       可选: --output <path> 指定输出路径")
        print("\n示例:")
        print("  hermes skill run douyin-livestream monitor 738365741507 --interval 180")
        print("  hermes skill run douyin-livestream list")
        print("  hermes skill run douyin-livestream dashboard --watch --compare")
        print("  hermes skill run douyin-livestream stats")
        print("  hermes skill run douyin-livestream alert check")
        print("  hermes skill run douyin-livestream report 1")
        return 1

    if args.command == "monitor":
        # Parse extra args
        import argparse as ap2
        p = ap2.ArgumentParser()
        p.add_argument("room_id", help="直播间ID (URL中的数字)")
        p.add_argument("--interval", type=int, default=300, help="抓取间隔(秒)")
        m_args = p.parse_args(args.args)
        return cmd_monitor(m_args)

    elif args.command == "list":
        return cmd_list(None)

    elif args.command == "report":
        import argparse as ap2
        p = ap2.ArgumentParser()
        p.add_argument("session_id", help="会话ID 或 主播UID")
        p.add_argument("--output", "-o", help="报告输出路径")
        r_args = p.parse_args(args.args)
        return cmd_report(r_args)

    elif args.command == "dashboard":
        dashboard_script = SCRIPTS_DIR / "dashboard.py"
        import subprocess
        cmd = [sys.executable, str(dashboard_script)] + args.args
        return subprocess.call(cmd)

    elif args.command == "stats":
        stats_script = SCRIPTS_DIR / "stats.py"
        import subprocess
        return subprocess.call([sys.executable, str(stats_script)] + args.args)

    elif args.command == "alert":
        alert_script = SCRIPTS_DIR / "alert.py"
        import subprocess
        return subprocess.call([sys.executable, str(alert_script)] + args.args)

    elif args.command == "tag":
        tag_script = SCRIPTS_DIR / "tag.py"
        import subprocess
        return subprocess.call([sys.executable, str(tag_script)] + args.args)

    else:
        print(f"❌ 未知命令: {args.command}")
        print("可用命令: monitor, list, dashboard, report, stats, alert")
        return 1


if __name__ == "__main__":
    sys.exit(main())
