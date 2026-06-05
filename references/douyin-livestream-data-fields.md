# Douyin Livestream — RSC Payload Data Field Reference

This document catalogs all discoverable fields in the React Server Components (RSC) payload of `live.douyin.com/<room_id>` pages, extracted from a real session (room 738365741507, streamer "无云斋", gaming category).

## Room Info Block (`roomStore.roomInfo.room`)

Found by searching HTML for `"roomStore":{"roomInfo":{"room":{...`

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `id_str` | string | `"7647708228742171426"` | Internal 19-digit room ID (≠ URL room_id) |
| `status` | int | `2` | `2` = live; unknown values for ended/offline |
| `status_str` | string | `"2"` | String version of status |
| `title` | string | `"无云斋主正在直播"` | Room title, often includes streamer name |
| `user_count_str` | string | `"1000+"` | Approximate viewer count (display format) |
| `cover` | object | `{"url_list": [...]}` | Array of Douyin CDN cover image URLs |
| `stream_url.flv_pull_url` | object | `{FULL_HD1: "...", SD1: "...", SD2: "..."}` | FLV stream URLs per quality level |
| `stream_url.default_resolution` | string | `"FULL_HD1"` | Default stream quality |
| `stream_url.hls_pull_url_map` | object | `{FULL_HD1: "...", SD1: "...", SD2: "..."}` | HLS stream URLs per quality |
| `stream_url.hls_pull_url` | string | `"http://pull-hls-t95..."` | Default HLS URL |
| `stream_url.stream_orientation` | int | `1` | Stream orientation flag |
| `stream_url.live_core_sdk_data` | object | `{pull_data: {options: {...}}}` | Contains quality options, bitrates, resolutions |

## Quality Options (`live_core_sdk_data.pull_data.options`)

| Field | Example |
|-------|---------|
| `default_quality.name` | `"超清"` |
| `default_quality.sdk_key` | `"origin"` |
| `default_quality.v_codec` | `"264"` |
| `default_quality.resolution` | `"720x1280"` |
| `default_quality.level` | `3` |
| `qualities[*].name` | `"标清"`, `"高清"`, `"超清"` |
| `qualities[*].sdk_key` | `"ld"`, `"sd"`, `"origin"` |
| `qualities[*].resolution` | `"480x853"`, `"540x960"`, `"720x1280"` |
| `qualities[*].v_bit_rate` | `1000000`, `1500000`, `1982464` |
| `qualities[*].fps` | `22` |
| `extra.height` | `1280` |
| `extra.width` | `720` |

## Owner / Streamer Info Block

Found by searching HTML for `"owner":{...` near the roomInfo section.

| Field | Type | Example |
|-------|------|---------|
| `id_str` | string | `"96405842509"` | Streamer's Douyin UID |
| `sec_uid` | string | `"MS4wLjABAAAA2oJjgb_YGBDKFpMgdv2qLyHib_6Yy4Au4tIP76hdGcs"` |
| `nickname` | string | `"无云斋"` |
| `avatar_thumb.url_list` | array | Array of avatar image CDN URLs |
| `follow_info.follow_status` | int | `0` (not followed) |
| `subscribe.is_member` | bool | `false` |
| `subscribe.level` | int | `0` |
| `foreign_user` | int | `0` |

## Room Auth Block

Found right after owner block.

| Field | Value | Meaning |
|-------|-------|---------|
| `Chat` | `true` | Text chat enabled |
| `Danmaku` | `false` | Danmaku (bullet comments) disabled |
| `Gift` | `true` | Gift sending enabled |
| `LuckMoney` | `true` | Red packets enabled |
| `Digg` | `true` | Like button enabled |
| `RoomContributor` | `true` | Contributor ranking enabled |
| `Props` | `true` | Props enabled |
| `UserCard` | `false` | User card disabled |
| `POI` | `true` | Location info visible |
| `Share` | `true` | Share enabled |
| `Landscape` | `1` | Landscape mode allowed |
| `LandscapeChat` | `2` | Landscape chat mode |
| `PublicScreen` | `1` | Public screen enabled |

## Game Category

Found in the `homeStore.recommendCategoryData` array (or the section before roomStore).

Each category item has:
```json
{
  "partition": {"id_str": "1011032", "type": 1, "title": "三角洲行动"},
  "has_parent_node": true,
  "second_node": {"id_str": "1", "type": 1, "title": "射击游戏"},
  "first_node": {"id_str": "103", "type": 4, "title": "游戏"}
}
```

The category hierarchy is: First Node (大分类) → Second Node (中分类) → Partition (具体游戏)

## Location

Found as `"room_chat_guide_locale_city":"天津"` in the RSC payload (near the room section).

## Raw HTML Scanning Strategy

Since the data is in a React Server Components stream (not plain JSON), use this approach:

1. **Find a known anchor** — e.g., the streamer's nickname which appears as plain unicode
2. **Extract a 2000-5000 byte window** around it
3. **Unescape the payload**: `\\"` → `"`, `\\u0026` → `&`, `\\/` → `/`, `\\n` → newline
4. **Parse** with regex or JSON parser

Known anchors ordered by reliability:
1. Streamer nickname (appears as plain Hanzi in `"nickname":"..."`)
2. `"roomStore"` string
3. `"owner"` string
4. Long numeric IDs (19-digit room IDs are unique)
5. `"status":2` (live status indicator)

## Cover Image

URL of the livestream room cover/snapshot image. Extracted from `room.cover.url_list[0]`.

```python
# In decoded RSC: "cover":{"url_list":["https://...image?..."]}
# In raw HTML: \"cover\":{\"url_list\":[\"https://...\"]}
```

Stored in `snapshots.raw_json` as key `cover_url`.

Example:
```
https://p11-webcast-sign.douyinpic.com/image-cut-tos-priv/xxx~tplv-qz53dukwul-common-resize:0:0.image?biz_tag=app_6383_webcast...
```

The cover image is displayed in HTML reports (generate_html_report.py) as a 9:16 aspect-ratio thumbnail in the overview section.

## Session Metadata

Also available from the HTML:
- `window.__new_project__='1'` — React project flag
- `window.__rsc_p__` — RSC route registrations (indicates what APIs are registered)
- `__ac_nonce` cookie — anti-crawler token from initial page visit
