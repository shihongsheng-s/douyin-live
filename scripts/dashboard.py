#!/usr/bin/env python3
"""
抖音直播间监控看板 — 多直播间实时概览

用法:
    python3 scripts/dashboard.py                    # 静态看板
    python3 scripts/dashboard.py --watch            # 每5秒自动刷新
    python3 scripts/dashboard.py --watch --interval 10  # 每10秒刷新
"""

import sys
import os
import time
import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from douyin_livestream import get_db, format_duration

# ── ANSI Colors ───────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"  # Clear screen + move cursor home

STATUS_COLORS = {
    "running": GREEN,
    "completed": CYAN,
    "error": RED,
    "cancelled": YELLOW,
}

STATUS_ICONS = {
    "running": "🟢",
    "completed": "✅",
    "error": "❌",
    "cancelled": "⏹",
}


def parse_dt(dt_str):
    """Parse datetime string, return datetime or None."""
    if not dt_str:
        return None
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
        try:
            return datetime.datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return None


def build_dashboard():
    """Query DB and return dashboard data."""
    conn = get_db()

    rows = conn.execute("""
        SELECT
            ms.id,
            ms.streamer_name,
            ms.streamer_uid,
            ms.room_url,
            ms.game_category,
            ms.location,
            ms.start_time,
            ms.end_time,
            ms.status,
            (SELECT COUNT(*) FROM snapshots WHERE session_id = ms.id) as snap_count,
            (SELECT MAX(user_count_num) FROM snapshots WHERE session_id = ms.id) as peak_viewers,
            (SELECT user_count_str FROM snapshots
             WHERE session_id = ms.id AND error IS NULL
             ORDER BY id DESC LIMIT 1) as last_user_count,
            (SELECT timestamp FROM snapshots
             WHERE session_id = ms.id AND error IS NULL
             ORDER BY id DESC LIMIT 1) as last_snap_time,
            (SELECT status_code FROM snapshots
             WHERE session_id = ms.id AND error IS NULL
             ORDER BY id DESC LIMIT 1) as last_status_code,
            (SELECT title FROM snapshots
             WHERE session_id = ms.id AND error IS NULL
             ORDER BY id DESC LIMIT 1) as last_title
        FROM monitoring_sessions ms
        WHERE ms.status = 'running'
        ORDER BY ms.id DESC
    """).fetchall()

    conn.close()
    return rows


