---
name: xiangqi-partner
description: 中国象棋盲棋对弈助手。当用户想下象棋、盲棋练习、对弈时使用此skill。触发词包括：下棋、象棋、盲棋、对弈、走棋、棋局、开局。即使用户没有明确说"盲棋"，只要提到下象棋相关的需求，就应该使用此skill。
---

# 盲棋对弈助手

帮助用户进行中国象棋盲棋练习，通过自然语言交互完成对弈。

> **变量说明**：`$SKILL_DIR` = 本 skill 所在目录

## 启动方式

```bash
cd $SKILL_DIR && scripts/xiangqi.sh <命令> [参数]
```

---

## 常用命令详解

### create - 创建棋局

**入参**：
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-c, --color` | 执方：`red`(红) 或 `black`(黑) | 从 `.env` 读取 |
| `-l, --level` | 难度等级：1-10 | 从 `.env` 读取 |

**示例**：
```bash
cd $SKILL_DIR && scripts/xiangqi.sh create -c red -l 5
cd $SKILL_DIR && scripts/xiangqi.sh create  # 使用配置文件默认值
```

**输出**：
```
执红方，难度5级，开始对局
GAME_ID:2026-05-04/2026-05-04_17-35_red_lv5.xqi
```

---

### move - 走棋

**入参**：
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `move` | 中文招法（必填） | - |
| `-g, --game-id` | 对局ID：`latest`、`#N`、路径 | `latest` |

**示例**：
```bash
cd $SKILL_DIR && scripts/xiangqi.sh move "炮二平五" -g latest
cd $SKILL_DIR && scripts/xiangqi.sh move "炮2平5" -g "#1"
```

**输出**：
```
🎯 用户：炮二平五 【将军】
🤖 AI：士四进五
```

**注意**：`#N` 需用引号，如 `-g "#1"`

---

### undo - 悔棋

**入参**：
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-g, --game-id` | 对局ID | `latest` |
| `-s, --steps` | 回退回合数（1回合=用户+AI各一步） | `1` |

**示例**：
```bash
cd $SKILL_DIR && scripts/xiangqi.sh undo -g latest -s 2
```

**输出**：
```
已回退到第 3 回合
```

---

### status - 查看状态

**入参**：
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-g, --game-id` | 对局ID | `latest` |

**示例**：
```bash
cd $SKILL_DIR && scripts/xiangqi.sh status -g latest
```

**输出**：
```
📍 当前：红方行棋 
回合数：5
招法记录：
1. 炮二平五  士四进五
2. 马二进三  炮八平五
...
```

---

### list - 对局列表

**入参**：
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-n, --limit` | 显示数量 | `10` |
| `-d, --days` | 查看最近N天的对局 | `0`（今天） |

**示例**：
```bash
cd $SKILL_DIR && scripts/xiangqi.sh list              # 最近10局
cd $SKILL_DIR && scripts/xiangqi.sh list -d 0         # 今天的对局
cd $SKILL_DIR && scripts/xiangqi.sh list -d 7         # 最近7天的对局
cd $SKILL_DIR && scripts/xiangqi.sh list -n 5 -d 3    # 最近3天，最多5局
```

**输出**：
```
序号 | 对局ID | 执方 | 难度 | 结果 | 步数
--------------------------------------------------
#1  | 2026-05-04/xxx.xqi | 红 | Lv3 | 进行中 | 5回合
#2  | 2026-05-04/yyy.xqi | 黑 | Lv5 | 负 | 20回合
...
```

**说明**：序号 `#N` 用于其他命令引用，如 `load -g "#1"`

---

### board - 棋盘图片

**入参**：
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-g, --game-id` | 对局ID | `latest` |
| `-o, --output` | 输出路径（可选） | 自动生成 |

**示例**：
```bash
cd $SKILL_DIR && scripts/xiangqi.sh board -g latest
```

**输出**：
```
棋盘图片已生成: /home/user/.blind-xiangqi/images/board_xxx.svg
BOARD_PATH:/home/user/.blind-xiangqi/images/board_xxx.svg
```

**后续**：用 `Read` 工具读取 SVG 路径展示给用户

---

### load - 加载对局

**入参**：
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-g, --game-id` | 对局ID：`latest`、`#N`、路径 | `latest` |
| `-m, --move-index` | 从指定回合开始（可选） | 从头开始 |

**示例**：
```bash
cd $SKILL_DIR && scripts/xiangqi.sh load -g "#1"
cd $SKILL_DIR && scripts/xiangqi.sh load -g "#2" -m 10  # 从第10回合开始
```

**输出**：
```
加载对局: 2026-05-04/xxx.xqi
执红方，难度3级
当前第 5 回合
招法记录：
1. 炮二平五  士四进五
...
```

---

### resign - 认输

**入参**：
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-g, --game-id` | 对局ID | `latest` |

**示例**：
```bash
cd $SKILL_DIR && scripts/xiangqi.sh resign -g latest
```

**输出**：
```
红方认输！黑方(AI)获胜
```

---

### config - 配置管理

**入参**：
| 参数 | 说明 |
|------|------|
| `-s, --show` | 显示所有配置 |
| `-k, --key` | 配置键名 |
| `-v, --value` | 配置值 |

**可配置项**：
| 键名 | 说明 | 类型 |
|------|------|------|
| `DEFAULT_PLAYER_COLOR` | 默认执方 | `red/black` |
| `DEFAULT_LEVEL` | 默认难度 | `1-10` |

**示例**：
```bash
# 显示配置
cd $SKILL_DIR && scripts/xiangqi.sh config --show

