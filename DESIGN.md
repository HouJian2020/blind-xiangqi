# 盲棋游戏 CLI 架构设计

> 项目：blind-xiangqi  
> 版本：v1.0 设计草案  
> 日期：2026-05-02

---

## 1. 项目概述

### 1.1 项目目标

构建一个盲棋游戏系统，核心特性：

- **自然语言交互**：输入中文招法（如"炮二平五"），返回中文招法
- **难度调节**：1-10 级难度
- **对局管理**：保存、查看、复盘历史对局
- **棋盘可视化**：生成任意招法节点的棋盘图片

### 1.2 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 象棋引擎 | **Pikafish** | Stockfish 衍生，UCI 协议，Skill Level 0-20，最强开源象棋引擎 |
| 棋盘图片 | **xiangqi-setup** | Python CLI，从 FEN 生成高质量 SVG |
| 核心层 | **Python 3.10+** | UCI 通信简单，易集成 xiangqi-setup |
| CLI 层 | **argparse** | 标准库，命令解析够用 |
| Skill 层 | OpenClaw Skill（后续） | 封装 CLI 为机器人可调用 |

---

## 2. 系统架构

### 2.1 架构分层

```
┌─────────────────────────────────────────────────┐
│         Skill 封装层（可选，后续开发）            │
│   OpenClaw Skill: blind-xiangqi                 │
│   - 调用 CLI 接口                                │
│   - 返回自然语言 + 图片                          │
└─────────────────────────────────────────────────┘
                        ↓ CLI 接口
┌─────────────────────────────────────────────────┐
│              CLI 交互层                          │
│   blind-xiangqi-cli                             │
│   - 参数解析（红/黑、难度）                      │
│   - 自然语言输入/输出                            │
│   - 对局管理命令                                 │
│   - 棋盘图片生成                                 │
└─────────────────────────────────────────────────┘
                        ↓ Python API
┌─────────────────────────────────────────────────┐
│              核心引擎层                          │
│   xiangqi-engine (Python Package)               │
│   - UCI 协议通信（Pikafish）                     │
│   - 招法转换（中文 ↔ UCI坐标）                   │
│   - 局面管理（FEN 状态）                         │
│   - 对局记录序列化                               │
└─────────────────────────────────────────────────┘
                        ↓ 子进程调用
┌──────────────────┬──────────────────────────────┐
│   Pikafish       │      xiangqi-setup           │
│   (UCI引擎)      │      (图片生成)              │
│   编译二进制     │      pip 安装                │
└──────────────────┴──────────────────────────────┘
```

---

## 3. CLI 命令设计

### 3.1 命令结构

```bash
blind-xiangqi <command> [options]

Commands:
  play        开始新对局
  history     查看历史对局列表  
  review      复盘历史对局
  show        显示棋盘图片
  config      配置默认设置
```

### 3.2 启动对局 (play)

```bash
blind-xiangqi play [--color red|black] [--level 1-10]

# 示例
blind-xiangqi play                    # 默认：红方，配置文件中的默认难度
blind-xiangqi play --color black      # 执黑先行
blind-xiangqi play --level 3          # 低难度
blind-xiangqi play -c black -l 8      # 执黑，难度8
```

### 对局内交互命令

| 命令 | 说明 |
|------|------|
| `<招法>` | 输入中文招法，如 `炮二平五` |
| `history` | 打印当前对局全部招法 |
| `show` | 显示当前棋盘图片 |
| `show <N>` | 显示第N招后棋盘图片 |
| `undo` | 撤销上一招（可选） |
| `quit` | 结束对局，自动保存 |
| `help` | 显示帮助 |

### 对局内交互示例

```
$ blind-xiangqi play -l 5
执红方，难度5，开始对局

> 炮二平五
AI: 马8进7

> 马二进三  
AI: 车9平8

> history
第1局 2026-05-02 18:21
1. 炮二平五  马8进7
2. 马二进三  车9平8

> show
棋盘图片已生成: /tmp/board_current.svg

> show 1
第1招后棋盘: /tmp/board_move01.svg

> quit
对局已保存: ~/.blind-xiangqi/games/2026-05-02/18-21_red_level5.xqi
```

---

## 4. 对局管理命令

### 4.1 查看历史对局列表 (history)

```bash
blind-xiangqi history [--date YYYY-MM-DD] [--limit N]

# 示例
blind-xiangqi history                    # 最近10局
blind-xiangqi history --date 2026-05-02  # 指定日期
blind-xiangqi history --limit 20         # 最近20局
```

