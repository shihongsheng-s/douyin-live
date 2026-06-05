#!/usr/bin/env python3
"""
Douyin Livestream — Core Data Extraction Library

Extracts structured data from live.douyin.com/<room_id> pages.
Handles React Server Components (RSC) payload parsing with retry logic.
"""

import re
import time
import json
import urllib.request
import urllib.error

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

BASE_URL = "https://live.douyin.com"
MAX_RETRIES = 3
RETRY_DELAY = 3

# ── Status Codes ──────────────────────────────────────────────
STATUS_MAP = {
    2: ("live", "直播中"),
    3: ("ended", "已结束"),
    4: ("ended", "已结束"),
    # other values may exist for different states
}

def status_name(code):
    """Return (english_name, chinese_name) for a status code."""
    if code in STATUS_MAP:
        return STATUS_MAP[code]
    return ("unknown", f"未知({code})")


# ── HTTP Fetch ────────────────────────────────────────────────

def fetch_page(room_id, timeout=30):
    """
    Fetch the douyin live page HTML with retry logic.

    Args:
        room_id: The room ID from the URL (e.g., '738365741507')
        timeout: Request timeout in seconds

    Returns:
        HTML string, or None if all retries exhausted

    Raises:
        ValueError if room_id is invalid
    """
    url = f"{BASE_URL}/{room_id}"
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Referer": f"{BASE_URL}/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                html = resp.read().decode("utf-8", errors="replace")
                return html
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}: {e.reason}"
            if e.code == 404:
                raise ValueError(f"直播间不存在或链接无效: {url}") from e
            if e.code == 403:
                raise ValueError(f"访问被拒绝(403)，可能被风控拦截: {url}") from e
        except urllib.error.URLError as e:
            last_error = f"网络错误: {e.reason}"
        except Exception as e:
            last_error = f"未知错误: {e}"

        if attempt < MAX_RETRIES:
            wait = RETRY_DELAY * attempt
            # Use a simple sleep; in production consider asyncio
            time.sleep(wait)

    return None


# ── RSC Payload Parsing ──────────────────────────────────────

def clean_rsc(text):
    """
    Unescape React Server Components escaped JSON strings.

    The RSC payload stores data as escaped JSON inside JS template
    literals, e.g. \\\" becomes ", \\u0026 becomes &, etc.
    """
    return (
        text.replace('\\u0026', '&')
            .replace('\\"', '"')
            .replace('\\n', '\n')
            .replace('\\/', '/')
            .replace('\\t', '\t')
            .replace('\\r', '')
    )


def find_data_region(html, anchor_words=None):
    """
    Find the region around room data in the RSC payload.

    Strategy:
    1. First try to find the actual room data by looking for 'room":{"id_str"' pattern
       which uniquely identifies the populated room info (not empty init).
    2. Fall back to searching the roomStore (last occurrence) or nickname anchors.

    Args:
        html: Raw HTML string
        anchor_words: Not used (kept for backward compat)

    Returns:
        (start, end) tuple of indices, or None if not found
    """
    # Strategy 1: Find the actual room data (room with id_str)
    # In raw HTML: \"room\":{\"id_str\":\"1234567890123456789\"
    pattern = r'\\"room\\"\s*:\s*\{[^}]*\\"id_str\\"'
    matches = list(re.finditer(pattern, html))
    if matches:
        # Use the LAST match (the one with actual data, not the empty init)
        m = matches[-1]
        idx = m.start()
        # Find the actual JSON object start
        obj_start = html.index('{', idx)
        start = max(0, obj_start - 100)
        end = min(len(html), obj_start + 8000)
        return (start, end)

    # Strategy 2: Find roomStore (last occurrence — has real data)
    try:
        last_idx = html.rindex('roomStore')
        start = max(0, last_idx - 2000)
        end = min(len(html), last_idx + 6000)
        return (start, end)
    except ValueError:
        pass

    # Strategy 3: Find any 'nickname' field that has a value
    # (not $undefined)
    try:
        for m in re.finditer(r'nickname\\":\\"(?!\$)([^"]+)', html):
            idx = m.start()
            start = max(0, idx - 2000)
            end = min(len(html), idx + 6000)
            return (start, end)
    except Exception:
        pass

    return None


