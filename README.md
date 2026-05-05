# 盲棋 CLI (Blind Xiangqi)

中国象棋盲棋练习 CLI 工具，支持自然语言招法输入，集成 Pikafish AI 引擎。

## 功能特性

- 🎯 **自然语言招法**：支持中文招法输入（如「炮二平五」），红黑双方均可使用中文数字
- 🤖 **AI 对弈**：集成 Pikafish 引擎，支持 1-10 难度等级
- 📊 **棋盘可视化**：生成 SVG 棋盘图片
- 💾 **对局记录**：自动保存对局历史，支持复盘和继续对局
- ⏪ **悔棋功能**：支持回退到任意回合
- 🏆 **胜负判断**：自动检测将死、困毙，显示趣味提示
- 🔧 **可配置**：支持默认难度、执方等配置

## 安装

### 1. 创建环境

```bash
conda create -n auto-dev python=3.10 -y
conda activate auto-dev
```

### 2. 安装依赖

```bash
pip install -e .
```

### 3. 安装 Pikafish 引擎

下载预编译版本并放置到指定目录：

```bash
mkdir -p ~/.blind-xiangqi/engines
# 将 pikafish 和 pikafish.nnue 放入该目录
```

引擎文件：
- `pikafish` - 主程序
- `pikafish.nnue` - 神经网络评估文件

## 使用说明

### 开始新对局

```bash
blind-xiangqi play --color red --level 5
```

参数说明：
- `--color` / `-c`：执方选择（`red` 红方 / `black` 黑方），默认红方
- `--level` / `-l`：难度等级 1-10，默认 5

### 继续历史对局

```bash
# 从最后一步继续
blind-xiangqi resume 2026-05-04/game.xqi

# 从第10步继续（回退到第10步后重新开始）
blind-xiangqi resume 2026-05-04/game.xqi -m 10

# 从开局重新开始这盘棋
blind-xiangqi resume 2026-05-04/game.xqi -m 0
```

### 查看历史对局

```bash
# 查看最近10局
blind-xiangqi history

# 按日期筛选
blind-xiangqi history --date 2026-05-04

# 限制数量
blind-xiangqi history --limit 5
```

### 显示棋盘图片

```bash
# 显示初始局面
blind-xiangqi show

# 显示指定对局
blind-xiangqi show 2026-05-04/game.xqi

# 显示第10招后的棋盘
blind-xiangqi show 2026-05-04/game.xqi --move 10

# 指定输出路径
blind-xiangqi show -o /tmp/board.svg
```

### 配置设置

```bash
# 查看当前配置
blind-xiangqi config

# 设置默认难度
blind-xiangqi config --default-level 8

# 设置默认执方
blind-xiangqi config --default-color black
```

## 对局内交互命令

进入对局后，支持以下命令：

| 命令 | 说明 | 示例 |
|------|------|------|
| `<招法>` | 输入中文招法走棋 | `炮二平五` |
| `back N` | 回退 N 步（默认1步） | `back 2` |
| `history` | 显示招法记录和可回退范围 | |
| `show` | 生成当前棋盘图片 | |
| `认输` / `resign` | 认输结束对局 | |
| `quit` / `exit` | 保存并退出对局 | |
| `help` | 显示帮助信息 | |

## 招法输入格式

中文招法格式遵循标准中国象棋记谱法：

```
<棋子名><列号><动作><目标列/行数>
```

**输入兼容性**：无论执红方还是黑方，都可以使用中文数字（一～九）或阿拉伯数字（1-9）输入。

示例：
- `炮二平五` 或 `炮2平5` - 炮从第二列平移到第五列
- `马八进七` 或 `马8进7` - 马从第八列进到第七列
- `车一进一` 或 `车1进1` - 车从第一列前进一格

## 游戏提示

### 将军提示

当走棋后将军对手，会显示 `【将军】` 提示。

### 胜负判断

游戏会自动检测将死和困毙状态：

| 场景 | 提示文案 |
|------|---------|
| 玩家绝杀 AI | `绝杀吴姐！` 或 `一招毙命！`（随机） |
| AI 绝杀玩家 | `哦哦，你噶了` |
| 玩家走棋导致被将军 | `非法招法: 此招法会导致被将军` |

