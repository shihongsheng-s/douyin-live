#!/usr/bin/env python3
"""
生成监控报告并保存到桌面和对话

用法:
    python3 scripts/generate_report.py <session_id>
    python3 scripts/generate_report.py <session_id> --desktop
"""

import sys
import os
import json
import datetime
from pathlib import Path

# Add scripts dir to path
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from douyin_livestream import generate_report, get_db


# ── 跨平台桌面路径 ──────────────────────────────────────

def get_desktop_path():
    """Cross-platform desktop path detection."""
    import os as _os
    # WSL
    if _os.environ.get("WSL_DISTRO_NAME"):
        users_dir = Path("/mnt/c/Users")
        if users_dir.exists():
            for p in sorted(users_dir.iterdir()):
                if p.name not in ("All Users", "Default", "Default User", "Public", "desktop.ini"):
                    desktop_candidate = p / "Desktop"
                    if desktop_candidate.exists():
                        return desktop_candidate
        return Path.home() / "Desktop"
    # macOS
    if sys.platform == "darwin":
        return Path.home() / "Desktop"
    # Linux
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        cn = Path.home() / "桌面"
        if cn.exists():
            return cn
    return desktop


def save_to_desktop(report_content, streamer_name, session_id):
    """Save report to desktop (cross-platform)."""
    safe_name = (streamer_name or f"session_{session_id}").replace("/", "_").replace(" ", "_")
    date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"直播运营报告_{safe_name}_{date_str}.md"
    desktop_dir = get_desktop_path()
    desktop_dir.mkdir(parents=True, exist_ok=True)
    desktop_path = desktop_dir / filename
    desktop_path.write_text(report_content, encoding="utf-8")
    return str(desktop_path)


def get_session_info(session_id):
    """Get session info from DB."""
    conn = get_db()
    session = conn.execute(
        "SELECT * FROM monitoring_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()
    return session


def get_latest_active_session():
    """Get the latest session that was running or completed."""
    conn = get_db()
    session = conn.execute(
        "SELECT id, streamer_name FROM monitoring_sessions "
        "WHERE status IN ('running', 'completed') "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return session


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="生成抖音直播监控报告")
    parser.add_argument("session_id", nargs="?", help="会话ID（缺省则用最新的）")
    parser.add_argument("--desktop", action="store_true", help="同时保存到桌面")
    args = parser.parse_args()

    session_id = args.session_id
    if not session_id:
        session = get_latest_active_session()
        if not session:
            print("❌ 没有找到监控会话")
            sys.exit(1)
        session_id = session["id"]
        print(f"📋 使用最新会话 #{session_id}")

    # Generate report
    report_path = generate_report(session_id)
    if not report_path:
        print(f"❌ 报告生成失败")
        sys.exit(1)

    print(f"✅ 报告已生成: {report_path}")

    # Read the content for output
    with open(report_path) as f:
        content = f.read()

    # Save to desktop if requested
    if args.desktop:
        session = get_session_info(session_id)
        streamer = session["streamer_name"] if session else "unknown"
        desktop_path = save_to_desktop(content, streamer, session_id)
        print(f"✅ 已保存到桌面: {desktop_path}")

    # Print the full report to stdout
    print("\n" + "=" * 60)
    print(content)