# 修改默认难度
cd $SKILL_DIR && scripts/xiangqi.sh config -k DEFAULT_LEVEL -v 5
```

**输出**：
```
# config --show
当前配置:
  PYTHON_INTERPRETER = ~/miniconda3/envs/auto-dev/bin/python
  GAME_STORAGE_DIR = ~/.blind-xiangqi/games
  DEFAULT_PLAYER_COLOR = red
  DEFAULT_LEVEL = 3

# config -k DEFAULT_LEVEL -v 5
已更新并保存 DEFAULT_LEVEL = 5
CONFIG_UPDATED:DEFAULT_LEVEL=5
```

---

## game_id 引用方式

| 方式 | 说明 | 示例 |
|------|------|------|
| `latest` | 最新对局（按修改时间） | `-g latest` |
| `#N` | 列表序号（需引号） | `-g "#1"` |
| 路径 | 对局文件路径 | `-g 2026-05-04/xxx.xqi` |

---

## 输出原则

**直接返回程序输出，不做额外补充。**

- 执行命令后，直接展示程序返回的内容
- 不添加"轮到你走棋"、"⚠️ 提示"等额外说明
- 不对招法做解释或点评

---

## 招法纠错

用户输入可能包含错字，需根据象棋规则自动纠错：

**常见错字映射**：

| 类型 | 错字示例 | 正确字 |
|------|---------|--------|
| 棋子 | 马、琪、骐 | 马 |
| 棋子 | 炮、跑、泡 | 炮 |
| 棋子 | 车、居、拘 | 车 |
| 棋子 | 兵、宾、冰 | 兵 |
| 棋子 | 仕、士、士 | 仕（红）/ 士（黑）|
| 棋子 | 相、象、像 | 相（红）/ 象（黑）|
| 棋子 | 帅、率、师 | 帅 |
| 列号（中文）| 一、壹、乙 | 一 |
| 列号（中文）| 二、贰、两 | 二 |
| 列号（中文）| 三、叁、散 | 三 |
| 列号（中文）| 四、肆、死 | 四 |
| 列号（中文）| 五、伍、吴、无 | 五 |
| 列号（中文）| 六、陆、留 | 六 |
| 列号（中文）| 七、柒、气、妻 | 七 |
| 列号（中文）| 八、捌、吧 | 八 |
| 列号（中文）| 九、玖、久 | 九 |
| 动作 | 平、屏、评 | 平 |
| 动作 | 进、近、金 | 进 |
| 动作 | 退、腿、推 | 退 |

**纠错流程**：
1. 识别用户输入中的错字
2. 根据映射表转换为正确字
3. 验证纠错后的招法是否符合象棋规则（该棋子是否存在、能否走到目标位置）
4. 若纠错后仍无法解析，向用户确认原输入

**示例**：
- 用户输入 `马吴进琪` → 纠错为 `马五进七`
- 用户输入 `跑2平5` → 红方纠错为 `炮二平五`，黑方纠错为 `炮2平5`
- 用户输入 `车八进六`（执黑方）→ 纠错为 `车8进6`

---

## 招法格式

基于 cchess 库，支持多种格式：

**基本格式**：`棋子+列号+动作+目标`

| 组成 | 说明 | 示例 |
|------|------|------|
| 棋子 | 车、马、炮、兵、仕、相、帅 | 炮 |
| 列号 | 棋子所在列 | 二、2 |
| 动作 | 平、进、退 | 平 |
| 目标 | 目标位置 | 五、5 |

**列号格式兼容**：
| 执方 | 支持格式 | 示例 |
|------|---------|------|
| 红方 | 中文数字（一～九）或阿拉伯数字（1-9） | `炮二平五`、`炮2平5` |
| 黑方 | 阿拉伯数字（1-9） | `炮8平5` |

**完整示例**：
- `炮二平五` / `炮2平5` - 红方炮从第2列平到第5列
- `马八进七` / `马8进7` - 红方马从第8列进到第7列
- `车一进一` / `车1进1` - 红方车从第1列前进1步
- `炮8平5` - 黑方炮从第8列平到第5列

**特殊提示**：
- `【将军】` - 走棋后将军对方
- `【被将军】` - AI走棋后将军用户

---

## 交互示例

**用户**: 我想下棋
**AI**: [执行 `scripts/xiangqi.sh config --show` 和 `scripts/xiangqi.sh list -d 0`]
[直接展示程序输出]

**用户**: 红方，难度5
**AI**: [执行 `scripts/xiangqi.sh create -c red -l 5`]
执红方，难度5级，开始对局

**用户**: 炮二平五
**AI**: [执行 `scripts/xiangqi.sh move "炮二平五" -g latest`]
🎯 用户：炮二平五
🤖 AI：炮8平5

**用户**: 马吴进琪
**AI**: [识别错字，纠错为 `马五进七`，执行 `scripts/xiangqi.sh move "马五进七" -g latest`]
🎯 用户：马五进七
🤖 AI：xxx

**用户**: 悔棋
**AI**: [执行 `scripts/xiangqi.sh undo -g latest -s 1`]
已回退到第 0 回合

**用户**: 看棋盘
**AI**: [执行 `scripts/xiangqi.sh board -g latest`，获取 BOARD_PATH，然后 Read 展示 SVG]

**用户**: 最近3天的对局
**AI**: [执行 `scripts/xiangqi.sh list -d 3`]

**用户**: 默认难度改成5
**AI**: [执行 `scripts/xiangqi.sh config -k DEFAULT_LEVEL -v 5`]
已更新并保存 DEFAULT_LEVEL = 5

---

## 注意事项

1. 每次走棋自动保存对局
2. 同一对局难度保持一致（从文件读取）
3. 配置修改持久化到 `xiangqi.env`
4. 棋盘图片为 SVG 格式，用 Read 工具展示
5. `#N` 引用需用引号：`-g "#1"`
6. 默认值从 `xiangqi.env` 读取，可通过 `config` 命令修改