## 难度等级说明

| 等级 | 搜索深度 | 思考时间 | 适用场景 |
|------|----------|----------|----------|
| 1-2 | depth 1-2 | 0.1秒 | 入门练习 |
| 3-5 | depth 3-5 | 0.1-0.3秒 | 初学者 |
| 6-8 | depth 6-10 | 0.3-0.5秒 | 中等水平 |
| 9-10 | depth 12-15 | 0.5-1.0秒 | 高手挑战 |

## 目录结构

```
~/.blind-xiangqi/
├── config.json           # 用户配置
├── engines/
│   ├── pikafish          # 引擎程序
│   └── pikafish.nnue     # 神经网络文件
└── games/
    └── 2026-05-04/       # 按日期分目录
        └── 08-21_red_lv5.xqi  # 对局记录文件
```

## 对局记录格式

`.xqi` 文件为 JSON 格式：

```json
{
  "meta": {
    "date": "2026-05-04T08:21:00",
    "player_color": "red",
    "level": 5,
    "result": "ongoing",
    "total_moves": 20
  },
  "moves": [
    {"num": 1, "player": "red", "chinese": "炮二平五", "uci": "h2e2"},
    {"num": 1, "player": "black", "chinese": "炮2平5", "uci": "b7e7"}
  ],
  "fen_history": ["...", "..."]
}
```

## 测试

```bash
# 运行全部测试
pytest tests/ -v

# 压力测试（Mock引擎）
pytest tests/test_pressure.py -v

# 真实引擎测试
pytest tests/test_real_engine.py -v
```

## 技术架构

### 核心依赖

| 库 | 用途 |
|---|------|
| **cchess** | 招法解析、合法性验证、将军检测 |
| **Pikafish** | AI 引擎（UCI 协议） |
| **xiangqi-setup** | 棋盘图片生成 |

### cchess 库功能

本项目使用 cchess 库实现核心象棋逻辑：

| 功能 | cchess API |
|------|------------|
| 中文招法解析 | `board.move_text("炮二平五")` |
| UCI 转中文 | `board.move_iccs("h2e2").to_text()` |
| 招法合法性 | `board.is_valid_iccs_move(uci)` |
| 被将军检测 | `board.is_checked_move(pos_from, pos_to)` |
| 无棋可走判断 | `board.no_moves()` |
| 将军检测 | `board.is_checking()` |

### 项目结构

```
xiangqi_engine/
├── cli.py              # CLI 命令入口、游戏循环
├── engine/
│   ├── pikafish.py     # Pikafish 引擎封装
│   └── uci_client.py   # UCI 协议客户端
├── game/
│   ├── board.py        # 棋盘状态管理
│   ├── game.py         # 对局管理、悔棋
│   ├── move.py         # 招法记录
│   └── validator.py    # 招法合法性验证
├── notation/
│   └── converter.py    # 中文招法转换（基于 cchess）
├── storage/
│   ├── config.py       # 配置管理
│   └── recorder.py     # 对局存储
├── image/
│   └ board_generator.py # 棋盘图片生成
```

## 开发

```bash
# 代码检查
ruff check xiangqi_engine/

# 自动修复
ruff check xiangqi_engine/ --fix
```

## Claude Code Skill

本项目包含一个 Claude Code skill，用于在 Claude Code CLI 中进行盲棋对弈。

### Skill 位置

```
.claude/skills/xiangqi-partner/
├── SKILL.md           # Skill 定义和使用说明
└── scripts/
    ├── xiangqi.sh     # Linux/macOS 启动脚本
    ├── xiangqi.bat    # Windows 启动脚本
    ├── xiangqi.env    # 配置文件
    ├── config.py      # 配置管理
    ├── executor.py    # 命令执行器
    └── xiangqi_api.py # API 封装
```

### 功能特性

- **自然语言交互**：直接与 Claude 对话下棋
- **招法纠错**：自动识别并纠错常见输入错字（如 `马吴进琪` → `马五进七`）
- **简洁输出**：直接返回程序输出，无冗余提示
- **多对局管理**：支持创建、切换、查看多个对局
- **棋盘可视化**：生成 SVG 棋盘图片

### 触发方式

在 Claude Code 中输入以下关键词即可触发：

