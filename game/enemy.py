"""
敌人模块 - Enemy 类及其行为逻辑。
"""
import math
import random
from typing import List, Tuple, Optional

import pygame

from game.config import CONFIG
from game.assets import images
from game.utils import draw_transparent_circle, draw_glow

# 毒塔施加的轻微减速系数（0.8 = 减速 20%）
VENOM_SLOW_FACTOR = 0.8


class Enemy:
    """敌人实体，沿路径移动并拥有多种状态效果。"""

    def __init__(
        self,
        path: List[Tuple[int, int]],
        hp: float,
        speed: float,
        enemy_type: str,
        reward: int,
        skill: Optional[str] = None,
    ):
        self.path = path
        self.x, self.y = float(path[0][0]), float(path[0][1])
        self.path_index: int = 0
        self.hp: float = hp
        self.max_hp: float = hp
        self.speed: float = speed
        self.type: str = enemy_type
        self.reward: int = reward
        self.alive: bool = True
        self.reached_end: bool = False

        # 状态效果计时器
        self.boost_timer: float = 0.0
        self.boost_factor: float = 1.0
        self.venom_timer: float = 0.0
        self.venom_dps: float = 0.0
        self.venom_initial_dps: float = 0.0
        self.ice_slow_timer: float = 0.0
        self.ice_slow_factor: float = 1.0
        self.frozen_timer: float = 0.0
        self.hit_flash_timer: float = 0.0
        self.invisible_timer: float = 0.0

        # 基础属性
        base = CONFIG.enemy_base[enemy_type]
        self.radius: int = base.radius
        self.color: Tuple[int, int, int] = base.color
        self.skill: Optional[str] = skill
        self.flying: bool = base.flying

        # 护盾相关
        self.shield_hp: float = 0.0
        self.shield_cd: float = 0.0
        self.shield_max: float = 0.0
        self.absorbed_damage: float = 0.0
        self.shield_broken: bool = False
        self.shield_count: int = 0  # 护盾已触发次数，用于递减护盾量

        # Boss 相关
        self.slow_tower_cd: float = 0.0
        self.has_summoned: bool = False

        # 图片（多帧动画）
        self.image: Optional[pygame.Surface] = None
        self.frames: Optional[list] = None
        self.anim_frame: int = 0
        self.anim_timer: float = 0.0
        self.anim_speed: float = 0.15  # 每帧间隔秒数

        frames = images.get_enemy_frames(enemy_type)
        if frames is not None:
            diameter = self.radius * 4  # 2倍显示大小
            self.frames = [pygame.transform.scale(f, (diameter, diameter)) for f in frames]
            self.image = self.frames[0]
        else:
            # 回退：单图
            img = images.get_enemy_image(enemy_type)
            if img is not None:
                diameter = self.radius * 4
                self.image = pygame.transform.scale(img, (diameter, diameter))

        # 初始化特殊能力计时器
        if self.type == 'tank' and self.skill == 'shield':
            self.shield_cd = 5.0
        if self.type == 'boss':
            self.slow_tower_cd = CONFIG.boss_slow_cd

        # 飞行敌人走直线：从入口直飞路线出口
        if self.flying:
            end_x, end_y = path[-1]
            self.path = [(self.x, self.y), (float(end_x), float(end_y))]

        # 路径总长度与已走距离（用于塔目标选择的"最接近终点"优先级）
        self._path_length: float = 0.0
        for i in range(len(self.path) - 1):
            x1, y1 = self.path[i]
            x2, y2 = self.path[i + 1]
            self._path_length += math.hypot(x2 - x1, y2 - y1)
        self.distance_traveled: float = 0.0

    @property
    def progress(self) -> float:
        """沿路径的进度（0~1），用于塔选择最接近终点的目标。"""
        if self._path_length <= 0:
            return 0.0
        return min(1.0, self.distance_traveled / self._path_length)

    # ---------- 伤害与状态效果 ----------

    def take_damage(self, damage: float, damage_type: Optional[str] = None) -> None:
        # ---- v1.1 平衡：伤害进入时的减免/加成（应用于总伤害） ----
        # 飞行敌人：弩塔 / 激光伤害减半
        if self.flying and damage_type in ('machine', 'laser'):
            damage = max(1, int(damage * 0.5))

        # 弩塔：对潜行者（fast）伤害 -20%
        if damage_type == 'machine' and self.type == 'fast':
            damage = max(1, int(damage * 0.8))

        # 弩塔：对有护盾敌人伤害减半（弩箭打不穿盾）
        if damage_type == 'machine' and self.shield_hp > 0:
            damage = max(1, int(damage * 0.5))

        # 毒塔：对飞行敌人伤害 +50%（克制飞行）
        if damage_type == 'venom' and self.flying:
            damage = int(damage * 1.5)

        self.hit_flash_timer = 0.08

        if self.shield_hp > 0:
            if damage_type == 'venom':
                # 毒液无视护盾：破盾后仍打 HP（之前 return 跳过了 HP 伤害，是 bug）
                self.shield_hp = 0
                self.shield_broken = True
                # 不 return，继续往下扣 HP
            else:
                absorbed = min(damage, self.shield_hp)
                self.shield_hp -= absorbed
                if self.type == 'tank':
                    self.absorbed_damage += absorbed
                if self.shield_hp <= 0:
                    self.shield_broken = True
                    if self.type == 'tank' and self.absorbed_damage > 0:
                        # v1.1.5：破盾回血基础 80% → 50%；
                        # 中毒坦克回血 = 非中毒 × 60% = 30%，毒塔克制依然成立。
                        # 注意：只有坦克自己的盾破了才回血，被分享到队友身上的盾破了不回血。
                        base_ratio = 0.5
                        heal_ratio = base_ratio * (0.6 if self.venom_timer > 0 else 1.0)
                        heal = int(self.absorbed_damage * heal_ratio)
                        self.hp = min(self.max_hp, self.hp + heal)
                        self.absorbed_damage = 0
                damage -= absorbed

        # ---- 冰塔霜冻易伤：应用于实际扣血量（玩家感知层面） ----
        if damage > 0:
            if self.frozen_timer > 0:
                damage = int(damage * 1.5)   # 被冻结 +50%
            elif self.ice_slow_timer > 0:
                damage = int(damage * 1.1)   # 被减速 +10%
            self.hp -= damage
            if self.hp <= 0:
                self.hp = 0
                self.alive = False

    @property
    def is_slowed(self) -> bool:
        """是否处于减速状态（冰塔减速或毒塔减速）。"""
        return self.ice_slow_timer > 0 or self.venom_timer > 0

    def apply_ice_slow(self, duration: float, slow_factor: float = 0.5) -> None:
        self.ice_slow_timer = max(self.ice_slow_timer, duration)
        # 冰塔减速拥有最高优先级，取更强的减速
        if slow_factor < self.ice_slow_factor:
            self.ice_slow_factor = slow_factor

    def apply_freeze(self, duration: float = 0.5) -> None:
        self.frozen_timer = max(self.frozen_timer, duration)

    def apply_boost(self, duration: float, boost_factor: float = 1.5) -> None:
        if self.is_slowed:
            return
        self.boost_timer = max(self.boost_timer, duration)
        self.boost_factor = boost_factor

    def apply_venom(self, dps: float, duration: float = 3.0) -> None:
        if dps > self.venom_dps:
            self.venom_dps = dps
            self.venom_initial_dps = dps
        self.venom_timer = max(self.venom_timer, duration)

    # ---------- 每帧更新 ----------

    def update(self, dt: float) -> None:
        if not self.alive:
            return

        # 毒伤
        if self.venom_timer > 0:
            self.venom_timer -= dt
            self.take_damage(self.venom_dps * dt)
            if random.random() < dt:
                self.venom_dps = max(1, self.venom_dps * 0.8)

        # 计时器递减
        if self.ice_slow_timer > 0:
            self.ice_slow_timer -= dt
            if self.ice_slow_timer <= 0:
                self.ice_slow_factor = 1.0
        if self.boost_timer > 0:
            self.boost_timer -= dt
        if self.frozen_timer > 0:
            self.frozen_timer -= dt
        if self.hit_flash_timer > 0:
            self.hit_flash_timer -= dt

        # 计算速度倍率
        speed_mult = 1.0
        if self.frozen_timer > 0:
            speed_mult = 0.0
        else:
            if self.ice_slow_timer > 0:
                # 冰塔减速优先
                speed_mult *= self.ice_slow_factor
            elif self.venom_timer > 0:
                # 毒塔轻微减速：仅当敌人没有冰塔减速时生效
                speed_mult *= VENOM_SLOW_FACTOR
            if self.boost_timer > 0:
                speed_mult *= self.boost_factor

        # 坦克护盾冷却
        if self.type == 'tank' and self.skill == 'shield':
            if self.shield_cd > 0:
                self.shield_cd -= dt

        # 移动
        step = self.speed * speed_mult * dt
        if self.flying:
            self._move_flying(step)
        else:
            self._move_along_path(step)

        # 帧动画（仅在移动时切换）
        if self.frames and step > 0:
            self.anim_timer += dt
            if self.anim_timer >= self.anim_speed:
                self.anim_timer = 0
                self.anim_frame = (self.anim_frame + 1) % len(self.frames)
                self.image = self.frames[self.anim_frame]

    def _move_flying(self, step: float) -> None:
        tx, ty = self.path[-1]
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist <= step:
            self.x, self.y = tx, ty
            self.distance_traveled += dist
            self.reached_end = True
            self.alive = False
        else:
            self.x += dx / dist * step
            self.y += dy / dist * step
            self.distance_traveled += step

    def _move_along_path(self, step: float) -> None:
        if self.path_index >= len(self.path) - 1:
            return
        tx, ty = self.path[self.path_index + 1]
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist <= step:
            self.x, self.y = tx, ty
            self.distance_traveled += dist
            self.path_index += 1
            if self.path_index >= len(self.path) - 1:
                self.reached_end = True
                self.alive = False
        else:
            self.x += dx / dist * step
            self.y += dy / dist * step
            self.distance_traveled += step

    # ---------- 绘制 ----------

    def draw(self, surface: pygame.Surface) -> None:
        # 阴影
        shadow_surf = pygame.Surface((self.radius * 2, self.radius), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 100), (0, 0, self.radius * 2, self.radius))
        surface.blit(shadow_surf, (int(self.x) - self.radius, int(self.y) + self.radius // 2))

        # 主体
        if self.image:
            surface.blit(
                self.image,
                (int(self.x - self.image.get_width() // 2), int(self.y - self.image.get_height() // 2))
            )
        else:
            pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)

        # 受击闪烁
        if self.hit_flash_timer > 0:
            draw_transparent_circle(surface, (255, 255, 255), (int(self.x), int(self.y)), self.radius, alpha=150)

        # 状态特效
        if self.ice_slow_timer > 0:
            draw_transparent_circle(surface, (200, 230, 255), (int(self.x), int(self.y)), self.radius + 1, alpha=80)
        if self.frozen_timer > 0:
            draw_transparent_circle(surface, (100, 200, 255), (int(self.x), int(self.y)), self.radius + 2, alpha=120)
        if self.venom_timer > 0:
            draw_transparent_circle(surface, (0, 255, 0), (int(self.x), int(self.y)), self.radius + 2, alpha=50)
        if self.type == 'boss':
            draw_glow(surface, (int(self.x), int(self.y)), (180, 50, 200), self.radius + 5)