**输出格式**：
```
对局历史：
┌────┬─────────────────────┬───────┬────────┬─────────┐
│ #  │ 文件名              │ 执方  │ 难度   │ 结果    │
├────┼─────────────────────┼───────┼────────┼─────────┤
│ 1  │ 18-21_red_lv5.xqi   │ 红    │ 5      │ 进行中  │
│ 2  │ 20-15_black_lv8.xqi │ 黑    │ 8      │ 负      │
│ 3  │ 14-30_red_lv3.xqi   │ 红    │ 3      │ 胜      │
└────┴─────────────────────┴───────┴────────┴─────────┘
```

### 4.2 复盘历史对局 (review)

```bash
blind-xiangqi review <game-file>

# 示例
blind-xiangqi review 18-21_red_lv5.xqi
```

**复盘交互命令**：

| 命令 | 说明 |
|------|------|
| `list` | 打印全部招法 |
| `show` | 显示初始棋盘 |
| `show <N>` | 显示第N招后棋盘 |
| `goto <N>` | 跳转到第N招局面 |
| `next` | 下一招 |
| `prev` | 上一招 |
| `quit` | 退出复盘 |

### 4.3 显示棋盘图片 (show)

```bash
blind-xiangqi show <game-file> [--move N] [--output path]

# 示例
blind-xiangqi show 18-21_red_lv5.xqi           # 终局棋盘
blind-xiangqi show game.xqi --move 5           # 第5招后
blind-xiangqi show game.xqi -m 10 -o board.svg # 输出到指定路径
```

### 4.4 配置默认设置 (config)

```bash
blind-xiangqi config [--default-level 1-10]

# 示例
blind-xiangqi config --default-level 5    # 设置默认难度为5
blind-xiangqi config                      # 显示当前配置
```

**配置文件位置**：`~/.blind-xiangqi/config.json`

---

## 5. 数据存储设计

### 5.1 目录结构

```
~/.blind-xiangqi/
├── config.json                    # 配置文件
├── sessions/                      # 活跃会话索引（新增）
│   ├── session_abc123.json        # session 元数据
│   └── session_def456.json
├── games/
│   ├── 2026-05-02/
│   │   ├── 18-21_red_lv5.xqi      # 对局记录
│   │   ├── 20-15_black_lv8.xqi
│   │   └── images/                # 棋盘图片缓存（可选）
│   │       ├── 18-21_move01.svg
│   │       └── 18-21_final.svg
│   ├── 2026-05-01/
│   │   └── 14-30_red_lv3.xqi
│   └── ...
└── engines/
    └── pikafish                   # Pikafish 二进制
```

### 5.2 配置文件格式

```json
{
  "default_level": 5,
  "default_color": "red",
  "engine_path": "~/.blind-xiangqi/engines/pikafish",
  "image_theme": "clean_alpha",
  "image_output_dir": "~/.blind-xiangqi/games/images"
}
```

---

## 6. 对局记录文件格式

```json
{
  "meta": {
    "date": "2026-05-02T18:21:00+08:00",
    "player_color": "red",
    "level": 5,
    "result": "ongoing",
    "total_moves": 32
  },
  "moves": [
    {"num": 1, "player": "red", "chinese": "炮二平五", "uci": "b2e5"},
    {"num": 1, "player": "black", "chinese": "马8进7", "uci": "h9g7"},
    {"num": 2, "player": "red", "chinese": "马二进三", "uci": "b0c2"}
  ],
  "fen_history": [
    "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR",
    "..."
  ],
  "final_fen": "..."
}
```

---

## 7. 核心模块设计

### 7.1 模块划分

```
xiangqi-engine/
├── engine/
│   ├── uci_client.py       # UCI 协议通信
│   └── pikafish.py         # Pikafish 封装
├── notation/
│   ├── converter.py        # 中文 ↔ UCI 转换
│   ├── parser.py           # 中文招法解析
│   └── generator.py        # 中文招法生成
├── game/
│   ├── board.py            # 棋盘状态管理
│   ├── move.py             # 招法数据结构
│   └── game.py             # 对局管理
├── session/                # Session 管理（新增）
│   ├── manager.py          # Session 创建/加载/清理
│   ├── store.py            # Session 文件读写
│   └── id_generator.py     # Session ID 生成
├── storage/
│   ├── recorder.py         # 对局记录
│   ├── loader.py           # 加载历史对局
│   └── config.py           # 配置管理
└── image/
    └── board_generator.py  # 棋盘图片生成
```

### 7.2 招法转换逻辑

#### 中文招法格式

```
<棋子名><列号><动作><目标列号>[目标行号]

棋子名：帅/将、仕/士、相/象、车、马、炮、兵/卒
列号：红方一~九（从右到左），黑方1~9（从左到右）
动作：平（横移）、进（前进）、退（后退）
```

#### UCI 坐标格式