- `下棋`、`象棋`、`盲棋`、`对弈`、`走棋`、`棋局`、`开局`

### 使用示例

```
用户: 我想下棋
Claude: [展示当前配置和对局列表]

用户: 红方，难度5
Claude: 执红方，难度5级，开始对局

用户: 炮二平五
Claude: 🎯 用户：炮二平五
        🤖 AI：炮8平5

用户: 马吴进琪
Claude: 🎯 用户：马五进七  [自动纠错]
        🤖 AI：xxx
```

### Skill 详细说明

完整功能请查看 [.claude/skills/xiangqi-partner/SKILL.md](.claude/skills/xiangqi-partner/SKILL.md)。

## 飞书机器人

飞书机器人是盲棋 CLI 的即时通讯版本，用户可以直接在飞书中与机器人对话下棋，无需通过大模型中转。

### 功能特性

- 🔄 **WebSocket 长连接**：无需公网 IP，服务器主动连接飞书
- 🎯 **自然语言交互**：发送招法文字直接走棋
- 🖼️ **棋盘图片**：发送「棋盘」查看当前局面
- 📋 **历史管理**：查看、切换、删除历史对局
- ⏪ **悔棋功能**：支持回退招法
- 🔒 **删除确认**：所有删除操作需二次确认

### 安装配置

#### 1. 创建飞书应用

1. 登录 [飞书开放平台](https://open.feishu.cn)
2. 创建企业自建应用，开启机器人能力
3. 配置权限：`im:message:send_as_bot`, `im:message:receive_as_bot`
4. 配置事件订阅（长连接方式），添加事件 `im.message.receive_v1`

#### 2. 配置环境变量

创建 `config/feishu.env` 文件：

```bash
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_ENCRYPT_KEY=
FEISHU_VERIFICATION_TOKEN=
DEFAULT_LEVEL=5
DEFAULT_COLOR=red
BOARD_IMAGE_METHOD=pil  # svg 或 pil
```

#### 3. 启动机器人

```bash
python main.py
```

### 交互命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `下棋` | 开始新对局 | `下棋`、`红方难度5` |
| `<招法>` | 走棋 | `炮二平五`、`马8进7` |
| `棋谱` | 查看招法记录 | |
| `棋盘` | 查看棋盘图片 | |
| `历史` | 查看历史对局 | `历史`、`历史 5`、`今天`、`昨天`、`最近三天`、`这个月` |
| `切换 N` | 继续历史对局 | `切换 1` |
| `悔棋` | 悔一步棋 | `悔棋`、`悔棋2` |
| `删除 N` | 删除对局（需确认） | `删除 1`、`删除 今天`、`清空` |
| `确认删除` | 执行删除 | |
| `认输` | 结束当前对局 | |
| `帮助` | 显示帮助信息 | |

### 时间范围查询

支持以下时间范围描述：

| 输入 | 含义 |
|------|------|
| `今天` / `今日` | 今日对局 |
| `昨天` / `昨日` | 昨日对局 |
| `最近三天` / `最近7天` | 最近 N 天 |
| `这一周` / `本周` | 本周对局 |
| `这个月` / `本月` | 本月对局 |
| `上个月` / `上月` | 上月对局 |

### 删除确认流程

所有删除操作需要二次确认：

```
用户: 删除 1
机器人: 即将删除对局 #1
       2026-05-05 红方 Lv5 12步
       发送「确认删除」执行

用户: 确认删除
机器人: 已删除对局 #1
```

发送其他消息会取消待执行的删除操作。

### 棋盘图片生成

支持两种方式：

| 方式 | 说明 |
|------|------|
| `svg` | 使用 xiangqi-setup CLI（原有稳定版本） |
| `pil` | 使用 PIL 直接绘制 PNG（新增版本，支持方向调整） |

通过 `BOARD_IMAGE_METHOD` 配置切换。

### 技术架构

```
feishu_bot/
├── bot.py           # 机器人主逻辑（WebSocket 长连接）
├── config.py        # 飞书配置管理
└── message.py       # 消息解析、意图识别

用户消息 → 飞书 WebSocket → BlindChessBot → GameSession → Pikafish 引擎 → 返回响应
```

---

## License

MIT