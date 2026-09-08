"""
波次生成模块 - 从 Game 类中提取的敌人生成逻辑。
"""
import random
from typing import List, Tuple, Optional

from game.config import CONFIG


# 波次条目: (enemy_type, hp, speed, reward, skill)
WaveEntry = Tuple[str, float, float, int, Optional[str]]


def _level_wave_counts(level: int, wave: int) -> Tuple[int, int, int, int, int]:
    """根据关卡（level）和波次（wave）返回各兵种数量: (normal, fast, tank, boss, flying)。

    10 关主题:
      1 边境村庄   - 教学关：纯步兵；第10波加 1 个 Boss
      2 幽暗森林   - 引入潜行者；第10波加 1 个 Boss
      3 腐败沼泽   - 引入坦克（部分带 shield 技能）
      4 远古墓地   - 坦克群，密集护盾
      5 废弃堡垒   - 首次出现 Boss（多只）
      6 恶魔要塞   - 飞灵入侵（空中 50%+）
      7 熔岩洞窟   - 全兵种混编（无 Boss）
      8 暗影深渊   - 多 Boss + 全兵种
      9 恐惧王座   - 密集波次（每波 ≥3 坦克 + ≥3 飞灵）
      10 地狱深渊  - 终局：极端密度 + 多 Boss + 多飞灵
    """
    total = 4 + wave * 3

    if level == 1:
        # 教学：纯步兵，最后波加 Boss
        n, f, t, b, fl = total, 0, 0, 0, 0
        if wave >= 10:
            b = 1
    elif level == 2:
        # 潜行者首秀：第 4 波起出现，最后波加 Boss
        f = max(0, wave - 3)
        n, t, b, fl = max(0, total - f), 0, 0, 0
        if wave >= 10:
            b = 1
    elif level == 3:
        # 坦克首秀：第 5 波起出现（部分带 shield）
        f = max(0, wave - 3)
        t = max(0, wave - 5)
        n, b, fl = max(0, total - f - t), 0, 0
    elif level == 4:
        # 坦克群：坦克为主
        t = max(0, wave - 1)
        n = max(0, total - t)
        f, b, fl = 0, 0, 0
    elif level == 5:
        # 首次 Boss
        f = max(0, wave - 3)
        t = max(0, wave - 5)
        b = max(0, wave - 8)
        n = max(0, total - f - t - b)
        fl = 0
    elif level == 6:
        # 飞灵入侵：第 3 波起飞灵、第 4 波起坦克
        fl = max(0, wave - 2)
        t = max(0, wave - 4)
        n = max(0, total - fl - t)
        f, b = 0, 0
    elif level == 7:
        # 全兵种混编（无 Boss）
        f = max(0, wave - 2)
        t = max(0, wave - 4)
        fl = max(0, wave - 3)
        n = max(0, total - f - t - fl)
        b = 0
    elif level == 8:
        # 暗影深渊：多 Boss + 全兵种
        f = max(0, wave - 2)
        t = max(0, wave - 3)
        fl = max(0, wave - 4)
        b = max(0, wave - 7)
        n = max(0, total - f - t - fl - b)
    elif level == 9:
        # 恐惧王座：密集 Boss + 高 HP（每波 ≥ 1 坦克 ≥ 1 飞灵）
        t = max(1, wave - 2)
        fl = max(1, wave - 3)
        f = max(0, wave - 3)
        b = max(0, wave - 5)
        n = max(0, total - f - t - fl - b)
    elif level >= 10:
        # 地狱深渊：终局，极端密度
        f = max(1, wave - 1)
        t = max(1, wave - 2)
        fl = max(1, wave - 2)
        b = max(0, wave - 4)
        n = max(0, total - f - t - fl - b)
    else:
        n, f, t, b, fl = total, 0, 0, 0, 0

    return n, f, t, b, fl


