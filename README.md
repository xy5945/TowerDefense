# 守护稚码王国

> 稚码园机器人编程 原创作品 · 暗黑魔幻 2D 塔防游戏
>
> **本作品由稚码园机器人编程团队完全原创设计开发，享有著作权，未经授权不得复制、修改或用于商业目的。**

![版本](https://img.shields.io/badge/version-v1.0.0-ffd700)
![Python](https://img.shields.io/badge/Python-3.8%2B-3776ab)
![pygame](https://img.shields.io/badge/pygame-2.0%2B-green)
![License](https://img.shields.io/badge/license-CC%20BY--NC%204.0-lightgrey)

---

## 这是什么

一款由 **Python + pygame** 编写的暗黑魔幻风格 2D 塔防游戏。10 关完整剧情，5 种防御塔 × 5 种敌人，含 Boss 多阶段战斗、毒液传染、护盾分享、穿透激光、隐身召唤等机制。

游戏名《守护稚码王国》取自机构名"稚码园"——寓意学员用代码守护自己的王国。

## 玩法概览

| 元素 | 详情 |
|---|---|
| **5 种防御塔** | 哨戒弩台(连射) · 霜寒尖塔(减速冻结) · 瘴毒祭坛(毒液传染) · 炼狱火炮(暴击重甲) · 奥术裂隙(穿透激光) |
| **5 种敌人** | 魔化步兵 · 暗影行者(加速光环) · 铁甲魔像(护盾分享) · 深渊领主(Boss) · 幽冥飞灵(直线飞行) |
| **10 关** | 边境村庄 → 幽暗森林 → 腐败沼泽 → 远古墓地 → 废弃堡垒 → 恶魔要塞 → 熔岩洞窟 → 暗影深渊 → 恐惧王座 → 地狱深渊 |
| **3 档难度** | 简单(敌人HP×0.7,无密语) · 普通(标准) · 困难(敌人HP×1.3,生命-5) |

### 塔 vs 兵种克制

```
弩台  →  杂兵群
冰塔  →  中速兵
毒塔  →  重甲群
火炮  →  重甲单体
激光  →  Boss / 隐身单位
```

### Boss 战（深渊领主）

- **每 7 秒** 减速最近的 2 座防御塔（持续 4 秒，攻速降至 70%）
- **血量 < 50%** 时进入 2 秒隐身 + 召唤 5 个增援

## 运行方式

### 系统要求
- Python 3.8 及以上
- pygame ≥ 2.0

### 安装与启动

```bash
# 1. 克隆或下载代码
git clone <repo-url>
cd TowerDefense

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动游戏
python main.py
```

### 打包为 exe

```bash
pyinstaller main.spec
# 产物在 dist/main.exe（带 assets 资源）
```

## 项目结构

```
TowerDefense/
├── main.py              # 入口：pygame 初始化、主循环、事件分发
├── game/                # 游戏逻辑包
│   ├── config.py        # 配置：屏幕/网格常量 + 10 关数据 + 塔/敌人 dataclass
│   ├── utils.py         # 资源路径、网格对齐、绘图辅助
│   ├── assets.py        # AudioManager / ImageManager / FontManager
│   ├── effects.py       # ParticlePool(600) + LaserManager(30) 对象池
│   ├── bullet.py        # 追踪型 Bullet + 拖尾粒子
│   ├── enemy.py         # 敌人 + 状态效果 + Boss AI
│   ├── tower.py         # 防御塔：目标选择、旋转、射击、3 级升级
│   ├── wave.py          # 波次生成 + 特殊兵种预告文案
│   ├── game.py          # Game 主控：状态机、输入、生命周期
│   └── renderer.py      # 所有绘图：菜单/路径/侧栏/UI
├── data/
│   └── levels.json      # 10 关路径坐标（带内置回退）
├── assets/              # 资源（背景图、敌人3帧动画、塔精灵、BGM、音效、字体）
├── main.spec            # PyInstaller 打包配置
└── requirements.txt     # pygame>=2.0.0
```

详细架构说明见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

## 项目特色

本项目由稚码园机器人编程团队独立设计开发，注重工程化与可玩性：

- **全中文注释 + 类型提示**：代码关键路径、类、核心方法均有说明
- **配置外置**：`levels.json` 改动路径无需改代码
- **单一职责**：渲染与逻辑完全分离（`renderer.py` vs `game.py`）
- **数据驱动**：核心数据结构（`TowerStats`/`EnemyStats`/`PathStyle`）使用 `@dataclass`
- **性能优化**：粒子、激光用环形索引复用，避免运行时 GC

## 研发故事

《守护稚码王国》是稚码园机器人编程团队为学员打造的原创 IP，旨在让孩子在沉浸式的游戏体验中感受代码与创造的乐趣。

整个作品由稚码园团队独立完成，覆盖美术设计、音乐创作、玩法开发与平衡调优，包含 3500+ 行代码、11 个模块。每一关路径、每种敌人 AI、每个 Boss 机制均由稚码园团队原创设计与反复打磨。

## 我们的承诺

- **完全原创**：所有代码、美术、音乐均由稚码园机器人编程团队原创设计
- **学员友好**：游戏与配套代码面向学员开放，可作为 Python + pygame 教学示例参考
- **持续迭代**：项目会持续更新更多关卡与机制

## 版权

```
稚码园机器人编程

本作品为稚码园机器人编程团队完全原创设计开发，享有著作权。
所有代码、美术、音乐均为原创。
未经书面授权，不得用于任何商业目的。
完整许可条款详见 [LICENSE](LICENSE)。
```

---

**稚码园机器人编程** — 用游戏点燃孩子的代码梦想