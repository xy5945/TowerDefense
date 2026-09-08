"""
游戏主逻辑模块 - Game 类管理游戏状态、实体更新和输入处理。
渲染逻辑已分离至 Renderer，波次生成已分离至 wave 模块。
"""
import math
import random
from typing import List, Tuple, Optional

import pygame

from game.config import (
    CONFIG, WIDTH, HEIGHT, MAP_W, SIDE_PANEL, GRID_SIZE, LEVEL_NAMES,
    load_paths, DIFFICULTY_CONFIGS, calc_star_rating, STAR_REWARD_COEFF,
)
from game.assets import audio, images
from game.effects import ParticlePool, LaserManager
from game.enemy import Enemy
from game.tower import Tower
from game.bullet import Bullet
from game.wave import generate_wave, generate_boss_summon, format_wave_preview
from game.renderer import Renderer
from game.utils import point_near_path, snap_to_grid


class Game:
    """游戏主控制器 - 状态机、实体管理与输入处理。"""

    def __init__(self, data_dir: str):
        self.state: str = 'menu'
        self.current_level: int = 1
        self.mouse_pos: Tuple[float, float] = (0.0, 0.0)
        self.game_speed: int = 1
        self.paused: bool = False
        # 难度：'easy' / 'normal' / 'hard'，默认普通
        self.difficulty: str = 'normal'

        # 提示与警告
        self.tip_timer: float = 0.0
        self.tip_text: str = ""
        self.boss_warning_timer: float = 0.0
        self.boss_warning_text: str = ""

        # 下一波预告：
        # - preview_delay_timer > 0: 波次清场后等待 0.5 秒再展示预告
        # - preview_visible: 预告面板正在显示中（玩家需点击任意位置关闭）
        # - preview_text: 当前显示的预告文案
        self.preview_delay_timer: float = 0.0
        self.preview_visible: bool = False
        self.preview_text: str = ""

        self.red_flash_timer: float = 0.0

        # UI 状态
        self.hovered_tower: Optional[str] = None
        self.selected_tower_type: Optional[str] = None
        self.selected_tower: Optional[Tower] = None

        # 调试快捷键按键序列缓冲
        self.debug_buffer: str = ""

        # 关卡介绍画面
        self.intro_timer: float = 0.0
        self.intro_bg: Optional[pygame.Surface] = None

        # 通关画面计时器（5 秒后自动返回菜单）
        self.victory_timer: float = 0.0

        # 主菜单背景
        self.menu_bg: Optional[pygame.Surface] = None
        self._load_menu_bg()

        # 游戏说明页滚动
        self.guide_scroll: float = 0.0
        # 关于本作品页滚动
        self.about_scroll: float = 0.0

        # 加载关卡路径
        self._path_templates = load_paths(data_dir)

        # 游戏实体（在 reset_game 中初始化）
        self.path: List[Tuple[int, int]] = []
        self.towers: List[Tower] = []
        self.enemies: List[Enemy] = []
        self.bullets: List[Bullet] = []
        self.particle_pool = ParticlePool(600)
        self.laser_manager = LaserManager(30)
        self.money: int = 0
        self.lives: int = 0
        self.wave: int = 0
        self.wave_active: bool = False
        self.spawn_queue: list = []
        self.spawn_timer: float = 0.0
        self.spawn_interval: float = 0.8
        self.level_background = None

        # 星级奖励：下关起手金币加成（跨关累计）
        self.next_level_bonus: int = 0

        # 星级结算相关字段
        self.killed_count: int = 0          # 本关击杀数
        self.level_elapsed: float = 0.0     # 本关用时（秒，暂停时也累计）
        self.result_stars: int = 0          # 最终星级
        self.result_leak_stars: int = 0     # 漏怪子评级
        self.result_time_stars: int = 0     # 用时子评级
        self.result_killed: int = 0         # 结算展示：击杀数
        self.result_leaked: int = 0         # 结算展示：漏怪数
        self.result_elapsed: float = 0.0    # 结算展示：用时
        self.result_reward_gold: int = 0    # 结算展示：金币奖励
        self.result_anim_timer: float = 0.0 # 星级点亮动画计时

        self.reset_game()
        audio.play_bgm("menu_bgm")

    def reset_game(self) -> None:
        """重置当前关卡的游戏状态。"""
        diff = DIFFICULTY_CONFIGS[self.difficulty]
        self.path = self._path_templates[self.current_level - 1]
        self.towers = []
        self.enemies = []
        self.bullets = []
        self.money = CONFIG.initial_money + (self.current_level - 1) * 20 + diff.initial_money_bonus
        self.lives = CONFIG.lives + diff.lives_bonus
        self.wave = 0
        self.wave_active = False
        self.spawn_queue = []
        self.spawn_timer = 0.0
        self.spawn_interval = 0.8
        self.selected_tower_type = None
        self.selected_tower = None
        self.laser_manager = LaserManager(30)
        self.particle_pool = ParticlePool(600)
        self.game_speed = 1
        self.paused = False
        self.boss_warning_timer = 0.0
        self.boss_warning_text = ""
        self.preview_delay_timer = 0.0
        self.preview_visible = False
        self.preview_text = ""
        # 星级奖励在 reset_game 时即合并进起手金币，并清零
        self.money = CONFIG.initial_money + (self.current_level - 1) * 20 + self.next_level_bonus + diff.initial_money_bonus
        self.next_level_bonus = 0
        self.killed_count = 0
        self.level_elapsed = 0.0
        self.level_background = images.load_background(self.current_level, MAP_W, HEIGHT)
        self.red_flash_timer = 0.0
        self.hovered_tower = None

    def _load_menu_bg(self) -> None:
        """加载主菜单背景图。"""
        try:
            from game.utils import resource_path
            path = resource_path("assets/backgrounds/menu_bg.png")
            self.menu_bg = pygame.image.load(path).convert()
            self.menu_bg = pygame.transform.scale(self.menu_bg, (WIDTH, HEIGHT))
        except pygame.error as e:
            print(f"主菜单背景加载失败: {e}")
            self.menu_bg = None

    def _enter_level_intro(self) -> None:
        """进入关卡介绍画面。"""
        self.state = 'level_intro'
        self.intro_timer = 3.0  # 3秒自动进入 或 点击跳过
        # 加载介绍背景（仅首次加载）
        if self.intro_bg is None:
            try:
                from game.utils import resource_path
                path = resource_path("assets/backgrounds/level_intro_bg.png")
                self.intro_bg = pygame.image.load(path).convert()
                self.intro_bg = pygame.transform.scale(self.intro_bg, (WIDTH, HEIGHT))
            except pygame.error as e:
                print(f"关卡介绍背景加载失败: {e}")
                self.intro_bg = None

    def _skip_intro_to_playing(self) -> None:
        """跳过介绍画面，直接进入游戏。"""
        self.state = 'playing'
        self.reset_game()
        audio.play_bgm(f"level_{self.current_level}_bgm")

    # ============================================================
    #  波次管理
    # ============================================================

    def start_wave(self) -> None:
        if self.wave < 10 and not self.wave_active and not self.preview_visible and self.preview_delay_timer <= 0:
            self._commit_wave()

    def _commit_wave(self) -> None:
        """预告结束后真正开打：把波次计数 +1、启动生成。"""
        self.wave += 1
        self.wave_active = True
        self.spawn_queue = generate_wave(self.current_level, self.wave)
        self.spawn_timer = 0.5
        self.spawn_interval = max(0.35, 0.75 - self.wave * 0.03)

    def _queue_next_wave_preview(self) -> None:
        """波次清场后排队下一波预告：先等 0.5 秒再展示。

        如果下一波只有普通小兵，则不弹预告，玩家直接点开始波次按钮即可开战。
        """
        if self.wave >= 10:
            return
        next_queue = generate_wave(self.current_level, self.wave + 1)
        preview = format_wave_preview(next_queue)
        if not preview:
            # 下一波没特殊兵种：玩家自己点开始按钮开战
            return
        self.preview_text = preview
        self.preview_delay_timer = 0.5
        self.preview_visible = False

    def dismiss_wave_preview(self) -> None:
        """玩家点击任意位置关闭预告（不阻塞游戏，可直接点开始波次按钮）。"""
        if self.preview_visible:
            self.preview_visible = False
            self.preview_text = ""

    def _spawn_extra_wave(self) -> None:
        """Boss 半血召唤额外敌人。"""
        entries = generate_boss_summon(self.wave)
        for e_type, hp, speed, reward, skill in entries:
            enemy = Enemy(self.path, hp, speed, e_type, reward, skill)
            self.enemies.append(enemy)

    # ============================================================
    #  塔放置
    # ============================================================

    def can_place_tower(self, pos: Tuple[int, int]) -> bool:
        x, y = pos
        if x < 0 or x > MAP_W or y < 0 or y > HEIGHT:
            return False
        if point_near_path(pos, self.path, 30):
            return False
        for t in self.towers:
            if math.hypot(t.x - x, t.y - y) < GRID_SIZE * 0.8:
                return False
        return True

    # ============================================================
    #  粒子效果
    # ============================================================

    def _spawn_death_particles(self, enemy: Enemy) -> None:
        color_schemes = {
            'normal': [(255, 80, 80), (255, 100, 50), (255, 50, 50)],
            'fast': [(255, 255, 0), (255, 200, 0), (255, 150, 0)],
            'tank': [(255, 140, 0), (255, 100, 0), (200, 80, 0)],
            'boss': [(180, 50, 200), (150, 0, 200), (100, 0, 150)],
            'flying': [(200, 200, 255), (150, 150, 255), (100, 100, 255)],
        }
        colors = color_schemes.get(enemy.type, [(255, 100, 0), (255, 50, 0), (255, 200, 0)])
        for _ in range(20):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(50, 200)
            self.particle_pool.spawn(
                enemy.x, enemy.y,
                math.cos(angle) * speed, math.sin(angle) * speed,
                random.uniform(0.3, 0.6),
                random.choice(colors),
                random.randint(2, 5),
            )

    def _spawn_shield_break_particles(self, enemy: Enemy) -> None:
        for _ in range(20):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(80, 200)
            self.particle_pool.spawn(
                enemy.x, enemy.y,
                math.cos(angle) * speed, math.sin(angle) * speed,
                random.uniform(0.2, 0.5),
                random.choice([(100, 200, 255), (200, 240, 255), (255, 255, 255)]),
                random.randint(2, 5),
            )
        self.particle_pool.spawn(enemy.x, enemy.y, 0, 0, 0.1, (255, 255, 255), 10)

    def _spawn_upgrade_effect(self, tower: Tower) -> None:
        for _ in range(15):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(30, 80)
            self.particle_pool.spawn(
                tower.x, tower.y,
                math.cos(angle) * speed, math.sin(angle) * speed,
                random.uniform(0.2, 0.4), (255, 215, 0),
                random.randint(3, 6),
            )

    # ============================================================
    #  游戏逻辑更新
    # ============================================================

    def update(self, dt: float) -> None:
        if self.state == 'level_intro':
            self.intro_timer -= dt
            if self.intro_timer <= 0:
                self._skip_intro_to_playing()
        elif self.state == 'playing':
            # 星级倒计时按真实时间累计：暂停时也继续计时，避免用暂停冻结星级时间
            self.level_elapsed += dt
            self._update_playing(dt * self.game_speed)
        elif self.state == 'level_complete':
            self.result_anim_timer += dt
        elif self.state == 'victory':
            self.victory_timer -= dt
            if self.victory_timer <= 0:
                self.state = 'menu'
                audio.play_bgm("menu_bgm")

    def _update_playing(self, dt: float) -> None:
        if self.paused:
            return

        # 计时器递减
        if self.tip_timer > 0:
            self.tip_timer -= dt
        if self.boss_warning_timer > 0:
            self.boss_warning_timer -= dt
        if self.red_flash_timer > 0:
            self.red_flash_timer -= dt

        # 下一波预告：先 0.5 秒延迟，再展示预告（玩家点击关闭）
        if self.preview_delay_timer > 0:
            self.preview_delay_timer -= dt
            if self.preview_delay_timer <= 0:
                self.preview_delay_timer = 0
                self.preview_visible = True

        # 生成敌人
        self._spawn_from_queue(dt)

        # 更新敌人
        self._update_enemies(dt)

        # 敌人特殊能力
        self._process_enemy_abilities(dt)

        # 处理死亡
        self._process_deaths()

        # 更新防御塔
        for t in self.towers:
            t.update(dt, self.enemies, self.bullets, self.laser_manager)

        # 更新子弹
        for b in self.bullets:
            b.update(dt)
        self.bullets = [b for b in self.bullets if b.alive]

        # 更新特效
        self.laser_manager.update(dt)
        self.particle_pool.update(dt)

        # 波次完成检测
        if self.wave_active and not self.spawn_queue and not self.enemies:
            self.wave_active = False
            self.money += 50 + self.wave * 10
            if self.wave >= 10:
                self._finish_level()
            else:
                # 当前波清场后，等 0.5 秒弹出下一波特殊兵种预告
                # 预告期间点击任意位置立即关闭
                self._queue_next_wave_preview()

        # 游戏结束检测
        if self.lives <= 0:
            self.state = 'game_over'

    def _spawn_from_queue(self, dt: float) -> None:
        if not (self.wave_active and self.spawn_queue):
            return
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            diff = DIFFICULTY_CONFIGS[self.difficulty]
            e_type, hp, speed, reward, skill = self.spawn_queue.pop(0)
            # 按难度缩放敌人 HP 与速度
            hp = hp * diff.enemy_hp_mult
            speed = speed * diff.enemy_speed_mult
            enemy = Enemy(self.path, hp, speed, e_type, reward, skill)
            self.enemies.append(enemy)
            self.spawn_timer = self.spawn_interval
            if e_type == 'boss':
                self.boss_warning_timer = 3.0
                self.boss_warning_text = "Boss 出现了！"
                audio.play('boss_warning')

    def _update_enemies(self, dt: float) -> None:
        for e in self.enemies:
            e.update(dt)
            if e.reached_end:
                self.lives -= 1
                e.alive = False
                self.red_flash_timer = 0.3
                audio.play('enemy_reach')

    def _process_enemy_abilities(self, dt: float) -> None:
        # 毒液传染
        for e in self.enemies:
            if e.alive and e.venom_timer > 0:
                for o in self.enemies:
                    if o.alive and o != e and o.venom_timer == 0:
                        dist = math.hypot(o.x - e.x, o.y - e.y)
                        if dist < (e.radius + o.radius) * 1.5:
                            o.apply_venom(e.venom_dps * 0.5, duration=2.0)
                            self.particle_pool.spawn(o.x, o.y, 0, 0, 0.3, (0, 255, 0), 5)

        # 毒液冒泡特效
        for e in self.enemies:
            if e.alive and e.venom_timer > 0 and random.random() < dt * 10:
                self.particle_pool.spawn(
                    e.x + random.uniform(-5, 5),
                    e.y + e.radius,
                    random.uniform(-10, 10),
                    random.uniform(20, 50),
                    0.3, (0, 255, 0), 2,
                )

        # 坦克护盾再生（v1.1 平衡：CD 缩短 + 每次触发血量递减）
        # 递减表：第1次30% → 第2次20% → 第3次10% → 第4次起5%
        SHIELD_DECAY_PERCENT = (0.30, 0.20, 0.10, 0.05)
        for e in self.enemies:
            if e.type == 'tank' and e.skill == 'shield' and e.alive:
                if e.shield_cd <= 0 and e.shield_hp <= 0:
                    idx = min(e.shield_count, len(SHIELD_DECAY_PERCENT) - 1)
                    shield_val = int(e.max_hp * SHIELD_DECAY_PERCENT[idx])
                    # 关卡/波次加成：每波 +5，让高难关护盾更厚
                    shield_val += self.wave * 5
                    if shield_val > 0:
                        e.shield_hp = shield_val
                        e.shield_max = shield_val
                        e.absorbed_damage = 0
                        # 分享给周围 2 个队友
                        others = [o for o in self.enemies if o.alive and not o.reached_end and o != e]
                        others.sort(key=lambda o: math.hypot(o.x - e.x, o.y - e.y))
                        for o in others[:2]:
                            o.shield_hp = max(o.shield_hp, shield_val)
                        e.shield_count += 1
                    # 3 秒后再次触发（v1.1：CD 5s → 3s）
                    e.shield_cd = 3.0

        # 快速敌人加速光环
        for e in self.enemies:
            if e.type == 'fast' and e.skill == 'boost_aura' and e.alive:
                for o in self.enemies:
                    if o.alive and not o.reached_end and o != e:
                        if math.hypot(o.x - e.x, o.y - e.y) < CONFIG.skill_range:
                            o.apply_boost(1.0, 1.5)

        # Boss 能力
        for e in self.enemies:
            if e.type != 'boss' or not e.alive:
                continue
            # 减速塔
            if e.slow_tower_cd > 0:
                e.slow_tower_cd -= dt
            else:
                if self.towers:
                    towers_sorted = sorted(self.towers, key=lambda t: math.hypot(t.x - e.x, t.y - e.y))
                    for t in towers_sorted[:2]:
                        t.apply_slow(CONFIG.boss_slow_duration, CONFIG.boss_slow_factor)
                e.slow_tower_cd = CONFIG.boss_slow_cd

            # 半血隐身 + 召唤
            if e.hp < e.max_hp * 0.5 and not e.has_summoned:
                e.has_summoned = True
                e.invisible_timer = 2.0
                self._spawn_extra_wave()
                self.tip_timer = 3.0
                self.tip_text = "Boss进入隐身状态！"
            if e.invisible_timer > 0:
                e.invisible_timer -= dt

        # 护盾破碎特效
        for e in self.enemies:
            if e.shield_broken:
                self._spawn_shield_break_particles(e)
                e.shield_broken = False

    def _process_deaths(self) -> None:
        alive_enemies = []
        for e in self.enemies:
            if not e.alive and not e.reached_end and e.hp <= 0:
                self.money += e.reward
                self.killed_count += 1
                self._spawn_death_particles(e)
                audio.play('enemy_death')
            if e.alive:
                alive_enemies.append(e)
        self.enemies = alive_enemies

    # ============================================================
    #  输入处理
    # ============================================================

    def handle_click(self, pos: Tuple[float, float], button: int = 1) -> None:
        x, y = pos

        # 右键取消
        if button == 3:
            if self.state == 'playing':
                self.selected_tower_type = None
                self.selected_tower = None
            return

        # 关卡介绍画面：点击跳过
        if self.state == 'level_intro':
            self._skip_intro_to_playing()
            return

        if self.state == 'menu':
            self._handle_menu_click(x, y)
        elif self.state == 'guide':
            self._handle_guide_click(x, y)
        elif self.state == 'about':
            self._handle_about_click(x, y)
        elif self.state == 'playing':
            # 预告面板正在显示：
            # - 点开始波次按钮：同时关闭预告并开战
            # - 点其它任意位置：仅关闭预告
            if self.preview_visible:
                if x > MAP_W:
                    px = MAP_W
                    wave_btn = pygame.Rect(px + 20, 330, SIDE_PANEL - 40, 45)
                    if wave_btn.collidepoint(pos):
                        self.dismiss_wave_preview()
                        self.start_wave()
                        return
                self.dismiss_wave_preview()
                return
            if x > MAP_W:
                self._handle_panel_click(pos)
            else:
                self._handle_map_click(pos)
        elif self.state in ('game_over', 'level_complete'):
            self._handle_end_screen_click(x, y)

    def _handle_menu_click(self, x: float, y: float) -> None:
        cx = WIDTH // 2
        btn_w, btn_h = 220, 55
        btn_x = cx - btn_w // 2

        # 开始游戏按钮 (y=300)
        if btn_x <= x <= btn_x + btn_w and 300 <= y <= 300 + btn_h:
            self.current_level = 1  # 每次开始都从第 1 关开始，不保存进度
            self._enter_level_intro()
        # 游戏说明按钮 (y=370)
        elif btn_x <= x <= btn_x + btn_w and 370 <= y <= 370 + btn_h:
            self.state = 'guide'
            self.guide_scroll = 0.0
        # 关于本作品按钮 (y=440)
        elif btn_x <= x <= btn_x + btn_w and 440 <= y <= 440 + btn_h:
            self.state = 'about'
        else:
            # 难度选择面板（与 renderer 同步）：y=512, 高44
            diff_panel_y = 512
            diff_panel_h = 44
            if btn_x <= x <= btn_x + btn_w and diff_panel_y <= y <= diff_panel_y + diff_panel_h:
                # 面板内：左 80px 是"难度"标签，右侧是 3 个按钮
                label_end_x = btn_x + 80
                if x < label_end_x:
                    return  # 点在标签上不算
                gap = 6
                btn_area_x = btn_x + 80
                btn_area_w = btn_w - 95
                diff_btn_w = (btn_area_w - gap * 2) // 3
                for i, diff_key in enumerate(('easy', 'normal', 'hard')):
                    bx = btn_area_x + i * (diff_btn_w + gap)
                    if bx <= x <= bx + diff_btn_w:
                        self.difficulty = diff_key
                        return

    def _handle_guide_click(self, x: float, y: float) -> None:
        """游戏说明页点击：返回按钮。"""
        btn_w, btn_h = 180, 48
        btn_x = WIDTH // 2 - btn_w // 2
        btn_y = HEIGHT - 60
        if btn_x <= x <= btn_x + btn_w and btn_y <= y <= btn_y + btn_h:
            self.state = 'menu'

    def _handle_about_click(self, x: float, y: float) -> None:
        """关于本作品页点击：返回按钮（固定底部，与 draw_about 同步）。"""
        btn_w, btn_h = 160, 42
        btn_x = WIDTH // 2 - btn_w // 2
        btn_y = HEIGHT - 58
        if btn_x <= x <= btn_x + btn_w and btn_y <= y <= btn_y + btn_h:
            self.state = 'menu'
            self.about_scroll = 0.0

    def handle_scroll(self, dy: int) -> None:
        """处理鼠标滚轮事件（游戏说明页/关于页滚动）。"""
        if self.state == 'guide':
            # 限制滚动范围，避免无限滚动/滚过头露白
            max_scroll = max(0, getattr(self, '_guide_content_height', 0) - (HEIGHT - 78 - 40))
            self.guide_scroll = max(0, min(self.guide_scroll - dy * 40, max_scroll))
        elif self.state == 'about':
            # 限制滚动范围，避免无限滚动
            max_scroll = max(0, getattr(self, '_about_content_height', 0) - (HEIGHT - 58 - 40))
            self.about_scroll = max(0, min(self.about_scroll - dy * 40, max_scroll))

    def _handle_map_click(self, pos: Tuple[float, float]) -> None:
        x, y = pos
        if self.selected_tower_type:
            sp = snap_to_grid(pos)
            cost = CONFIG.tower_types[self.selected_tower_type].cost
            if self.money >= cost and self.can_place_tower(sp):
                self.towers.append(Tower(sp[0], sp[1], self.selected_tower_type, self.particle_pool))
                self.money -= cost
                # 放置成功后取消选中，一次只能放置一个防御塔
                self.selected_tower_type = None
        else:
            for t in self.towers:
                t.selected = False
            self.selected_tower = None
            for t in self.towers:
                if math.hypot(t.x - x, t.y - y) < 20:
                    self.selected_tower = t
                    t.selected = True
                    break

    def _handle_panel_click(self, pos: Tuple[float, float]) -> None:
        x, y = pos
        px = MAP_W

        # 速度按钮
        speed_rects = [
            (pygame.Rect(px + 20, 70, 40, 26), 1),
            (pygame.Rect(px + 65, 70, 40, 26), 2),
            (pygame.Rect(px + 110, 70, 40, 26), 3),
        ]
        for rect, mult in speed_rects:
            if rect.collidepoint(pos):
                self.game_speed = mult
                return

        # 暂停
        pause_rect = pygame.Rect(px + 155, 70, 40, 26)
        if pause_rect.collidepoint(pos):
            self.paused = not self.paused
            return

        # 塔选择
        y_off = 105
        sorted_towers = sorted(CONFIG.tower_types.items(), key=lambda item: item[1].cost)
        for key, stats in sorted_towers:
            rect = pygame.Rect(px + 20, y_off, SIDE_PANEL - 40, 38)
            if rect.collidepoint(pos):
                if self.selected_tower_type == key:
                    self.selected_tower_type = None
                else:
                    self.selected_tower_type = key
                if self.selected_tower:
                    self.selected_tower.selected = False
                    self.selected_tower = None
                return
            y_off += 44

        # 开始波次
        wave_btn = pygame.Rect(px + 20, 330, SIDE_PANEL - 40, 45)
        if wave_btn.collidepoint(pos):
            self.start_wave()
            return

        # 升级/出售
        if self.selected_tower:
            t = self.selected_tower
            if t.level < 3:
                up_btn = pygame.Rect(px + 20, 435, 90, 38)
                if up_btn.collidepoint(pos):
                    cost = t.get_upgrade_cost()
                    if self.money >= cost:
                        self.money -= cost
                        t.total_upgrade_cost += cost
                        if t.upgrade():
                            self._spawn_upgrade_effect(t)
                    return
            sell_btn = (
                pygame.Rect(px + 130, 435, 90, 38)
                if t.level < 3
                else pygame.Rect(px + 20, 435, SIDE_PANEL - 40, 38)
            )
            if sell_btn.collidepoint(pos):
                self.money += t.get_sell_price()
                self.towers.remove(t)
                t.selected = False
                self.selected_tower = None

    def _handle_end_screen_click(self, x: float, y: float) -> None:
        if self.state == 'level_complete':
            btn = pygame.Rect(WIDTH // 2 - 120, HEIGHT - 150, 240, 60)
            if not btn.collidepoint(x, y):
                return
            if self.current_level < 10:
                self.current_level += 1
                self._enter_level_intro()
            else:
                self.state = 'victory'
                self.victory_timer = 5.0
        else:
            if not (WIDTH // 2 - 100 <= x <= WIDTH // 2 + 100 and HEIGHT // 2 + 60 <= y <= HEIGHT // 2 + 120):
                return
            self.state = 'menu'
            audio.play_bgm("menu_bgm")

    # ============================================================
    #  调试快捷键（连按序列触发）
    # ============================================================

    def handle_debug_key(self, key: int) -> None:
        """累计按键序列，命中组合后触发对应调试动作（仅游戏进行中生效）。"""
        if self.state != 'playing':
            return

        if key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
            ch = '\n'
        elif pygame.K_a <= key <= pygame.K_z:
            ch = chr(key)
        else:
            return

        self.debug_buffer += ch
        # 限制缓冲长度，避免无限增长
        if len(self.debug_buffer) > 12:
            self.debug_buffer = self.debug_buffer[-12:]

        if self.debug_buffer.endswith('next\n'):
            self.debug_buffer = ''
            self._debug_skip_level()
        elif self.debug_buffer.endswith('money\n'):
            self.debug_buffer = ''
            self._debug_add_money()

    def _finish_level(self) -> None:
        """通关结算：计算星级与奖励，进入结算画面（level_complete）。"""
        diff = DIFFICULTY_CONFIGS[self.difficulty]
        lives_max = CONFIG.lives + diff.lives_bonus
        leaked = max(0, lives_max - self.lives)

        stars, leak_stars, time_stars = calc_star_rating(
            leaked, self.level_elapsed, self.current_level,
        )

        # 前 9 关：星数 × 关数 × 系数 作为下关起手金币加成；第 10 关无下一关，不发奖励
        reward = 0
        if self.current_level < 10:
            reward = stars * self.current_level * STAR_REWARD_COEFF
            self.next_level_bonus += reward

        self.result_stars = stars
        self.result_leak_stars = leak_stars
        self.result_time_stars = time_stars
        self.result_killed = self.killed_count
        self.result_leaked = leaked
        self.result_elapsed = self.level_elapsed
        self.result_reward_gold = reward
        self.result_anim_timer = 0.0

        self.state = 'level_complete'
        audio.play('level_complete')

    def _debug_skip_level(self) -> None:
        """调试：跳过当前关，直接进入结算画面。"""
        self.wave = 10
        self.wave_active = False
        self.enemies.clear()
        self.spawn_queue.clear()
        self._finish_level()

    def _debug_add_money(self) -> None:
        """调试：加 500 金币。"""
        self.money += 500

    # ============================================================
    #  渲染委托
    # ============================================================

    def draw(self, renderer: Renderer) -> None:
        if self.state == 'menu':
            from game.assets import images as _images
            renderer.draw_menu(self.menu_bg, _images.get_logo(), self.difficulty)
        elif self.state == 'guide':
            renderer.draw_guide(self.guide_scroll)
            # 缓存渲染器计算出的内容高度，供 handle_scroll 做滚动上限
            self._guide_content_height = getattr(renderer, '_guide_content_height', 0)
        elif self.state == 'about':
            renderer.draw_about(self.about_scroll)
            self._about_content_height = getattr(renderer, '_about_content_height', 0)
        elif self.state == 'level_intro':
            level_name = LEVEL_NAMES[self.current_level - 1] if self.current_level <= len(LEVEL_NAMES) else ""
            renderer.draw_level_intro(
                self.intro_bg, self.current_level, level_name, self.intro_timer,
            )
        elif self.state == 'playing':
            renderer.draw_playing(
                path=self.path,
                towers=self.towers,
                enemies=self.enemies,
                bullets=self.bullets,
                laser_manager=self.laser_manager,
                particle_pool=self.particle_pool,
                level_background=self.level_background,
                selected_tower_type=self.selected_tower_type,
                selected_tower=self.selected_tower,
                mouse_pos=self.mouse_pos,
                money=self.money,
                tip_timer=self.tip_timer,
                tip_text=self.tip_text,
                boss_warning_timer=self.boss_warning_timer,
                boss_warning_text=self.boss_warning_text,
                red_flash_timer=self.red_flash_timer,
                hovered_tower=self.hovered_tower,
                current_level=self.current_level,
                wave=self.wave,
                lives=self.lives,
                game_speed=self.game_speed,
                paused=self.paused,
                wave_preview_visible=self.preview_visible,
                wave_preview_text=self.preview_text,
                level_elapsed=self.level_elapsed,
            )
        elif self.state == 'game_over':
            renderer.draw_game_over()
        elif self.state == 'level_complete':
            level_name = LEVEL_NAMES[self.current_level - 1] if self.current_level <= len(LEVEL_NAMES) else ""
            renderer.draw_level_complete(
                current_level=self.current_level,
                level_name=level_name,
                stars=self.result_stars,
                leak_stars=self.result_leak_stars,
                time_stars=self.result_time_stars,
                killed=self.result_killed,
                leaked=self.result_leaked,
                elapsed=self.result_elapsed,
                reward_gold=self.result_reward_gold,
                anim_timer=self.result_anim_timer,
            )
        elif self.state == 'victory':
            renderer.draw_victory(self.difficulty)

    def update_hover(self, mouse_pos: Tuple[float, float]) -> None:
        """更新鼠标悬浮状态（由主循环调用）。"""
        self.mouse_pos = mouse_pos
        # 检测悬浮的塔商店项
        self.hovered_tower = None
        if self.state != 'playing':
            return
        px = MAP_W
        y = 105
        sorted_towers = sorted(CONFIG.tower_types.items(), key=lambda item: item[1].cost)
        for key, stats in sorted_towers:
            rect = pygame.Rect(px + 20, y, SIDE_PANEL - 40, 38)
            if rect.collidepoint(mouse_pos):
                self.hovered_tower = key
                break
            y += 44
