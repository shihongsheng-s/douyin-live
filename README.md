# 抖音直播间监控与运营分析系统

> 一个基于 Hermes Agent 的抖音直播间智能监控工具 — 自动采集直播数据、多直播间竞品对比、跨场次分析、智能告警、自动生成运营报告。

---

## 功能一览

| 功能 | 说明 |
|------|------|
| 🎯 **实时监控** | 输入直播间链接，后台自动每 N 分钟抓取在线人数、标题、状态 |
| 🏆 **竞品对比** | 多直播间并列对比，绿色 = 最高，红色 = 最低，一眼看清差距 |
| 📊 **运营报告** | 直播结束后自动生成 HTML 报告，含四层运营分析框架 |
| 🚨 **智能告警** | 在线暴跌、峰值新高、留存优异时自动推送通知 |
| 🏷️ **内容标注** | 直播中标记关键事件（上福利、讲产品、答疑），自动关联在线变化 |
| 📝 **标题追踪** | 自动检测标题变更，分析哪个标题拉在线效果最好 |
| 📈 **跨场次统计** | 分析历史所有场次，找出最佳开播时段、时长、直播日 |
| 🖥️ **Dashboard** | 终端实时看板，支持 `--watch` 自动刷新和 `--compare` 竞品对比 |

---

## 快速开始

### 1. 监控一个直播间

```bash
cd ~/.hermes/skills/social-media/douyin-livestream

# 前台监控（终端保持打开）
python3 scripts/douyin_livestream.py monitor 738365741507 --interval 180
```

### 2. 在对话中通过 Hermes 后台监控（推荐）

```
你: 帮我监控这个直播间 https://live.douyin.com/xxx
我: 好的，已设置每5分钟抓取一次
    直播结束后自动出报告
```

### 3. 查看监控看板

```bash
# 默认看板
python3 scripts/dashboard.py

# 实时刷新
python3 scripts/dashboard.py --watch

# 竞品对比模式（多个直播间并列对比）
python3 scripts/dashboard.py --compare
```

### 4. 生成运营报告

```bash
# 生成 HTML 报告并保存到桌面
python3 scripts/generate_html_report.py <session_id> --desktop

# 使用最新会话
python3 scripts/generate_html_report.py --desktop
```

---

## 命令参考

### 核心命令

```
douyin_livestream.py monitor <room_id> [--interval 秒]
  启动前台监控
  示例: python3 scripts/douyin_livestream.py monitor 738365741507 --interval 180

douyin_livestream.py list
  查看正在监控的直播间

douyin_livestream.py dashboard [--watch] [--compare]
  多直播间看板
  --watch     每5秒自动刷新
  --compare   竞品对比模式（并列对比）

douyin_livestream.py report <session_id> [--output 路径]
  生成运营报告

douyin_livestream.py stats
  跨场次统计分析（需要至少2场已完成直播）

douyin_livestream.py alert check|list
  智能告警系统
  check   检查新告警
  list    查看历史告警

douyin_livestream.py tag add|list|analyze
  内容标注系统
  add "<内容>"       标记事件（自动关联在线人数）
  list               查看事件记录
  analyze            分析哪些动作最有效
```

### 独立脚本

```bash
scripts/dashboard.py          --watch           # 看板
scripts/dashboard.py          --compare         # 竞品对比
scripts/generate_html_report.py <id> --desktop  # 生成HTML报告
scripts/stats.py                                # 跨场次分析
scripts/alert.py              check|list        # 告警系统
scripts/tag.py                add|list|analyze  # 内容标注
scripts/extract.py                              # 核心数据提取库
```

---

## 报告内容结构

HTML 报告包含完整四层运营分析框架：

```
📊 直播运营分析报告
│
├─ 📈 指标卡片
│   峰值在线 / 平均在线 / 最低在线 / 留存率 / 趋势 / 时长
│
├─ 📈 SVG 折线图
│   在线人数变化趋势（带数据标注点）
│
├─ 📋 直播间概览
│   主播 / 直播间 / 状态 / 时间 / 分类 + 封面截图
│
├─ 🔍 多维度运营效果分析（Tab切换4层）
│   ├─ 数据结果层 — KPI评分 + 核心结论
│   ├─ 行为过程层 — 进房→停留→互动→转化
│   ├─ 根因逻辑层 — 问题根因分析 + 追问清单
│   └─ 战略决策层 — 定位/产品/用户/竞争策略
│
├─ 💡 运营优化建议
│   ├─ 💪 优势     哪些做得好
│   ├─ ⚠️ 劣势     哪些存在短板
│   ├─ 🔧 优化点   具体怎么做
│   └─ 🌟 借鉴点   学习方向
│
├─ 📋 分阶段行动计划
│   ├─ 🔴 紧急（立即执行）
│   ├─ 🟡 重要（1-3天）
│   └─ 🟢 长期（持续优化）
│
├─ 🏆 历次直播数据对比
│   本场 vs 历史场次对比（峰值/平均/数据点/分类）
│
├─ 🚨 智能告警记录
│   在线暴跌 / 峰值新高 / 留存优异 等事件
│
├─ 🏷️ 内容标注效果分析
│   🥇 拉在线效果最佳的动作
│   😢 掉在线最多的动作
│
├─ 📝 标题变更与效果追踪
│   每个标题的平均在线 / 峰值 / 使用次数
│
└─ 📊 详细数据时间线
    每条抓取记录的完整数据表格
```