def generate_wave(level: int, wave: int) -> List[WaveEntry]:
    """根据关卡（level）和波次（wave）生成敌人队列。"""
    normal_count, fast_count, tank_count, boss_count, flying_count = _level_wave_counts(level, wave)

    level_hp_mult = 1 + 0.2 * (level - 1)
    level_sp_mult = 1 + 0.05 * (level - 1)
    hp_mult = (1 + 0.4 * (wave - 1)) * level_hp_mult
    sp_mult = (1 + 0.03 * (wave - 1)) * level_sp_mult
    rw_mult = 1 + 0.1 * wave

    # 技能上限：随关卡 + 波次递增，关 4+ 坦克技能 100%
    if level <= 2:
        max_skill = 0 if wave <= 3 else 2
    elif level <= 4:
        max_skill = 3 if wave <= 5 else 5
    elif level <= 7:
        max_skill = 2 if wave <= 4 else 5
    else:
        max_skill = 4 if wave <= 5 else 6

    queue: List[WaveEntry] = []

    # 普通敌人
    b = CONFIG.enemy_base['normal']
    for _ in range(normal_count):
        queue.append(('normal', b.hp * hp_mult, b.speed * sp_mult, int(b.reward * rw_mult), None))

    # 快速敌人
    skill_count = 0
    b = CONFIG.enemy_base['fast']
    for _ in range(fast_count):
        skill: Optional[str] = None
        if skill_count < max_skill and random.random() < 0.7:
            skill = 'boost_aura'
            skill_count += 1
        queue.append(('fast', b.hp * hp_mult, b.speed * sp_mult, int(b.reward * rw_mult), skill))

    # 重甲敌人
    b = CONFIG.enemy_base['tank']
    for _ in range(tank_count):
        skill = None
        # 关卡 3+ 的坦克有更高概率带 shield 技能
        skill_chance = 0.7 if level >= 3 else 0.5
        if skill_count < max_skill and random.random() < skill_chance:
            skill = 'shield'
            skill_count += 1
        queue.append(('tank', b.hp * hp_mult, b.speed * sp_mult, int(b.reward * rw_mult), skill))

    # Boss
    b = CONFIG.enemy_base['boss']
    for _ in range(boss_count):
        queue.append(('boss', b.hp * hp_mult, b.speed * sp_mult, int(b.reward * rw_mult), 'boss'))

    # 飞行敌人
    b = CONFIG.enemy_base['flying']
    for _ in range(flying_count):
        queue.append(('flying', b.hp * hp_mult, b.speed * sp_mult, int(b.reward * rw_mult), None))

    random.shuffle(queue)
    return queue


def generate_boss_summon(wave: int) -> List[WaveEntry]:
    """Boss 半血召唤的额外敌人。"""
    hp_mult = 1 + 0.4 * (wave - 1)
    sp_mult = 1 + 0.03 * (wave - 1)
    rw_mult = 1 + 0.1 * wave

    entries: List[WaveEntry] = []
    for i in range(5):
        if i < 2:
            b = CONFIG.enemy_base['fast']
            speed = b.speed * CONFIG.boss_summon_speed_mult * sp_mult
            entries.append(('fast', b.hp * hp_mult, speed, int(b.reward * rw_mult), 'boost_aura'))
        else:
            b = CONFIG.enemy_base['normal']
            entries.append(('normal', b.hp * hp_mult, b.speed * sp_mult, int(b.reward * rw_mult), None))
    return entries


# 敌人在预告提示中的中文显示名（按 type）
_ENEMY_DISPLAY_NAME = {
    'normal': '魔化步兵',
    'fast':   '暗影行者',
    'tank':   '铁甲魔像',
    'boss':   '深渊领主',
    'flying': '幽冥飞灵',
}

# 普通小兵（不预告具体数量）；其他类型都算"特殊"
_SPECIAL_TYPES = ('fast', 'tank', 'boss', 'flying')

# 技能名 → 简短标签
_SKILL_LABEL = {
    'shield':     '·护盾',
    'boost_aura': '·加速',
}


def format_wave_preview(queue: List[WaveEntry]) -> str:
    """把生成出来的波次队列压缩成可读的预告文字。

    规则（每个兵种单独一行）：
    - 普通小兵（normal）不出现任何文字（无数量、无名字）
    - 特殊兵种（fast/tank/boss/flying）只要队列里有，至少出现一次就单独一行展示名字与属性标签
    - 带技能者在名字后追加标签（·护盾 / ·加速）；同一种类带不带技能视为两个不同行

    例子：
    - 队列含飞行+暗影行者(无技能)+暗影行者(加速)+铁甲魔像(护盾)+Boss：
      输出三行：暗影行者\\n暗影行者·加速\\n铁甲魔像·护盾\\n深渊领主\\n幽冥飞灵
    - 整波只有普通小兵时返回空串（调用方据此跳过预告）
    """
    if not queue:
        return ''

    # 按 (type, skill_label) 维度去重保留顺序
    seen: list = []
    for entry in queue:
        etype, _, _, _, skill = entry
        if etype == 'normal':
            continue
        label = _SKILL_LABEL.get(skill, '')
        key = (etype, label)
        if key not in seen:
            seen.append(key)

    if not seen:
        return ''

    # 按显示顺序：fast → tank → boss → flying；同 type 内无技能在前、带技能在后
    order = ('fast', 'tank', 'boss', 'flying')
    sorted_keys = sorted(
        seen,
        key=lambda k: (order.index(k[0]), 0 if k[1] == '' else 1, k[1])
    )

    lines = []
    for etype, label in sorted_keys:
        name = _ENEMY_DISPLAY_NAME[etype]
        lines.append(f"{name}{label}")
    return '\n'.join(lines)


def wave_preview_is_special_only(queue: List[WaveEntry]) -> bool:
    """返回 True 表示该波次只有普通小兵（玩家不需要操心布局）。"""
    return all(e[0] == 'normal' for e in queue)
