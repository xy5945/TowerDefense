"""
防御塔模块 - Tower 类，包含目标选择、射击逻辑和升级系统。
"""
import math
import random
from typing import List, Optional

import pygame

from game.config import CONFIG
from game.assets import audio, fonts
from game.effects import ParticlePool, LaserManager
from game.bullet import Bullet
from game.utils import draw_transparent_circle


class Tower:
    """防御塔实体。"""

    def __init__(
        self,
        x: int,
        y: int,
        tower_type: str,
        particle_pool: Optional[ParticlePool] = None,
    ):
        self.x, self.y = x, y
        self.type: str = tower_type
        self.level: int = 1

        stats = CONFIG.tower_types[tower_type]
        self.range: int = stats.range
        self.damage: int = stats.damage
        self.fire_rate: float = stats.fire_rate
        self.color = stats.color
        self.special: Optional[str] = stats.special
        self.cost: int = stats.cost
        self.crit_chance: float = stats.crit_chance
        self.is_laser: bool = stats.laser
        self.is_venom: bool = stats.venom
        self.rapid_fire: bool = stats.rapid_fire
        # v1.1 平衡：连射加速 / 暴击伤害 / 溅射
        self.max_rapid_count: int = stats.max_rapid_count
        self.crit_damage_mult: float = stats.crit_damage_mult
        self.splash_radius: int = stats.splash_radius
        self.splash_damage_mult: float = stats.splash_damage_mult

        self.total_upgrade_cost: int = 0
        self.cooldown: float = 0.0
        self.angle: float = 0.0
        self.target_angle: float = 0.0
        self.selected: bool = False
        self.slow_timer: float = 0.0
        self.slow_factor: float = 1.0
        self.upgrade_effect_timer: float = 0.0
        self.particle_pool: Optional[ParticlePool] = particle_pool
        self.last_target = None
        self.rapid_count: int = 0
        self.sound_cooldown: float = 0.0

    def get_upgrade_cost(self) -> int:
        """获取下一级升级费用。"""
        if self.level < 3:
            return CONFIG.upgrade_costs[self.type][self.level - 1]
        return 0

    def upgrade(self) -> bool:
        """升级防御塔，返回是否成功。"""
        if self.level < 3:
            self.level += 1
            self.damage = int(self.damage * 1.5)
            self.range = int(self.range * 1.2)
            self.fire_rate *= 1.15
            if self.type == 'cannon':
                self.crit_chance += 0.10
            self.upgrade_effect_timer = 0.3
            return True
        return False

    def preview_upgrade_stats(self):
        """预览升级后的属性（不改变当前状态），用于升级按钮悬浮提示。

        返回 dict，包含 level/damage/range/fire_rate/crit_chance；
        已满级返回 None。
        """
        if self.level >= 3:
            return None
        return {
            'level': self.level + 1,
            'damage': int(self.damage * 1.5),
            'range': int(self.range * 1.2),
            'fire_rate': self.fire_rate * 1.15,
            'crit_chance': (
                self.crit_chance + 0.10 if self.type == 'cannon'
                else self.crit_chance
            ),
        }

    def get_sell_price(self) -> int:
        return int((self.cost + self.total_upgrade_cost) * 0.5)

    def apply_slow(self, duration: float, factor: float) -> None:
        """Boss 对塔的减速效果。"""
        self.slow_timer = max(self.slow_timer, duration)
        self.slow_factor = min(self.slow_factor, factor)

    def _spawn_muzzle_flash(self) -> None:
        """生成枪口闪光粒子。"""
        if not self.particle_pool:
            return
        muzzle_x = self.x + math.cos(self.angle) * 20
        muzzle_y = self.y + math.sin(self.angle) * 20

        color_map = {
            'cannon': (255, 200, 100),
            'ice': (150, 200, 255),
            'venom': (100, 255, 100),
        }
        if self.is_laser:
            flash_color = (200, 100, 255)
        else:
            flash_color = color_map.get(self.type, (255, 255, 200))

        for _ in range(random.randint(3, 5)):
            angle_offset = random.uniform(-0.5, 0.5)
            speed = random.uniform(30, 80)
            vx = math.cos(self.angle + angle_offset) * speed
            vy = math.sin(self.angle + angle_offset) * speed
            life = random.uniform(0.05, 0.15)
            radius = random.randint(2, 4)
            self.particle_pool.spawn(muzzle_x, muzzle_y, vx, vy, life, flash_color, radius)

    def _find_target(self, enemies: list):
        """选择射程内沿路径最远的敌人。"""
        target = None
        best = -1
        for e in enemies:
            if not e.alive or e.reached_end:
                continue
            # 飞行敌人免疫炮塔和冰塔
            if e.flying and self.type in ('cannon', 'ice'):
                continue
            # 隐身敌人只被激光塔攻击
            if e.invisible_timer > 0 and not self.is_laser:
                continue
            dist = math.hypot(e.x - self.x, e.y - self.y)
            if dist <= self.range and e.progress > best:
                best = e.progress
                target = e
        return target

    def update(self, dt: float, enemies: list, bullets: list, laser_manager: LaserManager) -> None:
        if self.upgrade_effect_timer > 0:
            self.upgrade_effect_timer -= dt
        if self.slow_timer > 0:
            self.slow_timer -= dt
        if self.sound_cooldown > 0:
            self.sound_cooldown -= dt

        self.cooldown -= dt
        if self.cooldown > 0:
            # 平滑旋转
            diff = (self.target_angle - self.angle) % (2 * math.pi)
            if diff > math.pi:
                diff -= 2 * math.pi
            self.angle += diff * min(1, dt * 8)
            return

        target = self._find_target(enemies)
        if not target:
            if self.rapid_fire:
                self.last_target = None
                self.rapid_count = 0
            return

        # 机枪塔连射计数（上限由 TowerStats.max_rapid_count 控制）
        if self.rapid_fire:
            if self.last_target is target:
                self.rapid_count = min(self.rapid_count + 1, self.max_rapid_count)
            else:
                self.rapid_count = 0
                self.last_target = target

        # 旋转朝向目标（激光塔用更高旋转因子，hitscan 不容许"边转边打"漏目标）
        self.target_angle = math.atan2(target.y - self.y, target.x - self.x)
        diff = (self.target_angle - self.angle) % (2 * math.pi)
        if diff > math.pi:
            diff -= 2 * math.pi
        rot_speed = dt * 15 if self.is_laser else dt * 8
        self.angle += diff * min(1, rot_speed)

        # 激光塔开火门控：hitscan 没追踪子弹补救，差几度就漏
        # 阈值 0.05 rad ≈ 2.9° → 250 远约 13 像素偏移，仍在 (radius+5) 容差范围内
        # _find_target 选的是"最远进度"，可能与 self.angle 当前方向不一致——
        # angle 没追上时开火，_fire_laser 沿 self.angle 扫描根本对不上 target，白开火
        # 门控时不重置 cooldown，让它走完自然开火周期（0.8/秒 = 1.25s）
        if self.is_laser and abs(diff) > 0.05:
            return

        # 计算有效射速
        fire_rate_multiplier = 1.0
        if self.rapid_fire and self.last_target is target:
            fire_rate_multiplier = 1.0 + 0.1 * self.rapid_count
        eff_fire_rate = self.fire_rate * fire_rate_multiplier
        if self.slow_timer > 0:
            eff_fire_rate *= self.slow_factor
        self.cooldown = 1.0 / eff_fire_rate

        # 开火
        self._fire(target, enemies, bullets, laser_manager)

    def _fire(self, target, enemies: list, bullets: list, laser_manager: LaserManager) -> None:
        if self.is_laser:
            self._fire_laser(enemies, laser_manager)
            self._spawn_muzzle_flash()
            audio.play('laser_shot')
        elif self.is_venom:
            bullets.append(Bullet(
                self.x, self.y, target, self.damage, 'venom',
                enemies, particle_pool=self.particle_pool,
            ))
            self._spawn_muzzle_flash()
            audio.play('venom_shot')
        elif self.type == 'ice':
            bullets.append(Bullet(
                self.x, self.y, target, self.damage, 'ice',
                enemies, special='slow', particle_pool=self.particle_pool,
            ))
            self._spawn_muzzle_flash()
            audio.play('ice_shot')
        elif self.type == 'cannon':
            crit = random.random() < self.crit_chance
            dmg = self._get_crit_damage() if crit else self.damage
            bullets.append(Bullet(
                self.x, self.y, target, dmg, 'cannon',
                enemies, is_critical=crit, particle_pool=self.particle_pool,
            ))
            # v1.1 平衡：火炮小范围溅射（命中后对周围敌人造成 50% 基础伤害）
            self._apply_cannon_splash(target, enemies)
            self._spawn_muzzle_flash()
            audio.play('cannon_shot')
        else:  # machine
            bullets.append(Bullet(
                self.x, self.y, target, self.damage, self.type,
                enemies, particle_pool=self.particle_pool,
            ))
            self._spawn_muzzle_flash()
            if self.sound_cooldown <= 0:
                audio.play('machine_shot')
                self.sound_cooldown = 0.12

    def _get_crit_damage(self) -> int:
        """计算加农炮暴击伤害（基础伤害 × 暴击倍率）。"""
        return int(self.damage * self.crit_damage_mult)

    def _apply_cannon_splash(self, target, enemies: list) -> None:
        """火炮溅射：对主目标周围半径内的敌人造成 splash_damage_mult 倍基础伤害。
        溅射同样受目标过滤（飞行免疫、隐身）限制，但不参与暴击判定。"""
        if self.splash_radius <= 0:
            return
        splash_dmg = int(self.damage * self.splash_damage_mult)
        if splash_dmg <= 0:
            return
        for e in enemies:
            if e is target or not e.alive or e.reached_end:
                continue
            # 火炮不能打飞行敌人（保持与 _find_target 一致的过滤）
            if e.flying:
                continue
            # 隐身只被激光看见
            if e.invisible_timer > 0:
                continue
            if math.hypot(e.x - target.x, e.y - target.y) <= self.splash_radius:
                e.take_damage(splash_dmg, damage_type='cannon')

    def _fire_laser(self, enemies: list, laser_manager: LaserManager) -> None:
        """激光塔射击：穿透所有命中的敌人，伤害递减；连续命中同一目标触发过载。"""
        length = self.range
        cos_a = math.cos(self.angle)
        sin_a = math.sin(self.angle)
        hit_list = []
        for e in enemies:
            if not e.alive or e.reached_end:
                continue
            dx = e.x - self.x
            dy = e.y - self.y
            t = dx * cos_a + dy * sin_a
            if 0 <= t <= length:
                d2 = dx * dx + dy * dy - t * t
                # 激光是 hitscan，250 远的目标即使差 1° 也会偏 4 像素
                # 容差 +5 让"开火门控"放过的微小角度偏差也能命中
                if d2 <= (e.radius + 5) ** 2:
                    hit_list.append((t, e))
        hit_list.sort(key=lambda item: item[0])

        # v1.1 平衡：过载机制——连续命中同一目标，伤害 +10%/次，封顶 (max_rapid_count * 10%)
        if hit_list:
            primary = hit_list[0][1]
            if self.last_target is primary:
                self.rapid_count = min(self.rapid_count + 1, self.max_rapid_count)
            else:
                self.rapid_count = 0
            self.last_target = primary
            overload_mult = 1.0 + 0.1 * self.rapid_count
        else:
            # 没有命中任何目标：重置计数
            self.last_target = None
            self.rapid_count = 0
            overload_mult = 1.0

        # 穿透减伤：50% → 40%（每次穿透保留更多伤害）
        mult = overload_mult
        for _, e in hit_list:
            dmg = int(self.damage * mult)
            if dmg > 0:
                e.take_damage(dmg, damage_type='laser')
            mult *= 0.4  # 穿透衰减 50% → 40%
            if self.particle_pool:
                for _ in range(3):
                    angle = random.uniform(0, 2 * math.pi)
                    speed = random.uniform(50, 150)
                    self.particle_pool.spawn(
                        e.x, e.y,
                        math.cos(angle) * speed, math.sin(angle) * speed,
                        random.uniform(0.1, 0.3), (255, 200, 255),
                        random.randint(2, 4),
                    )
        laser_manager.add(self.x, self.y, self.angle, length, self.color)

    # ---------- 绘制 ----------

    def draw(self, surface: pygame.Surface) -> None:
        from game.assets import images

        sprite = images.get_tower_sprite(self.type)

        # 阴影
        shadow_surf = pygame.Surface((30, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 100), (0, 0, 30, 10))
        surface.blit(shadow_surf, (self.x - 15, self.y + 10))

        if sprite:
            # --- 精灵图模式 ---
            spr_w, spr_h = sprite.get_size()
            surface.blit(sprite, (self.x - spr_w // 2, self.y - spr_h // 2))

            # 方向指示器（旋转小箭头）
            cos_a = math.cos(self.angle)
            sin_a = math.sin(self.angle)
            ind_len = 18
            end_x = self.x + cos_a * ind_len
            end_y = self.y + sin_a * ind_len
            pygame.draw.line(surface, self.color, (self.x, self.y), (end_x, end_y), 2)
            # 箭头尖
            tip_len = 6
            for da in (0.4, -0.4):
                tx = end_x - math.cos(self.angle + da) * tip_len
                ty = end_y - math.sin(self.angle + da) * tip_len
                pygame.draw.line(surface, self.color, (end_x, end_y), (tx, ty), 2)
        else:
            # --- 几何图形回退模式 ---
            base_size = 16
            cos_a = math.cos(self.angle)
            sin_a = math.sin(self.angle)
            half = base_size // 2
            points = [
                (self.x + cos_a * half - sin_a * half, self.y + sin_a * half + cos_a * half),
                (self.x + cos_a * half + sin_a * half, self.y + sin_a * half - cos_a * half),
                (self.x - cos_a * half + sin_a * half, self.y - sin_a * half - cos_a * half),
                (self.x - cos_a * half - sin_a * half, self.y - sin_a * half + cos_a * half),
            ]
            pygame.draw.polygon(surface, (150, 150, 150), points)
            pygame.draw.polygon(surface, self.color, points, 2)
            barrel_len = 22
            end_x = self.x + cos_a * barrel_len
            end_y = self.y + sin_a * barrel_len
            pygame.draw.line(surface, (100, 100, 100), (self.x, self.y), (end_x, end_y), 6)

        # 升级特效（金色扩散环）
        if self.upgrade_effect_timer > 0:
            alpha = int(255 * (self.upgrade_effect_timer / 0.3))
            radius = int(20 + (1 - self.upgrade_effect_timer / 0.3) * 30)
            draw_transparent_circle(surface, (255, 215, 0), (self.x, self.y), radius, alpha)

        # 等级视觉增强
        if self.level == 2:
            # 2级：白色光环
            glow_surf = pygame.Surface((44, 44), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (255, 255, 255, 40), (22, 22), 22)
            pygame.draw.circle(glow_surf, (255, 255, 255, 80), (22, 22), 20, 1)
            surface.blit(glow_surf, (self.x - 22, self.y - 22))
        elif self.level == 3:
            # 3级：金色脉动光环
            pulse = 0.7 + 0.3 * math.sin(pygame.time.get_ticks() * 0.004)
            alpha = int(100 * pulse)
            glow_surf = pygame.Surface((52, 52), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (255, 215, 0, alpha), (26, 26), 26)
            pygame.draw.circle(glow_surf, (255, 215, 0, int(alpha * 1.5)), (26, 26), 24, 2)
            surface.blit(glow_surf, (self.x - 26, self.y - 26))

        # 等级数字
        if self.level > 1:
            font = fonts.get(14)
            lv_color = (255, 215, 0) if self.level == 3 else (255, 255, 255)
            lv = font.render(str(self.level), True, lv_color)
            surface.blit(lv, (self.x - lv.get_width() // 2, self.y + 14))

        # 选中高亮
        if self.selected:
            pygame.draw.circle(surface, (255, 255, 0), (self.x, self.y), 24, 2)
