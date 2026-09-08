"""
配置模块 - 使用 dataclass 替代原始字典，提供类型安全和清晰的结构定义。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import json
import os

# ---------- 屏幕与地图常量 ----------
WIDTH: int = 960
HEIGHT: int = 600
SIDE_PANEL: int = 240
MAP_W: int = WIDTH - SIDE_PANEL
GRID_SIZE: int = 40

# ---------- 游戏锁定日期 ----------
LOCK_DATE = "2026-09-11"

# ---------- 关卡名称（1-10关） ----------
LEVEL_NAMES: List[str] = [
    "边境村庄",
    "幽暗森林",
    "腐败沼泽",
    "远古墓地",
    "废弃堡垒",
    "恶魔要塞",
    "熔岩洞窟",
    "暗影深渊",
    "恐惧王座",
    "地狱深渊",
]


# ---------- 星级评价 ----------
# 漏怪数 → 星级阈值：漏 0→3星，漏 1~5→2星，漏 6~10→1星，漏 >10→0星
STAR_LEAK_MAX: List[int] = [0, 5, 10]
# 金币加成系数：奖励 = 星数 × 关数 × 系数
STAR_REWARD_COEFF: int = 20
# 每关标准用时（秒），索引 0 对应第 1 关：第 1 关 240s，之后每关 +20s
STAR_PAR_TIMES: List[float] = [240, 260, 280, 300, 320, 340, 360, 380, 400, 420]
# 用时星级倍率：≤1.0×par→3星，≤1.5×par→2星，≤2.5×par→1星，否则 0 星
STAR_TIME_MULT: List[float] = [1.0, 1.5, 2.5]


def calc_star_countdown(elapsed: float, level: int) -> Tuple[int, float]:
    """游戏内星级倒计时。

    返回 (目标星级, 剩余秒数)：
    - 先倒计 3 星时间，归零后开始倒计 2 星剩余时间，再归零倒计 1 星；
    - 1 星时间也走完后返回 (0, 0.0)，不再倒计时。
    """
    par = STAR_PAR_TIMES[min(level, len(STAR_PAR_TIMES)) - 1]
    t3 = par * STAR_TIME_MULT[0]
    t2 = par * STAR_TIME_MULT[1]
    t1 = par * STAR_TIME_MULT[2]

    if elapsed < t3:
        return 3, max(0.0, t3 - elapsed)
    if elapsed < t2:
        return 2, max(0.0, t2 - elapsed)
    if elapsed < t1:
        return 1, max(0.0, t1 - elapsed)
    return 0, 0.0


def calc_star_rating(leaked: int, elapsed: float, level: int) -> Tuple[int, int, int]:
    """根据漏怪数与用时计算星级。

    返回 (最终星级, 漏怪星级, 用时星级)。
    最终星级取两者较小值——漏怪和用时都要达标才能拿满星。
    """
    # 漏怪评级
    if leaked <= STAR_LEAK_MAX[0]:
        leak_stars = 3
    elif leaked <= STAR_LEAK_MAX[1]:
        leak_stars = 2
    elif leaked <= STAR_LEAK_MAX[2]:
        leak_stars = 1
    else:
        leak_stars = 0

    # 用时评级（相对本关标准用时）
    par = STAR_PAR_TIMES[min(level, len(STAR_PAR_TIMES)) - 1]
    if elapsed <= par * STAR_TIME_MULT[0]:
        time_stars = 3
    elif elapsed <= par * STAR_TIME_MULT[1]:
        time_stars = 2
    elif elapsed <= par * STAR_TIME_MULT[2]:
        time_stars = 1
    else:
        time_stars = 0

    return min(leak_stars, time_stars), leak_stars, time_stars


@dataclass
class DifficultyConfig:
    """难度配置：影响敌人属性、起手资源、通关后奖励。"""
    name: str                      # 显示名
    enemy_hp_mult: float           # 敌人 HP 倍率
    enemy_speed_mult: float        # 敌人速度倍率
    initial_money_bonus: int       # 起手金币加成
    lives_bonus: int               # 生命数加成
    show_secret_phrase: bool       # 通关后是否显示老师的隐藏奖励密语
    secret_phrase: str = ""        # 该难度对应的密语文本（简单模式为空）


# 三档难度（顺序：简单 → 普通 → 困难）
DIFFICULTY_CONFIGS: Dict[str, DifficultyConfig] = {
    'easy': DifficultyConfig(
        name='简单',
        enemy_hp_mult=0.8,
        enemy_speed_mult=0.9,
        initial_money_bonus=50,
        lives_bonus=5,
        show_secret_phrase=False,  # 简单模式通关不显示密语
        secret_phrase="",
    ),
    'normal': DifficultyConfig(
        name='普通',
        enemy_hp_mult=1.0,
        enemy_speed_mult=1.0,
        initial_money_bonus=0,
        lives_bonus=0,
        show_secret_phrase=True,
        secret_phrase="Stay hungry, stay foolish！",
    ),
    'hard': DifficultyConfig(
        name='困难',
        enemy_hp_mult=1.2,
        enemy_speed_mult=1.1,
        initial_money_bonus=0,
        lives_bonus=-5,
        show_secret_phrase=True,
        secret_phrase=(
            "When something is important enough, "
            "you do it even if the odds are not in your favor."
        ),
    ),
}


@dataclass
class TowerStats:
    """防御塔基础属性"""
    name: str
    cost: int
    range: int
    damage: int
    fire_rate: float
    color: Tuple[int, int, int]
    rapid_fire: bool = False
    crit_chance: float = 0.0
    special: Optional[str] = None
    freeze_chance: float = 0.0
    laser: bool = False
    venom: bool = False

    # ---- v1.1 平衡性扩展字段 ----
    # 连射加速：连续命中同一目标，每次 +10%，封顶 (max_rapid_count * 10%)。
    # 弩塔 = 3 (上限 +30%)；激光过载 = 5 (上限 +50%)；其他默认 5。
    max_rapid_count: int = 5
    # 火炮暴击伤害倍率（默认 2.0，v1.1 调到 2.5）
    crit_damage_mult: float = 2.0
    # 火炮溅射半径（0 表示无溅射）
    splash_radius: int = 0
    # 火炮溅射伤害倍率（相对 damage）
    splash_damage_mult: float = 0.5
    # 冰塔霜冻易伤：被减速敌人受到的伤害加成
    slow_vuln_bonus: float = 0.0
    # 冰塔霜冻易伤：被冻结敌人受到的伤害加成
    freeze_vuln_bonus: float = 0.0
    # 毒塔对飞行敌人的伤害加成
    venom_flying_bonus: float = 0.0


@dataclass
class EnemyStats:
    """敌人基础属性"""
    hp: int
    speed: int
    reward: int
    color: Tuple[int, int, int]
    radius: int
    name: str = ""
    flying: bool = False


@dataclass
class GameConfig:
    """全局游戏配置，替代原始 CONFIG 字典"""
    width: int = WIDTH
    height: int = HEIGHT
    side_panel: int = SIDE_PANEL
    map_w: int = MAP_W
    grid_size: int = GRID_SIZE
    initial_money: int = 250
    lives: int = 20

    # 技能与 Boss 相关
    skill_range: int = 60
    shield_percent: float = 0.3
    boss_slow_factor: float = 0.7
    boss_slow_duration: float = 4.0
    boss_slow_cd: float = 7.0
    boss_summon_speed_mult: float = 1.5

    tower_types: Dict[str, TowerStats] = field(default_factory=dict)
    upgrade_costs: Dict[str, List[int]] = field(default_factory=dict)
    enemy_base: Dict[str, EnemyStats] = field(default_factory=dict)

    def __post_init__(self):
        if not self.tower_types:
            self.tower_types = _default_tower_types()
        if not self.upgrade_costs:
            self.upgrade_costs = _default_upgrade_costs()
        if not self.enemy_base:
            self.enemy_base = _default_enemy_base()


@dataclass
class PathStyle:
    """关卡路径视觉风格"""
    path_color: Tuple[int, int, int]
    border_color: Tuple[int, int, int]
    path_width: int = 30
    border_width: int = 2
    glow_color: Optional[Tuple[int, int, int]] = None


LEVEL_PATH_STYLES: List[PathStyle] = [
    PathStyle(path_color=(160, 140, 110), border_color=(120, 100, 80)),                                          # 1 边境村庄 - 泥土路
    PathStyle(path_color=(90, 110, 75), border_color=(60, 80, 50)),                                                # 2 幽暗森林 - 苔藓路
    PathStyle(path_color=(100, 115, 85), border_color=(70, 85, 60), glow_color=(80, 140, 60)),                     # 3 腐败沼泽 - 毒沼路
    PathStyle(path_color=(130, 130, 140), border_color=(100, 100, 110), glow_color=(120, 160, 200)),               # 4 远古墓地 - 石板路
    PathStyle(path_color=(140, 135, 125), border_color=(110, 105, 95)),                                             # 5 废弃堡垒 - 碎砖路
    PathStyle(path_color=(80, 50, 45), border_color=(50, 30, 25), glow_color=(200, 80, 30)),                       # 6 恶魔要塞 - 黑曜石裂路
    PathStyle(path_color=(90, 40, 20), border_color=(60, 25, 10), glow_color=(255, 120, 30), path_width=28),       # 7 熔岩洞窟 - 岩浆裂纹
    PathStyle(path_color=(40, 25, 60), border_color=(60, 35, 80), glow_color=(150, 80, 200), path_width=26),       # 8 暗影深渊 - 虚空裂痕
    PathStyle(path_color=(70, 25, 25), border_color=(45, 15, 15), glow_color=(180, 40, 40)),                        # 9 恐惧王座 - 血石路
    PathStyle(path_color=(50, 20, 10), border_color=(30, 10, 5), glow_color=(220, 100, 20), path_width=26),        # 10 地狱深渊 - 地狱裂缝
]


def _default_tower_types() -> Dict[str, TowerStats]:
    return {
        # 哨戒弩台 — 早期清杂兵主力：便宜、攻速快、连射加速，
        # 但对小体型/有护盾敌人伤害大幅削减。射程中等。
        'machine': TowerStats(
            name='哨戒弩台', cost=80, range=100, damage=8, fire_rate=4,
            color=(255, 200, 0), rapid_fire=True, max_rapid_count=3,
        ),
        # 炼狱火炮 — 单体爆发：伤害高、暴击强、附带小范围溅射；
        # 攻速慢，不能打飞行敌人。
        'cannon': TowerStats(
            name='炼狱火炮', cost=180, range=150, damage=50, fire_rate=1.0,
            color=(255, 80, 80), crit_chance=0.20,
            crit_damage_mult=2.5, splash_radius=35, splash_damage_mult=0.6,
        ),
        # 霜寒尖塔 — 控制辅助：输出低但给被减速/冻结的敌人提供易伤，
        # 配其他塔打伤害。不能打飞行敌人。
        'ice': TowerStats(
            name='霜寒尖塔', cost=100, range=110, damage=6, fire_rate=1.2,
            color=(0, 200, 255), special='slow', freeze_chance=0.15,
            slow_vuln_bonus=0.10, freeze_vuln_bonus=0.50,
        ),
        # 奥术裂隙 — Boss 终结者：射程远、伤害高、连续命中同一目标触发过载，
        # 穿透减伤 40%，无视隐身。
        'sniper': TowerStats(
            name='奥术裂隙', cost=250, range=250, damage=80, fire_rate=0.6,
            color=(160, 120, 255), laser=True, max_rapid_count=5,
        ),
        # 瘴毒祭坛 — AOE 群毒：毒伤持续 4s、可传染、无视护盾，
        # 对飞行敌人伤害 +50%，适合坦克群与飞灵。
        'venom': TowerStats(
            name='瘴毒祭坛', cost=120, range=130, damage=18, fire_rate=1.4,
            color=(0, 255, 0), venom=True, venom_flying_bonus=0.50,
        ),
    }


def _default_upgrade_costs() -> Dict[str, List[int]]:
    return {
        'machine': [120, 220],
        'ice': [150, 250],
        'cannon': [260, 380],
        'sniper': [350, 550],
        'venom': [180, 300],
    }


def _default_enemy_base() -> Dict[str, EnemyStats]:
    return {
        'normal': EnemyStats(hp=60, speed=60, reward=10, color=(255, 80, 80), radius=8, name="魔化步兵"),
        'fast': EnemyStats(hp=40, speed=100, reward=12, color=(255, 255, 0), radius=6, name="暗影行者"),
        'tank': EnemyStats(hp=150, speed=40, reward=25, color=(255, 140, 0), radius=12, name="铁甲魔像"),
        'boss': EnemyStats(hp=400, speed=50, reward=80, color=(180, 50, 200), radius=16, name="深渊领主"),
        'flying': EnemyStats(hp=60, speed=30, reward=20, color=(200, 200, 255), radius=10, name="幽冥飞灵", flying=True),
    }


def load_paths(data_dir: str) -> List[List[Tuple[int, int]]]:
    """
    从 JSON 文件加载关卡路径数据，替代硬编码的 PATH_TEMPLATES。
    """
    path_file = os.path.join(data_dir, "levels.json")
    try:
        with open(path_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        paths = []
        for level_path in data['levels']:
            paths.append([tuple(p) for p in level_path])
        return paths
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"加载关卡路径失败: {e}，使用内置默认路径")
        return _builtin_paths()


def _builtin_paths() -> List[List[Tuple[int, int]]]:
    """内置默认路径（原 PATH_TEMPLATES）"""
    return [
        [(0, 160), (160, 160), (160, 480), (560, 480), (560, 160), (720, 160)],
        [(0, 120), (200, 120), (200, 400), (520, 400), (520, 160), (720, 160)],
        [(0, 120), (160, 120), (160, 280), (320, 280), (320, 440), (480, 440), (480, 520), (720, 520)],
        [(0, 160), (120, 160), (120, 400), (240, 400), (240, 160), (360, 160), (360, 400), (480, 400), (480, 160), (720, 160)],
        [(0, 480), (160, 480), (160, 320), (320, 320), (320, 160), (480, 160), (480, 120), (720, 120)],
        [(0, 120), (160, 120), (160, 320), (320, 320), (320, 120), (480, 120), (480, 320), (640, 320), (640, 120), (720, 120)],
        [(0, 160), (560, 160), (560, 480), (160, 480), (160, 520), (720, 520)],
        [(0, 480), (640, 480), (640, 120), (160, 120), (160, 80), (720, 80)],
        [(0, 80), (200, 80), (200, 240), (400, 240), (400, 400), (560, 400), (560, 520), (720, 520)],
        [(0, 520), (200, 520), (200, 360), (400, 360), (400, 200), (560, 200), (560, 80), (720, 80)],
    ]


# ---------- 全局配置实例 ----------
CONFIG = GameConfig()