def extract_snapshot(html):
    """
    Extract a complete data snapshot from a douyin live page.

    Args:
        html: Raw HTML string from fetch_page()

    Returns:
        dict with keys:
            - success: bool
            - error: str or None
            - room_id: str (internal 19-digit ID)
            - url_room_id: str (from the URL)
            - status: int (2=live)
            - status_text: str (chinese description)
            - title: str (room title)
            - user_count_str: str (display format, e.g. '1000+')
            - nickname: str (streamer name)
            - streamer_uid: str
            - game_category: str
            - location: str
            - timestamp: float (unix time)
    """
    result = {
        "success": False,
        "error": None,
        "room_id": None,
        "url_room_id": None,
        "status": None,
        "status_text": None,
        "title": None,
        "user_count_str": None,
        "nickname": None,
        "streamer_uid": None,
        "game_category": None,
        "location": None,
        "timestamp": time.time(),
    }

    if not html:
        result["error"] = "Empty HTML response"
        return result

    # Find the data region
    region = find_data_region(html)
    if region is None:
        result["error"] = "Could not locate data region in page"
        return result

    start, end = region
    snippet = html[start:end]
    clean = clean_rsc(snippet)

    # ── Extract fields ──

    # Room ID (internal 19-digit)
    m = re.search(r'"id_str"\s*:\s*"(\d{19})"', clean)
    if m:
        result["room_id"] = m.group(1)

    # URL room ID (from page metadata)
    m = re.search(r'live\.douyin\.com/(\d+)', clean)
    if m:
        result["url_room_id"] = m.group(1)

    # Status
    m = re.search(r'"status"\s*:\s*(\d+)', clean)
    if m:
        code = int(m.group(1))
        result["status"] = code
        _, result["status_text"] = status_name(code)

    # Title
    m = re.search(r'"title"\s*:\s*"([^"]+)"', clean)
    if m:
        result["title"] = m.group(1)

    # User count string
    m = re.search(r'"user_count_str"\s*:\s*"([^"]+)"', clean)
    if m:
        result["user_count_str"] = m.group(1)

    # Streamer nickname
    m = re.search(r'"nickname"\s*:\s*"([^"]+)"', clean)
    if m:
        result["nickname"] = m.group(1)

    # Streamer UID from owner block
    # Look for "owner":{"id_str":"..." in the decoded text
    m = re.search(r'"owner"\s*:\s*\{[^}]*"id_str"\s*:\s*"(\d+)"', clean)
    if m:
        result["streamer_uid"] = m.group(1)
    else:
        # Fallback: search raw HTML for owner block
        m2 = re.search(r'owner[^}]{0,500}id_str[^"]*"(\d+)"', html)
        if m2:
            result["streamer_uid"] = m2.group(1)

    # Game category (first partition title found)
    m = re.search(r'"partition"\s*:\s*\{[^}]*"title"\s*:\s*"([^"]+)"', clean)
    if m:
        result["game_category"] = m.group(1)

    # Location
    m = re.search(r'room_chat_guide_locale_city[^:]*:\s*"([^"]+)"', html)
    if m:
        result["location"] = m.group(1)

    # Cover image URL (room snapshot/thumbnail)
    # Search for "cover":{"url_list":["https://...image?..."]
    m = re.search(r'"cover"\s*:\s*\{[^}]*"url_list"\s*:\s*\[\s*"([^"]+)"', clean)
    if m:
        result["cover_url"] = m.group(1)
    else:
        # Fallback: search raw HTML for webcast cover pattern
        m2 = re.search(r'cover[^:]*:\s*\{[^}]*url_list[^:]*:\s*\[\s*"([^"]+)"', html)
        if m2:
            url = m2.group(1)
            # Clean escaping
            url = url.replace('\\u0026', '&').replace('\\/', '/').replace('\\"', '"')
            result["cover_url"] = url

    result["success"] = True
    return result


def parse_user_count(user_count_str):
    """
    Parse the user count display string to a numeric estimate.

    Examples:
        '1000+'  -> 1000
        '1.2万'  -> 12000
        '3.5万+' -> 35000
        '500'    -> 500
        '1000+'  -> 1000

    Returns:
        int (estimated count) or None if unparseable
    """
    if not user_count_str:
        return None

    s = user_count_str.strip().replace(',', '').replace('+', '')

    try:
        if '万' in s:
            val = float(s.replace('万', ''))
            return int(val * 10000)
        return int(float(s))
    except (ValueError, TypeError):
        return None


def extract_all_images(html):
    """
    Extract cover image URLs from the page.

    Returns:
        list of image URLs
    """
    urls = []
    # Look for cover URL list
    for m in re.finditer(r'"(https?://[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', html):
        url = m.group(1).replace('\\u0026', '&').replace('\\/', '/')
        if 'webcast-cover' in url or 'douyinpic.com' in url:
            urls.append(url)
    return list(set(urls))