---

## 数据库结构

### `monitoring_sessions` — 监控会话

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER | 会话ID |
| room_url | TEXT | 直播间URL |
| room_id | TEXT | 内部19位RoomID |
| streamer_uid | TEXT | 主播UID |
| streamer_name | TEXT | 主播昵称 |
| game_category | TEXT | 直播分类 |
| location | TEXT | 位置 |
| tags | TEXT | 标签（如 `self,competitor`） |
| start_time | TEXT | 监控开始时间 |
| end_time | TEXT | 监控结束时间 |
| status | TEXT | `running` / `completed` / `error` / `cancelled` |

### `snapshots` — 数据快照

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER | 快照ID |
| session_id | INTEGER | 所属会话 |
| timestamp | TEXT | 抓取时间 |
| status_code | INTEGER | 直播状态码（2=直播中） |
| status_text | TEXT | 状态描述 |
| title | TEXT | 直播间标题 |
| user_count_str | TEXT | 在线人数（显示格式） |
| user_count_num | INTEGER | 在线人数（解析后数值） |
| nickname | TEXT | 主播昵称 |
| raw_json | TEXT | 原始JSON数据 |
| fetch_duration_ms | INTEGER | 请求耗时(ms) |
| error | TEXT | 错误信息 |

### `stream_events` — 事件标注

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER | 事件ID |
| session_id | INTEGER | 所属会话 |
| timestamp | TEXT | 标记时间 |
| content | TEXT | 事件描述 |
| online_at_event | INTEGER | 标记时的在线人数 |
| online_change | INTEGER | 与上一条快照的人数变化 |

### `alerts` — 告警记录

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER | 告警ID |
| session_id | INTEGER | 所属会话 |
| alert_type | TEXT | `sharp_drop` / `new_peak` / `great_retention` / `competitor_live` |
| message | TEXT | 告警内容 |
| severity | TEXT | `info` / `warning` / `critical` |
| triggered_at | TEXT | 触发时间 |

---

## 系统架构

```
用户输入 room_id
       ↓
  ┌──────────────────────────────────────────┐
  │          采集层 (extract.py)              │
  │                                          │
  │  fetch_page(room_id)                     │
  │    → HTTP GET live.douyin.com/{room_id}  │
  │    → 3次自动重试 + 递增延迟              │
  │                                          │
  │  extract_snapshot(html)                  │
  │    → 解析 RSC 数据                       │
  │    → 提取 status/title/user_count/cover  │
  └──────────────────┬───────────────────────┘
                     ↓
  ┌──────────────────────────────────────────┐
  │          存储层 (SQLite)                  │
  │                                          │
  │  monitoring_sessions ← 会话管理          │
  │  snapshots           ← 数据快照          │
  │  stream_events       ← 事件标注          │
  │  alerts              ← 告警记录          │
  └──────────────────┬───────────────────────┘
                     ↓
  ┌──────────────────────────────────────────┐
  │          分析层                           │
  │                                          │
  │  stats.py       ← 跨场次统计分析          │
  │  alert.py       ← 智能告警引擎           │
  │  tag.py         ← 内容效果分析           │
  └──────────────────┬───────────────────────┘
                     ↓
  ┌──────────────────────────────────────────┐
  │          展示层                           │
  │                                          │
  │  dashboard.py   ← 终端实时看板           │
  │  generate_html_report.py ← HTML报告      │
  │                   ← 飞书仪表盘风格       │
  └──────────────────────────────────────────┘
```

### 数据流（监控生命周期）

```
用户提供链接
    ↓
创建 cronjob（每5分钟）
    ↓
  循环:
    fetch_page → extract_snapshot → INSERT INTO snapshots
    ↓
    直播中 → 回复一行状态简报
    已结束 → 自动生成 HTML 报告
          → 保存到桌面
          → 发送摘要到对话
          → MONITORING_COMPLETE
    ↓
用户说"停止监控" → 移除 cronjob → 标记 cancelled → 出报告
```

---

## 安装（用于 GitHub 发布）

```bash
# 克隆到 Hermes skills 目录
cp -r douyin-livestream/ ~/.hermes/skills/social-media/

# 验证安装
python3 ~/.hermes/skills/social-media/douyin-livestream/scripts/douyin_livestream.py list
```

### 依赖

- Python 3.8+
- SQLite3（Python 内置）
- 标准库: `json`, `re`, `urllib`, `sqlite3`, `datetime`, `pathlib`

**无需第三方依赖，纯标准库实现。**

---

## 常见问题

### 为什么只能拿到在线人数？

抖音直播间页面是 React Server Components 渲染，只能拿到初始 SSR 数据（在线人数、标题、状态）。弹幕、礼物、电商数据需要通过 WebSocket 或抖音开放平台 API 获取。

### 监控频率限制？

建议抓取间隔 ≥ 60 秒。默认 300 秒（5分钟）是经过测试的安全值，低于 60 秒可能触发风控。

### 数据存储在哪里？

`~/.hermes/skills/social-media/douyin-livestream/data/monitoring.db`

### 报告保存在哪里？

- 技能目录: `~/.hermes/skills/social-media/douyin-livestream/reports/`
- 桌面（WSL）: `/mnt/c/Users/Administrator/Desktop/`

---

## License

MIT
