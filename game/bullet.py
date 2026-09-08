"""
子弹模块 - Bullet 类，追踪目标并施加伤害与特殊效果。
"""
import math
import random
from typing import List, Optional

import pygame

from game.config import CONFIG
from game.effects import ParticlePool
from game.utils import draw_glow


class Bullet:
    """追踪型子弹实体。"""

    def __init__(
        self,
        x: float,
        y: float,
        target,
        damage: float,
        bullet_type: str,
        enemies: list,
        special: Optional[str] = None,
        is_critical: bool = False,
        particle_pool: Optional[ParticlePool] = None,
    ):
        self.x, self.y = x, y
        self.target = target
        self.damage: float = damage
        self.bullet_type: str = bullet_type
        self.enemies = enemies
        self.special: Optional[str] = special
        self.is_critical: bool = is_critical
        self.speed: float = 300.0
        self.alive: bool = True
        self.dx, self.dy = 0.0, 0.0
        self.particle_pool: Optional[ParticlePool] = particle_pool
        self.trail_timer: float = 0.0

        if target:
            dx = target.x - x
            dy = target.y - y
            dist = math.hypot(dx, dy)
            if dist > 0:
                self.dx, self.dy = dx / dist, dy / dist

    def update(self, dt: float) -> None:
        if not self.alive:
            return

        # 目标已死亡则销毁
        if self.target and not self.target.alive:
            self.alive = False
            return

        # 追踪目标
        if self.target:
            dx = self.target.x - self.x
            dy = self.target.y - self.y
            dist = math.hypot(dx, dy)
            if dist > 0:
                self.dx, self.dy = dx / dist, dy / dist
            step = self.speed * dt
            if dist <= step:
                self._hit_target(self.target)
                self.alive = False
            else:
                self.x += self.dx * step
                self.y += self.dy * step

        # 拖尾粒子
        if self.particle_pool:
            self.trail_timer += dt
            if self.trail_timer > 0.02:
                self.trail_timer = 0
                trail_color = self._get_trail_color()
                life = random.uniform(0.1, 0.2)
                radius = random.randint(1, 3)
                self.particle_pool.spawn(
                    self.x, self.y, -self.dx * 30, -self.dy * 30,
                    life, trail_color, radius,
                )

    def _get_trail_color(self):
        color_map = {
            'machine': (255, 220, 80),    # 弩箭拖尾 - 金色
            'cannon': (255, 120, 20),      # 火球拖尾 - 橙红
            'ice': (120, 200, 255),        # 冰晶拖尾 - 冰蓝
            'venom': (80, 255, 80),        # 毒液拖尾 - 翠绿
        }
        return color_map.get(self.bullet_type, (255, 255, 255))

    def _hit_target(self, target) -> None:
        if not target.alive:
            return

        if self.bullet_type == 'venom':
            target.take_damage(self.damage, damage_type='venom')
            # v1.1 平衡：毒伤持续 3s → 4s，配合传染加强群体压制
            target.apply_venom(self.damage, duration=4.0)
            if self.particle_pool:
                for _ in range(8):
                    angle = random.uniform(0, 2 * math.pi)
                    speed = random.uniform(50, 150)
                    vx = math.cos(angle) * speed
                    vy = math.sin(angle) * speed
                    life = random.uniform(0.2, 0.4)
                    radius = random.randint(2, 4)
                    self.particle_pool.spawn(self.x, self.y, vx, vy, life, (0, 255, 0), radius)
        else:
            target.take_damage(self.damage, damage_type=self.bullet_type)
            if self.special == 'slow' and self.bullet_type == 'ice':
                # v1.1 平衡：冰塔减速 50%/1.5s → 40%/2s（更柔和但持续更久）
                target.apply_ice_slow(2.0, 0.6)
                freeze_chance = CONFIG.tower_types['ice'].freeze_chance
                if random.random() < freeze_chance:
                    target.apply_freeze(0.5)
                self._apply_area_slow(target)

    def _apply_area_slow(self, target) -> None:
        """冰霜塔范围减速：对目标附近最多2个敌人施加减速（与直接命中一致）。"""
        others = [e for e in self.enemies if e.alive and not e.reached_end and e != target]
        others.sort(key=lambda e: math.hypot(e.x - target.x, e.y - target.y))
        for e in others[:2]:
            e.apply_ice_slow(2.0, 0.6)

    # ---------- 绘制 ----------

    def draw(self, surface: pygame.Surface) -> None:
        ix, iy = int(self.x), int(self.y)
        angle = math.atan2(self.dy, self.dx)

        if self.bullet_type == 'machine':
            # 哨戒弩台 - 弩箭形状：细长菱形 + 金色发光
            bolt_len = 10
            bolt_w = 3
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            # 菱形四点
            tip = (self.x + cos_a * bolt_len, self.y + sin_a * bolt_len)
            tail = (self.x - cos_a * bolt_len * 0.4, self.y - sin_a * bolt_len * 0.4)
            left = (self.x - sin_a * bolt_w, self.y + cos_a * bolt_w)
            right = (self.x + sin_a * bolt_w, self.y - cos_a * bolt_w)
            pygame.draw.polygon(surface, (255, 220, 80), [tip, left, tail, right])
            pygame.draw.polygon(surface, (255, 255, 200), [tip, left, tail, right], 1)

        elif self.bullet_type == 'cannon':
            # 炼狱火炮 - 火球：多层渐变圆 + 暴击强化
            if self.is_critical:
                # 暴击火球：更大更亮
                draw_glow(surface, (ix, iy), (255, 100, 0), 18)
                pygame.draw.circle(surface, (255, 200, 50), (ix, iy), 8)
                pygame.draw.circle(surface, (255, 100, 0), (ix, iy), 6)
                pygame.draw.circle(surface, (255, 255, 200), (ix, iy), 3)
            else:
                # 普通火球
                draw_glow(surface, (ix, iy), (255, 80, 0), 12)
                pygame.draw.circle(surface, (255, 140, 30), (ix, iy), 6)
                pygame.draw.circle(surface, (255, 220, 100), (ix, iy), 3)

        elif self.bullet_type == 'ice':
            # 霜寒尖塔 - 冰晶碎片：旋转六角星 + 冰蓝发光
            draw_glow(surface, (ix, iy), (100, 180, 255), 10)
            for i in range(6):
                a = angle + i * math.pi / 3
                arm_len = 7 if i % 2 == 0 else 5
                ex = self.x + math.cos(a) * arm_len
                ey = self.y + math.sin(a) * arm_len
                pygame.draw.line(surface, (180, 230, 255), (self.x, self.y), (ex, ey), 2)
            pygame.draw.circle(surface, (220, 240, 255), (ix, iy), 3)

        elif self.bullet_type == 'venom':
            # 瘴毒祭坛 - 毒液球：脉动绿球 + 滴落效果
            pulse = 0.8 + 0.2 * math.sin(pygame.time.get_ticks() * 0.01)
            r = int(6 * pulse)
            # 外发光
            glow_surf = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (0, 255, 0, 50), (r * 2, r * 2), r * 2)
            surface.blit(glow_surf, (ix - r * 2, iy - r * 2))
            # 毒液球主体
            pygame.draw.circle(surface, (40, 200, 40), (ix, iy), r + 1)
            pygame.draw.circle(surface, (100, 255, 100), (ix, iy), r)
            # 高光
            pygame.draw.circle(surface, (200, 255, 200), (ix - 1, iy - 1), max(1, r // 2))