```
<起点列><起点行><终点列><终点行>

列：a-h（从左到右）
行：0-9（红方底线为0，黑方底线为9）
```

#### 转换示例

| 中文招法 | UCI坐标 | 说明 |
|----------|---------|------|
| 炮二平五 | b2e5 | 红炮从第2列平移到第5列 |
| 马8进7 | h9g7 | 黑马从第8列进到第7列 |
| 车一进一 | a0a1 | 红车从底线前进一格 |
| 兵三进一 | c4c5 | 红兵从第3列前进 |

---

## 8. 难度等级映射

Pikafish 支持 Skill Level 0-20，映射为用户友好的 1-10 级：

| 用户等级 | Pikafish Skill Level | 说明 |
|----------|---------------------|------|
| 1 | 0 | 初学者，随机走棋 |
| 2 | 2 | 简单，只看1-2步 |
| 3 | 4 | 入门，基本战术 |
| 4 | 6 | 普通，常见开局 |
| 5 | 8 | 中等，适中难度 |
| 6 | 10 | 较强，需要认真思考 |
| 7 | 12 | 强，接近业余高手 |
| 8 | 14 | 很强，业余高手水平 |
| 9 | 16 | 极强，接近专业水平 |
| 10 | 18-20 | 最强，专业级（含完整搜索） |

**实现方式**：
```python
def map_level(user_level: int) -> int:
    """用户等级 1-10 → Pikafish Skill Level 0-20"""
    return min(20, (user_level - 1) * 2)
```

---

## 9. 依赖安装

### 9.1 Pikafish 安装

```bash
# 编译安装
git clone https://github.com/official-pikafish/Pikafish.git
cd Pikafish/src
make -j profile-build
cp pikafish ~/.blind-xiangqi/engines/

# 或下载预编译版本
# https://github.com/official-pikafish/Pikafish/releases
```

### 9.2 xiangqi-setup 安装

```bash
pip install xiangqi-setup
```

### 9.3 Python 依赖

```bash
pip install chess  # 基础象棋库（可选，用于 FEN 解析）
```

---

## 10. 后续开发计划

### Phase 1: CLI 核心（当前）

- [ ] UCI 协议通信模块
- [ ] 招法转换模块
- [ ] 对局管理模块
- [ ] CLI 命令实现
- [ ] 棋盘图片生成

### Phase 2: Skill 封装

#### Session 机制设计

采用 **CLI 内部持久化** 方案，Session 与对局维度绑定：

```
~/.blind-xiangqi/sessions/
├── session_abc123.json    # session 元数据
└── session_def456.json
```

**Session 文件格式**：
```json
{
  "session_id": "abc123",
  "game_file": "games/2026-05-02/18-21_red_lv5.xqi",
  "created_at": "2026-05-02T18:21:00+08:00",
  "last_activity": "2026-05-02T18:35:00+08:00",
  "status": "active",
  "context": {
    "user_id": "feishu_user_001",
    "channel_id": "group_xyz"
  }
}
```

#### CLI 命令扩展（Session 支持）

```bash
# 新对局自动创建 session
blind-xiangqi play --color red --level 5
# 输出: Session: abc123 已创建

# 继续对局
blind-xiangqi continue abc123

# 输入招法
blind-xiangqi move abc123 "炮二平五"
# 输出: AI: 马8进7

# 查看/结束 session
blind-xiangqi status abc123
blind-xiangqi quit abc123
```

#### Skill 接口规范

**输入**：
```yaml
inputs:
  action: new | continue | move | status | quit | history | show
  session_id: string (可选，new 时无需)
  move: string (可选，仅 move action 需要)
  options:
    color: red | black
    level: 1-10
```

**输出**：
```yaml
outputs:
  status: success | error | game_over
  session_id: string (new action 返回)
  message: string (中文描述)
  ai_move: string (可选，AI 回应招法)
  image_path: string (可选，棋盘图片路径)
  game_result: string (可选，胜负结果)
```

#### 开发任务清单

- [ ] Session 管理模块实现
- [ ] CLI 命令扩展（continue/move/status）
- [ ] OpenClaw Skill 定义
- [ ] 飞书消息格式适配（SVG → PNG 转换）

### Phase 3: 增强功能（可选）

- [ ] 开局库集成
- [ ] 对局统计分析
- [ ] 多引擎支持

---

## 11. 参考资料

- Pikafish: https://github.com/official-pikafish/Pikafish
- xiangqi-setup: https://github.com/hartwork/xiangqi-setup
- UCI 协议: https://github.com/official-pikafish/Pikafish/wiki/UCI-&-Commands
- 象棋规则: https://en.wikipedia.org/wiki/Xiangqi

---

*文档完成于 2026-05-02*