def render_dashboard(rows, watch_mode=False):
    """Render the dashboard to a string."""
    lines = []

    # ── Header ────────────────────────────────────────────────
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    running = len(rows)

    lines.append(f"{BOLD}{CYAN}╔══════════════════════════════════════════════════════════════╗{RESET}")
    lines.append(f"{BOLD}{CYAN}║       抖音直播间监控看板{RESET}                          {now_str}")
    lines.append(f"{BOLD}{CYAN}╠══════════════════════════════════════════════════════════════╣{RESET}")
    lines.append(f"{BOLD}{CYAN}║{RESET}  🟢 正在监控: {running} 个直播间{RESET}")
    if watch_mode:
        lines.append(f"{BOLD}{CYAN}║{RESET}  {DIM}按 Ctrl+C 退出看板{RESET}")
    lines.append(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════════════╝{RESET}")
    lines.append("")

    if not rows:
        lines.append(f"{DIM}暂无监控记录，使用 monitor 命令开始监控{RESET}")
        lines.append("")
        return "\n".join(lines)

    # ── Table Header ──────────────────────────────────────────
    header = (
        f"{BOLD}{'ID':>4}  {'主播':<14} {'状态':<6} {'在线':<10} {'数据点':>6}  "
        f"{'已播时长':<12} {'分类':<12} {'最后更新'}{RESET}"
    )
    lines.append(header)
    lines.append("─" * len(header))

    # ── Table Rows ────────────────────────────────────────────
    for r in rows:
        sid = r["id"]
        name = (r["streamer_name"] or "?")[:14]
        status_text = r["status"]
        status_color = STATUS_COLORS.get(status_text, RESET)
        status_icon = STATUS_ICONS.get(status_text, "❓")

        # Online count
        if status_text == "running":
            online = r["last_user_count"] or "等待数据..."
            # Show live duration
            st = parse_dt(r["start_time"])
            if st:
                duration_secs = (datetime.datetime.now() - st).total_seconds()
                duration_str = format_duration(duration_secs)
            else:
                duration_str = "N/A"
        elif status_text == "completed":
            peak = r["peak_viewers"] or "?"
            online = f"峰值: {peak}"
            st = parse_dt(r["start_time"])
            et = parse_dt(r["end_time"])
            if st and et:
                duration_secs = (et - st).total_seconds()
                duration_str = format_duration(duration_secs)
            else:
                duration_str = "N/A"
        else:
            online = "-"
            duration_str = "-"

        snap_count = r["snap_count"] or 0
        category = (r["game_category"] or "-")[:12]

        # Last update time
        last_ts = r["last_snap_time"] or ""
        if last_ts:
            try:
                dt = datetime.datetime.strptime(last_ts, "%Y-%m-%d %H:%M:%S")
                last_str = dt.strftime("%H:%M:%S")
            except ValueError:
                last_str = last_ts[-8:] if len(last_ts) >= 8 else last_ts
        else:
            last_str = "-"

        # Color the status badge
        status_badge = f"{status_color}{status_icon} {status_text}{RESET}"

        line = (
            f"{sid:>4}  {name:<14} {status_badge:<12} {online:<10} {snap_count:>6}  "
            f"{duration_str:<12} {category:<12} {last_str}"
        )
        lines.append(line)

    lines.append("─" * len(header))
    lines.append(f"{DIM}ID = 会话ID | 使用 report <ID> 查看详细报告{RESET}")
    lines.append("")

    return "\n".join(lines)


def render_compare(rows):
    """
    Render a comparison grid for multiple running sessions (P0).
    Shows all sessions side-by-side with key metrics.
    """
    lines = []
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    count = len(rows)

    lines.append(f"{BOLD}{CYAN}╔══════════════════════════════════════════════════════════════╗{RESET}")
    lines.append(f"{BOLD}{CYAN}║       🏆 竞品对比看板{RESET}                          {now_str}")
    lines.append(f"{BOLD}{CYAN}╠══════════════════════════════════════════════════════════════╣{RESET}")
    lines.append(f"{BOLD}{CYAN}║{RESET}  对比直播间: {count} 个  |  绿色=最高  红色=最低")
    if count < 2:
        lines.append(f"{BOLD}{CYAN}║{RESET}  {YELLOW}提示: 需要至少2个直播间才能对比，继续监控更多直播间{RESET}")
    lines.append(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════════════╝{RESET}")
    lines.append("")

    if not rows:
        return render_dashboard(rows)  # fallback

    # Build comparison data
    columns = []
    for r in rows:
        sid = r["id"]
        name = (r["streamer_name"] or "?")[:14]
        st = parse_dt(r["start_time"])
        duration_sec = (datetime.datetime.now() - st).total_seconds() if st else 0
        online = r["last_user_count"] or "0"
        peak = r["peak_viewers"] or 0
        snap_count = r["snap_count"] or 0
        category = (r["game_category"] or "-")[:10]

        # Parse online to number
        try:
            online_num = int(''.join(c for c in online if c.isdigit())) if online else 0
        except ValueError:
            online_num = 0

        columns.append({
            "name": name,
            "online": online,
            "online_num": online_num,
            "peak": peak,
            "snaps": snap_count,
            "duration": format_duration(duration_sec),
            "duration_sec": duration_sec,
            "category": category,
        })

    # Find max/min values for highlighting
    max_online = max(c["online_num"] for c in columns) if columns else 0
    max_peak = max(c["peak"] for c in columns) if columns else 0
    max_snaps = max(c["snaps"] for c in columns) if columns else 0

    # ── Comparison table ──────────────────────────────────────
    col_width = 20
    sep = "  "

    # Header row
    hdr = f"{'指标':<12}"
    for c in columns:
        hdr += f"{sep}{BOLD}{c['name']:<{col_width}}{RESET}"
    lines.append(hdr)
    lines.append("─" * (12 + (col_width + len(sep)) * len(columns)))

    def fmt_val(val, is_max=False, is_min=False):
        if is_max:
            return f"{GREEN}{val:<{col_width}}{RESET}"
        elif is_min:
            return f"{RED}{val:<{col_width}}{RESET}"
        return f"{val:<{col_width}}"

    metrics = [
        ("👥 在线", "online", lambda c: c["online"], False),
        ("📈 峰值", "peak", lambda c: str(c["peak"]), True),
        ("⏱ 时长", "duration", lambda c: c["duration"], False),
        ("📊 数据点", "snaps", lambda c: str(c["snaps"]), True),
        ("🏷 分类", "category", lambda c: c["category"], False),
    ]

    for label, key, val_fn, highlight in metrics:
        row = f"{label:<12}"
        vals = [val_fn(c) for c in columns]
        if highlight:
            numeric_vals = [c["online_num"] if key == "online" else c["peak"] if key == "peak" else c["snaps"] if key == "snaps" else 0 for c in columns]
            max_v = max(numeric_vals) if numeric_vals else 0
            min_v = min(numeric_vals) if numeric_vals else 0
        else:
            max_v = min_v = 0

        for i, c in enumerate(columns):
            raw = val_fn(c)
            if highlight:
                nv = c["online_num"] if key == "online" else c["peak"] if key == "peak" else c["snaps"] if key == "snaps" else 0
                is_max = nv == max_v and max_v > 0
                is_min = nv == min_v and min_v < max_v
                row += f"{sep}{fmt_val(raw, is_max, is_min)}"
            else:
                row += f"{sep}{raw:<{col_width}}"
        lines.append(row)

    lines.append("─" * (12 + (col_width + len(sep)) * len(columns)))
    lines.append(f"{DIM}🟢 = 该项最高  |  🔴 = 该项最低{RESET}")
    lines.append("")

    # ── Summary insights ──────────────────────────────────────
    if len(columns) >= 2:
        lines.append(f"{BOLD}💡 对比洞察:{RESET}")
        best_online = max(columns, key=lambda c: c["online_num"])
        best_peak = max(columns, key=lambda c: c["peak"])
        lines.append(f"  👑 在线领先: {GREEN}{best_online['name']}{RESET}（{best_online['online']}人）")
        lines.append(f"  👑 峰值最高: {GREEN}{best_peak['name']}{RESET}（峰值{best_peak['peak']}人）")

    lines.append("")
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="抖音直播间监控看板")
    parser.add_argument("--watch", "-w", action="store_true", help="自动刷新模式")
    parser.add_argument("--interval", "-i", type=int, default=5, help="刷新间隔(秒)，默认5秒")
    parser.add_argument("--compare", "-c", action="store_true", help="竞品对比模式（多直播间并列对比）")
    args = parser.parse_args()

    render_fn = render_compare if args.compare else render_dashboard

    if args.watch:
        try:
            while True:
                rows = build_dashboard()
                output = render_fn(rows, watch_mode=True)
                sys.stdout.write(CLEAR + output)
                sys.stdout.flush()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n👋 看板已退出")
    else:
        rows = build_dashboard()
        output = render_fn(rows)
        print(output)


if __name__ == "__main__":
    main()
