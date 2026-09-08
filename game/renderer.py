"""
渲染器模块 - 从 Game 类中分离出所有绘图逻辑，职责单一。
"""
import math
import random
from typing import List, Tuple, Optional

import pygame

from game.config import (
    CONFIG, WIDTH, HEIGHT, MAP_W, SIDE_PANEL, GRID_SIZE,
    LEVEL_PATH_STYLES, DIFFICULTY_CONFIGS, STAR_REWARD_COEFF, calc_star_countdown,
)
from game.assets import fonts
from game.utils import (
    draw_transparent_circle,
    draw_transparent_rect,
    draw_dashed_circle,
    draw_glow,
    snap_to_grid,
)


class Renderer:
    """游戏画面渲染器，管理所有绘图操作。"""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen

    def set_screen(self, screen: pygame.Surface) -> None:
        self.screen = screen

    # ============================================================
    #  菜单 / 过渡画面
    # ============================================================

    def draw_menu(self, menu_bg: Optional[pygame.Surface], logo: Optional[pygame.Surface] = None, difficulty: str = 'normal') -> None:
        """主菜单：暗黑魔幻风格，背景图 + 发光标题 + 三个按钮 + 难度选择。"""
        # 背景
        if menu_bg:
            self.screen.blit(menu_bg, (0, 0))
        else:
            self.screen.fill((20, 15, 30))

        # 半透明暗色遮罩，增强文字可读性
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        self.screen.blit(overlay, (0, 0))

        font_title = fonts.get(52)
        font_sub = fonts.get(22)
        font_btn = fonts.get(26)

        cx = WIDTH // 2

        # Logo 图标（居中显示在标题上方）
        if logo:
            logo_size = 160
            logo_scaled = pygame.transform.smoothscale(logo, (logo_size, logo_size))
            logo_x = cx - logo_size // 2
            logo_y = 10
            self.screen.blit(logo_scaled, (logo_x, logo_y))
            title_y = 190
        else:
            title_y = 120

        # 标题 "守护稚码王国" + 发光效果
        title_text = "守护稚码王国"

        # 发光层
        for offset, alpha in [(4, 30), (3, 50), (2, 80)]:
            glow = font_title.render(title_text, True, (180, 120, 40))
            glow.set_alpha(alpha)
            self.screen.blit(glow, (cx - glow.get_width() // 2 + offset, title_y + offset))
            self.screen.blit(glow, (cx - glow.get_width() // 2 - offset, title_y - offset))

        # 标题主体
        title_surf = font_title.render(title_text, True, (255, 220, 130))
        self.screen.blit(title_surf, (cx - title_surf.get_width() // 2, title_y))

        # 副标题
        sub_text = "暗黑塔防游戏"
        sub_surf = font_sub.render(sub_text, True, (180, 160, 120))
        self.screen.blit(sub_surf, (cx - sub_surf.get_width() // 2, title_y + 65))

        # 按钮样式
        btn_w, btn_h = 220, 55
        btn_x = cx - btn_w // 2
        btn_colors = {
            'start': ((60, 140, 70), (80, 180, 90), (40, 100, 50)),
            'guide': ((60, 70, 140), (80, 90, 180), (40, 50, 100)),
            'about': ((120, 90, 50), (180, 130, 70), (80, 60, 30)),
        }

        # 开始游戏按钮
        btn_start_y = 300
        btn_text = "开始游戏"
        self._draw_styled_button(btn_x, btn_start_y, btn_w, btn_h, btn_text, btn_colors['start'], font_btn)

        # 游戏说明按钮
        btn_guide_y = 370
        self._draw_styled_button(btn_x, btn_guide_y, btn_w, btn_h, "游戏说明", btn_colors['guide'], font_btn)

        # 关于本作品按钮
        btn_about_y = 440
        self._draw_styled_button(btn_x, btn_about_y, btn_w, btn_h, "关于本作品", btn_colors['about'], font_btn)

        # 难度选择区（独立暗色面板，与上方按钮拉开呼吸空间）
        diff_panel_y = 512
        diff_panel_h = 44
        diff_panel_rect = pygame.Rect(btn_x, diff_panel_y, btn_w, diff_panel_h)
        pygame.draw.rect(self.screen, (30, 28, 45), diff_panel_rect, border_radius=8)
        pygame.draw.rect(self.screen, (90, 80, 60), diff_panel_rect, 1, border_radius=8)

        # "难度"标签
        font_diff = fonts.get(18)
        label_surf = font_diff.render("难度", True, (200, 190, 170))
        self.screen.blit(
            label_surf,
            (diff_panel_rect.x + 18, diff_panel_rect.centery - label_surf.get_height() // 2),
        )

        # 3 个难度按钮（嵌入面板右侧）
        diff_buttons = [
            ('easy', (90, 150, 100)),
            ('normal', (100, 130, 180)),
            ('hard', (180, 90, 90)),
        ]
        n = len(diff_buttons)
        gap = 6
        btn_area_x = diff_panel_rect.x + 80
        btn_area_w = diff_panel_rect.width - 95
        diff_btn_w = (btn_area_w - gap * (n - 1)) // n
        diff_btn_h = 28

        for i, (diff_key, base_color) in enumerate(diff_buttons):
            bx = btn_area_x + i * (diff_btn_w + gap)
            by = diff_panel_rect.centery - diff_btn_h // 2
            selected = (difficulty == diff_key)
            rect = pygame.Rect(bx, by, diff_btn_w, diff_btn_h)
            if selected:
                pygame.draw.rect(self.screen, base_color, rect, border_radius=5)
                pygame.draw.rect(self.screen, (255, 215, 0), rect, 2, border_radius=5)
            else:
                pygame.draw.rect(self.screen, (50, 48, 70), rect, border_radius=5)
                pygame.draw.rect(self.screen, (110, 100, 80), rect, 1, border_radius=5)
            diff_name = DIFFICULTY_CONFIGS[diff_key].name
            text_color = (255, 255, 255) if selected else (180, 175, 165)
            text = font_diff.render(diff_name, True, text_color)
            self.screen.blit(
                text,
                (rect.centerx - text.get_width() // 2,
                 rect.centery - text.get_height() // 2),
            )

        # 底部版权与版本号
        font_footer = fonts.get(16)
        footer_text = "稚码园机器人编程  原创作品  v1.0.0"
        footer_surf = font_footer.render(footer_text, True, (160, 150, 130))
        self.screen.blit(
            footer_surf,
            (cx - footer_surf.get_width() // 2, HEIGHT - 22),
        )

    def _draw_styled_button(self, x, y, w, h, text, colors, font):
        """绘制带边框和阴影的风格化按钮。"""
        bg_color, border_color, shadow_color = colors

        # 阴影
        pygame.draw.rect(self.screen, (0, 0, 0), (x + 3, y + 3, w, h), border_radius=12)

        # 按钮主体
        btn_rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, bg_color, btn_rect, border_radius=12)
        pygame.draw.rect(self.screen, border_color, btn_rect, 2, border_radius=12)

        # 文字（带阴影）
        txt_shadow = font.render(text, True, (0, 0, 0))
        txt_surf = font.render(text, True, (255, 255, 255))
        self.screen.blit(txt_shadow, (btn_rect.centerx - txt_shadow.get_width() // 2 + 1, btn_rect.centery - txt_shadow.get_height() // 2 + 1))
        self.screen.blit(txt_surf, (btn_rect.centerx - txt_surf.get_width() // 2, btn_rect.centery - txt_surf.get_height() // 2))

    def draw_guide(self, scroll_offset: int) -> None:
        """游戏说明页面：防御塔和敌人的详细介绍，可滚动。v1.1.3 重设计。"""
        # 背景渐变
        self.screen.fill((15, 12, 25))
        for i in range(0, HEIGHT, 4):
            ratio = i / HEIGHT
            r = int(15 + 8 * ratio)
            g = int(12 + 6 * ratio)
            b = int(25 + 5 * ratio)
            pygame.draw.line(self.screen, (r, g, b), (0, i), (WIDTH, i), 1)

        font_title = fonts.get(48)
        font_section = fonts.get(32)
        font_name = fonts.get(26)
        font_stats = fonts.get(17)
        font_body = fonts.get(18)
        font_small = fonts.get(16)

        gold = (212, 175, 55)
        gold_light = (255, 220, 130)
        gold_dim = (140, 115, 35)
        dim_text = (180, 175, 165)
        dim_text2 = (140, 135, 125)
        white = (240, 235, 225)
        cyan = (140, 220, 255)

        # 裁剪区域：滚动内容只在顶部区显示，底部留给返回按钮（防止遮挡）
        clip_rect = pygame.Rect(0, 0, WIDTH, HEIGHT - 78)
        self.screen.set_clip(clip_rect)

        y = 24 - scroll_offset
        cx = WIDTH // 2

        # === 顶部标题区 ===
        # 装饰横线（左）
        pygame.draw.line(self.screen, gold_dim, (cx - 230, y + 26), (cx - 130, y + 26), 1)
        pygame.draw.line(self.screen, gold_dim, (cx + 130, y + 26), (cx + 230, y + 26), 1)
        # 中央菱形装饰
        diamond_cx, diamond_cy = cx, y + 26
        pygame.draw.polygon(self.screen, gold, [
            (diamond_cx, diamond_cy - 5),
            (diamond_cx + 5, diamond_cy),
            (diamond_cx, diamond_cy + 5),
            (diamond_cx - 5, diamond_cy),
        ])
        # 大标题
        title = font_title.render("游 戏 说 明", True, gold_light)
        self.screen.blit(title, (cx - title.get_width() // 2, y))
        y += 70

        # 副标题
        sub = font_small.render("Tower Defense Manual · 暗黑魔幻塔防全攻略", True, dim_text)
        self.screen.blit(sub, (cx - sub.get_width() // 2, y))
        y += 32

        def draw_section_header(text, color=gold):
            """绘制章节标题（金色文字 + 横线 + 中央菱形）"""
            nonlocal y
            y += 12
            pygame.draw.line(self.screen, gold_dim, (50, y + 18), (90, y + 18), 2)
            pygame.draw.line(self.screen, gold_dim, (WIDTH - 90, y + 18), (WIDTH - 50, y + 18), 2)
            pygame.draw.polygon(self.screen, gold_dim, [
                (cx, y + 14), (cx + 4, y + 18), (cx, y + 22), (cx - 4, y + 18)
            ])
            sec = font_section.render(text, True, color)
            self.screen.blit(sec, (cx - sec.get_width() // 2, y))
            y += 48

        def draw_entry(name, color, stats, desc):
            """绘制单个塔/敌人物品（卡片式，高度随描述自适应）"""
            nonlocal y
            card_x = 50
            card_w = WIDTH - 100
            # 预估描述行数 → 卡片高度
            desc_lines = self._count_wrapped_lines(desc, font_body, card_w - 80)
            card_h = 84 + desc_lines * 24 + 12
            # 卡片背景
            card_rect = pygame.Rect(card_x, y - 6, card_w, card_h)
            pygame.draw.rect(self.screen, (28, 24, 40), card_rect, border_radius=6)
            pygame.draw.line(self.screen, (50, 45, 65), (card_x + 16, card_rect.bottom - 1),
                             (card_x + card_w - 16, card_rect.bottom - 1), 1)
            # 左侧 4px 彩色边条
            pygame.draw.rect(self.screen, color, (card_x, y - 6, 4, card_h), border_radius=2)
            # 圆形图标
            cx_icon = card_x + 32
            cy_icon = y + 22
            pygame.draw.circle(self.screen, color, (cx_icon, cy_icon), 11)
            pygame.draw.circle(self.screen, (255, 255, 255), (cx_icon, cy_icon), 11, 2)
            # 塔/敌名（白色 + 阴影）
            name_shadow = font_name.render(name, True, (0, 0, 0))
            name_surf = font_name.render(name, True, white)
            self.screen.blit(name_shadow, (card_x + 56, y + 5))
            self.screen.blit(name_surf, (card_x + 54, y + 3))
            # 装饰点（标题右侧）
            for i in range(3):
                d_color = (color[0] // 2, color[1] // 2, color[2] // 2)
                pygame.draw.circle(self.screen, d_color, (card_x + card_w - 28 - i * 14, y + 24), 2)
            # 属性行（带背景框）
            stats_y = y + 42
            stats_w = font_stats.size(stats)[0]
            stats_x = card_x + 54
            stats_bg = pygame.Rect(stats_x - 6, stats_y - 3, stats_w + 12, 22)
            pygame.draw.rect(self.screen, (35, 30, 50), stats_bg, border_radius=4)
            pygame.draw.rect(self.screen, (color[0] // 3, color[1] // 3, color[2] // 3),
                             stats_bg, 1, border_radius=4)
            stats_surf = font_stats.render(stats, True, (255, 215, 130))
            self.screen.blit(stats_surf, (stats_x, stats_y))
            # 描述（自动换行）
            self._draw_wrapped_text(desc, font_body, dim_text, card_x + 54, y + 78, card_w - 80, 24)
            y += card_h + 14

        # ===== 防御塔部分 =====
        draw_section_header("◆ 防御塔 ◆")

        tower_data = [
            ("哨戒弩台", (255, 200, 0), "基础 80 | 伤 8 | 射程 100 | 攻速 4/秒",
             "王国哨兵操纵的连弩机台。持续攻击同一目标时射速逐渐提升（上限+30%）。造价低、易上手，但对幽冥飞灵（×0.5）、暗影行者（×0.8）、有护盾敌人（×0.5）伤害受限。"),
            ("炼狱火炮", (255, 80, 80), "基础 180 | 伤 50 | 射程 150 | 攻速 1/秒",
             "以地狱之火锻造的重型火炮。20%概率暴击（暴击伤害2.5倍）。命中后产生半径35的溅射，对周围敌人造成60%基础伤害。专克重甲单体，无法攻击幽冥飞灵。"),
            ("霜寒尖塔", (0, 200, 255), "基础 100 | 伤 6 | 射程 110 | 攻速 1.2/秒",
             "远古冰霜法师遗留的冻结之塔。命中后减速敌人40%持续2秒，15%概率冻结0.5秒。霜冻易伤：被减速敌人受到的伤害+10%，被冻结敌人受到的伤害+50%。同时减速目标附近2个敌人。无法攻击幽冥飞灵。"),
            ("奥术裂隙", (160, 120, 255), "基础 250 | 伤 80 | 射程 250 | 攻速 0.6/秒",
             "撕裂空间释放奥术能量的裂隙。穿透光束命中路径上所有敌人，每穿透一个目标伤害衰减40%。过载机制：连续命中同一目标伤害递增（+10%/次，最高+50%）。无视隐身，对幽冥飞灵伤害减半。"),
            ("瘴毒祭坛", (0, 255, 0), "基础 120 | 伤 18 | 射程 130 | 攻速 1.4/秒",
             "散发致命瘴气的暗黑祭坛。施加持续毒伤（4秒），毒素会传染给附近未中毒的敌人。毒液无视护盾直接侵蚀生命，对幽冥飞灵伤害+50%。中毒状态的坦克破盾回血仅30%（非中毒坦克回血50%），毒塔是真正的坦克克星。"),
        ]

        for name, color, stats, desc in tower_data:
            draw_entry(name, color, stats, desc)

        # ===== 敌人部分 =====
        draw_section_header("◆ 敌人类型 ◆")

        enemy_data = [
            ("魔化步兵", (255, 80, 80), "HP 60 | 速度 60 | 赏金 10",
             "被黑暗力量侵蚀的士兵，失去理智却保留了战斗本能。数量众多，是魔王军团的主要推进力量。"),
            ("暗影行者", (255, 255, 0), "HP 40 | 速度 100 | 赏金 12",
             "在阴影中穿行的迅捷恶魔。部分拥有加速光环，可提升周围友军50%移动速度（持续1.5秒）。速度快但血量低，需要弩塔/激光快速击杀。"),
            ("铁甲魔像", (255, 140, 0), "HP 150 | 速度 40 | 赏金 25",
             "以黑铁铸造的巨型魔像，高血量低速度。部分拥有护盾能力：每3秒回复护盾（血量比例递减：第1次30%→第2次20%→第3次10%→第4次起5%，每波额外+5），并分享给附近2个友军。护盾破碎时回复吸收伤害的50%；若坦克处于中毒状态，回血仅30%（非中毒的60%），毒塔是真正的坦克克星。"),
            ("深渊领主", (180, 50, 200), "HP 400 | 速度 50 | 赏金 80",
             "来自深渊的强大恶魔领主。每7秒减速最近2座防御塔（持续4秒）。血量低于50%时进入隐身并召唤增援。只有奥术裂隙能稳定打击隐身状态。"),
            ("幽冥飞灵", (200, 200, 255), "HP 60 | 速度 30 | 赏金 20",
             "脱离肉体的怨灵，沿直线飘行，无视路径弯曲。对哨戒弩台和奥术裂隙伤害减免50%，对瘴毒祭坛+50%。炼狱火炮和霜寒尖塔无法攻击幽冥飞灵，必须搭配弩塔/激光/毒塔。"),
        ]

        for name, color, stats, desc in enemy_data:
            draw_entry(name, color, stats, desc)

        # ===== 评星与奖励 =====
        draw_section_header("◆ 评星与奖励 ◆")

        def draw_subsection(title: str, lines, accent):
            """绘制一个浅色小标题段落（标题 + 多个 bullet 行，自动换行）。"""
            nonlocal y
            y += 8
            # 小标题（金色细体）
            title_surf = font_body.render("★ " + title, True, accent)
            self.screen.blit(title_surf, (70, y))
            y += 24
            for line in lines:
                prefix = "  · "
                wrapped_w = WIDTH - 200
                n = self._count_wrapped_lines(prefix + line, font_body, wrapped_w)
                self._draw_wrapped_text(prefix + line, font_body, white, 80, y, wrapped_w, 22)
                y += n * 22 + 4
            y += 10

        draw_subsection("漏怪评级（基于本关漏掉的敌人数量）", [
            "★★★ 满星：全程 0 漏——完美通关，护旗不倒。",
            "★★ 二星：漏 1~5 个，个别突破防线。",
            "★ 一星：漏 6~10 个，惊险守住。",
            "✦ 无星：漏 11 个以上，防线已失，建议调整布阵再来。",
        ], cyan)

        draw_subsection("用时评级（用时越快星级越高）", [
            "最终星级 = min(漏怪星级, 用时星级)，两维度都达标才能拿满星。",
            "标准用时：第 1 关 240 秒起，每过 1 关再 +20 秒。",
            "★★★ ≤ 标准用时 ｜ ★★ ≤ 1.5× 标准用时 ｜ ★ ≤ 2.5× 标准用时 ｜ 否则无星。",
        ], (180, 220, 180))

        draw_subsection("实时倒计时（屏幕右下角）", [
            "开局从 3 星时间开始倒计；归零后自动切到 2 星剩余时间，再归零切到 1 星剩余时间。",
            "1 星剩余时间走完后，计时器停在 0:00 不再倒计。",
            "按真实时间累计——暂停期间也继续计时，无法靠暂停冻结星级时间。",
        ], (200, 200, 220))

        draw_subsection("下关起手金币加成", [
            "奖励公式：奖励金币 = 星数 × 关数 × 20，自动并入下一关起手金币。",
            "示例：通过第 5 关 3 星 → 下一关起手 +300 金币（3 × 5 × 20）。",
            "第 10 关通关仅展示战绩，无金币加成。",
        ], (255, 200, 100))

        # ===== 通用提示 =====
        draw_section_header("◆ 战术提示 ◆")

        tips = [
            ("基础机制", "每关10波敌人，全部通关后进入下一关；塔可升3级，出售返还50%。"),
            ("操作", "支持1x/2x/3x变速和暂停；右键点击可取消当前选中的防御塔。"),
            ("星级倒计时", "屏幕右下角显示本关星级倒计时，用时越快星级越高；倒计时按真实时间累计，暂停时也继续计时。"),
            ("护盾机制", "铁甲魔像护盾：每3秒回复护盾（30%→20%→10%→5%递减），破盾时回50%吸收伤害；只有坦克自己的盾破了才回血。"),
            ("毒塔克制", "毒塔对铁甲魔像特别有效：毒液无视护盾，且中毒坦克破盾回血仅30%（非中毒坦克的60%）。"),
            ("飞灵限制", "幽冥飞灵只有弩塔、激光、毒塔能打；火炮和冰塔无法攻击飞灵。"),
            ("隐身对策", "Boss隐身阶段只有奥术裂隙能稳定输出，提前布防是关键。"),
        ]

        for label, text in tips:
            # 标签（先预计算宽度，用于内容起点定位）
            tag_surf = font_stats.render(f" {label} ", True, (40, 25, 0))
            tag_w = tag_surf.get_width()
            # 内容可用宽度
            content_x = 68 + tag_w + 16
            avail_w = WIDTH - content_x - 30
            # 预估行数 → 本行总高度（至少 36，多行则按行高累加）
            n_lines = self._count_wrapped_lines(text, font_body, avail_w)
            row_h = max(36, n_lines * 24 + 10)
            # 左侧金色竖条（高度随内容自适应）
            pygame.draw.rect(self.screen, gold, (55, y + 4, 3, row_h - 6), border_radius=2)
            # 标签
            tag_bg = pygame.Rect(65, y + 4, tag_w + 6, 22)
            pygame.draw.rect(self.screen, gold, tag_bg, border_radius=4)
            self.screen.blit(tag_surf, (68, y + 7))
            # 内容（自动换行）
            self._draw_wrapped_text(text, font_body, dim_text, content_x, y + 8, avail_w, 24)
            y += row_h

        y += 30

        # 记录内容总高度（用于滚动限制）
        self._guide_content_height = y + scroll_offset

        # 解除 clip：返回按钮画在滚动内容之外，需要全屏绘制权限
        self.screen.set_clip(None)

        # === 返回按钮（固定屏幕底部）===
        btn_w, btn_h = 180, 48
        btn_x = cx - btn_w // 2
        btn_y = HEIGHT - 60
        # 加按钮阴影
        shadow_rect = pygame.Rect(btn_x, btn_y + 3, btn_w, btn_h)
        pygame.draw.rect(self.screen, (0, 0, 0), shadow_rect, border_radius=6)
        self._draw_styled_button(
            btn_x, btn_y, btn_w, btn_h, "返 回 菜 单",
            ((100, 60, 60), (160, 90, 90), (60, 30, 30)), fonts.get(22),
        )

        self.screen.set_clip(None)

    def _draw_wrapped_text(self, text, font, color, x, y, max_width, line_height):
        """绘制自动换行的文本。"""
        words = list(text)  # 按字符拆分（中文适用）
        line = ""
        cy = y
        for ch in words:
            test = line + ch
            if font.size(test)[0] > max_width:
                surf = font.render(line, True, color)
                self.screen.blit(surf, (x, cy))
                cy += line_height
                line = ch
            else:
                line = test
        if line:
            surf = font.render(line, True, color)
            self.screen.blit(surf, (x, cy))

    @staticmethod
    def _count_wrapped_lines(text, font, max_width):
        """计算自动换行后的行数（与 _draw_wrapped_text 同一算法）。"""
        lines = 1
        line = ""
        for ch in list(text):
            test = line + ch
            if font.size(test)[0] > max_width:
                lines += 1
                line = ch
            else:
                line = test
        return lines

    def draw_about(self, scroll_offset: int = 0) -> None:
        """关于本作品页面：上下结构，文字可滚动，返回按钮固定在底部。"""
        # 背景
        self.screen.fill((15, 12, 25))

        gold = (212, 175, 55)
        gold_light = (255, 220, 130)
        gold_dim = (160, 130, 40)
        white = (230, 225, 215)
        dim_text = (180, 175, 165)

        # 字号整体缩小，留出一屏能看完的空间
        font_title = fonts.get(32)
        font_section = fonts.get(20)
        font_body = fonts.get(17)
        font_small = fonts.get(15)

        cx = WIDTH // 2

        # 返回按钮固定在底部（先算位置，给文字区预留顶部）
        btn_w, btn_h = 160, 42
        btn_x = cx - btn_w // 2
        btn_y = HEIGHT - 58

        # 文字区上边界 30、下边界 = btn_y - 10（即 HEIGHT - 68）
        # 用 set_clip 把文字绘制限制在这个区间，绝不溢出到按钮区
        text_area_top = 30
        text_area_bottom = btn_y - 10
        self.screen.set_clip(pygame.Rect(0, text_area_top, WIDTH, text_area_bottom - text_area_top))

        # 从上到下铺内容，应用滚动偏移
        y = text_area_top - scroll_offset

        # 主标题
        title = font_title.render("关于本作品", True, gold_light)
        self.screen.blit(title, (cx - title.get_width() // 2, y))
        y += font_title.get_height() + 10

        # 装饰线 + 作品名
        line_y = y + 14
        pygame.draw.line(self.screen, gold_dim, (cx - 180, line_y), (cx - 80, line_y), 1)
        pygame.draw.line(self.screen, gold_dim, (cx + 80, line_y), (cx + 180, line_y), 1)
        sub_text = font_section.render("守护稚码王国", True, gold)
        self.screen.blit(sub_text, (cx - sub_text.get_width() // 2, y))
        y += font_section.get_height() + 18

        # ===== 作品信息 =====
        section = font_section.render("◆ 作品信息", True, gold)
        self.screen.blit(section, (cx - 200, y))
        y += font_section.get_height() + 8

        info_lines = [
            ("版本", "v1.0.0"),
            ("引擎", "Python + pygame"),
            ("代码量", "3,400+ 行 Python"),
            ("模块数", "11 个"),
            ("关卡", "10 关（边境村庄 → 地狱深渊）"),
            ("塔种", "5 种（弩台/冰塔/毒塔/火炮/激光）"),
            ("敌人", "5 种（步兵/行者/魔像/领主/飞灵）"),
        ]
        for label, value in info_lines:
            label_surf = font_body.render(label, True, dim_text)
            value_surf = font_body.render(value, True, white)
            self.screen.blit(label_surf, (cx - 180, y))
            self.screen.blit(value_surf, (cx - 80, y))
            y += font_body.get_height() + 4

        y += 8

        # ===== 关于稚码园 =====
        section = font_section.render("◆ 关于稚码园", True, gold)
        self.screen.blit(section, (cx - 200, y))
        y += font_section.get_height() + 8

        org_lines = [
            "我们相信每个孩子都能创造自己的世界。",
            "编程不是枯燥的代码,而是创造的工具。",
            "稚码园机器人编程,用游戏点燃孩子的代码梦想。",
        ]
        for line in org_lines:
            surf = font_body.render(line, True, white)
            self.screen.blit(surf, (cx - surf.get_width() // 2, y))
            y += font_body.get_height() + 6

        y += 8

        # ===== 版权声明 =====
        section = font_section.render("◆ 版权声明", True, gold)
        self.screen.blit(section, (cx - 200, y))
        y += font_section.get_height() + 8

        copyright_lines = [
            "本作品由稚码园教学团队与学员共同完成。",
            "代码、美术、音乐均为原创或经合法授权。",
            "稚码园机器人编程  保留所有权利。",
        ]
        for line in copyright_lines:
            surf = font_small.render(line, True, dim_text)
            self.screen.blit(surf, (cx - surf.get_width() // 2, y))
            y += font_small.get_height() + 4

        # 记录内容总高度（用于滚动限制）
        self._about_content_height = y + scroll_offset

        # 取消裁剪
        self.screen.set_clip(None)

        # 在裁剪外画一条分隔线，提示按钮是独立区域
        pygame.draw.line(self.screen, gold_dim, (40, btn_y - 14), (WIDTH - 40, btn_y - 14), 1)

        # 返回按钮（固定在屏幕底部）
        self._draw_styled_button(
            btn_x, btn_y, btn_w, btn_h, "返回菜单",
            ((100, 60, 60), (160, 90, 90), (60, 30, 30)), fonts.get(22),
        )

    def draw_level_intro(
        self,
        intro_bg: Optional[pygame.Surface],
        current_level: int,
        level_name: str,
        intro_timer: float,
    ) -> None:
        """关卡介绍画面：中世纪书封风格，显示关卡编号和主题名称。"""
        # 背景
        if intro_bg:
            self.screen.blit(intro_bg, (0, 0))
        else:
            self.screen.fill((10, 10, 10))

        font_big = fonts.get(48)
        font_med = fonts.get(32)
        font_small = fonts.get(20)

        gold = (212, 175, 55)
        gold_light = (255, 223, 120)
        gold_dim = (160, 130, 40)

        # 关卡编号（如 "第一关"）
        level_label = f"— 第 {current_level} 关 —"
        label_surf = font_med.render(level_label, True, gold_dim)
        label_x = WIDTH // 2 - label_surf.get_width() // 2
        label_y = HEIGHT // 2 - 80

        # 带阴影的文字
        shadow_offset = 2
        for surf, x_off, y_off, color in [
            (label_surf, shadow_offset, shadow_offset, (30, 25, 10)),
            (label_surf, 0, 0, gold_dim),
        ]:
            self.screen.blit(surf, (label_x + x_off, label_y + y_off))

        # 主题名称（大字）
        name_surf = font_big.render(level_name, True, gold_light)
        name_x = WIDTH // 2 - name_surf.get_width() // 2
        name_y = HEIGHT // 2 - 25

        # 名称阴影 + 主体
        name_shadow = font_big.render(level_name, True, (40, 30, 10))
        self.screen.blit(name_shadow, (name_x + 3, name_y + 3))
        self.screen.blit(name_surf, (name_x, name_y))

        # 装饰分隔线
        line_y = name_y + name_surf.get_height() + 15
        line_w = min(name_surf.get_width() + 40, 400)
        line_x = WIDTH // 2 - line_w // 2
        pygame.draw.line(self.screen, gold_dim, (line_x, line_y), (line_x + line_w, line_y), 1)
        # 两端小菱形装饰
        for dx in (0, line_w):
            diamond_cx = line_x + dx
            diamond_cy = line_y
            pts = [
                (diamond_cx, diamond_cy - 4),
                (diamond_cx + 4, diamond_cy),
                (diamond_cx, diamond_cy + 4),
                (diamond_cx - 4, diamond_cy),
            ]
            pygame.draw.polygon(self.screen, gold, pts)

        # "点击任意位置开始" 提示（呼吸闪烁效果）
        pulse = 0.5 + 0.5 * math.sin(intro_timer * 3.0)
        alpha = int(80 + 175 * pulse)
        hint_color = (
            int(gold[0] * alpha / 255),
            int(gold[1] * alpha / 255),
            int(gold[2] * alpha / 255),
        )
        hint_surf = font_small.render("点击任意位置开始", True, hint_color)
        hint_x = WIDTH // 2 - hint_surf.get_width() // 2
        hint_y = HEIGHT // 2 + 80
        self.screen.blit(hint_surf, (hint_x, hint_y))

    def draw_game_over(self) -> None:
        self.screen.fill((30, 30, 30))
        font_big = fonts.get(36)
        font_med = fonts.get(24)

        txt = font_big.render("游戏结束", True, (255, 80, 80))
        self.screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT // 2 - 80))
        btn = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 + 60, 200, 60)
        pygame.draw.rect(self.screen, (150, 50, 50), btn, border_radius=10)
        bt = font_med.render("返回菜单", True, (255, 255, 255))
        self.screen.blit(bt, (btn.centerx - bt.get_width() // 2, btn.centery - bt.get_height() // 2))

    def draw_level_complete(
        self,
        current_level: int,
        level_name: str,
        stars: int,
        leak_stars: int,
        time_stars: int,
        killed: int,
        leaked: int,
        elapsed: float,
        reward_gold: int,
        anim_timer: float,
    ) -> None:
        """结算画面：星级评价（逐颗点亮）+ 数据统计 + 金币奖励。"""
        self.screen.fill((24, 28, 34))

        font_big = fonts.get(40)
        font_med = fonts.get(24)
        font_small = fonts.get(20)

        # 标题
        title = f"第 {current_level} 关 · {level_name} 完成！"
        txt = font_big.render(title, True, (230, 200, 120))
        self.screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, 70))

        # 大星星（最终星级，逐颗点亮）
        lit = min(stars, 1 + int(anim_timer / 0.35))
        star_cx = [WIDTH // 2 - 90, WIDTH // 2, WIDTH // 2 + 90]
        for i, cx in enumerate(star_cx):
            self._draw_star(cx, 180, 42, i < lit)

        # 数据统计
        time_str = f"{int(elapsed) // 60}:{int(elapsed) % 60:02d}"
        stats = f"击杀 {killed}   漏怪 {leaked}   用时 {time_str}"
        st = font_small.render(stats, True, (185, 185, 190))
        self.screen.blit(st, (WIDTH // 2 - st.get_width() // 2, 250))

        # 子评级：漏怪 + 用时（解释最终星级如何得出）
        self._draw_sub_rating(WIDTH // 2 - 190, 302, "漏怪", leak_stars, font_small)
        self._draw_sub_rating(WIDTH // 2 + 40, 302, "用时", time_stars, font_small)

        # 奖励行
        if current_level < 10:
            reward_txt = f"金币加成 +{reward_gold}（{stars}星 × 第{current_level}关 × {STAR_REWARD_COEFF}）"
        else:
            reward_txt = "最终战绩达成"
        rt = font_med.render(reward_txt, True, (255, 215, 80))
        self.screen.blit(rt, (WIDTH // 2 - rt.get_width() // 2, 370))

        # 按钮
        btn = pygame.Rect(WIDTH // 2 - 120, HEIGHT - 150, 240, 60)
        pygame.draw.rect(self.screen, (60, 140, 70), btn, border_radius=10)
        btn_label = "下一关" if current_level < 10 else "查看通关奖励"
        bt = font_med.render(btn_label, True, (255, 255, 255))
        self.screen.blit(bt, (btn.centerx - bt.get_width() // 2, btn.centery - bt.get_height() // 2))

    def _draw_star(self, cx: int, cy: int, r: int, filled: bool) -> None:
        """画一颗五角星。filled=True 金色实心，否则灰色空心轮廓。"""
        pts = []
        for i in range(10):
            angle = -math.pi / 2 + i * math.pi / 5
            radius = r if i % 2 == 0 else r * 0.45
            pts.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        if filled:
            pygame.draw.polygon(self.screen, (255, 200, 60), pts)
            pygame.draw.polygon(self.screen, (200, 150, 30), pts, width=2)
        else:
            pygame.draw.polygon(self.screen, (70, 70, 82), pts, width=2)

    def _draw_sub_rating(self, x: int, y: int, label: str, count: int, font) -> None:
        """画一行小评级：标签 + 3 颗小星。"""
        txt = font.render(label, True, (150, 150, 160))
        self.screen.blit(txt, (x, y + 1))
        for i in range(3):
            self._draw_star(x + 56 + i * 28, y + 13, 11, i < count)

    def _wrap_words(self, text: str, font, max_width: int, max_lines: int):
        """按单词折行；若超过 max_lines 行返回 None（交由调用方缩小字号重试）。"""
        lines: list = []
        cur = ''
        for word in text.split(' '):
            trial = word if not cur else cur + ' ' + word
            if font.size(trial)[0] <= max_width:
                cur = trial
                continue
            if cur:
                lines.append(cur)
                if len(lines) >= max_lines:
                    return None
            cur = word
        if cur:
            if len(lines) >= max_lines:
                return None
            lines.append(cur)
        return lines

    def _fit_phrase_lines(self, text: str, max_width: int, color=(255, 220, 100), max_lines: int = 2):
        """自动缩放字号 + 折行，返回可直接 blit 的 Surface 列表（最多 max_lines 行）。"""
        for size in range(44, 15, -2):
            font = fonts.get(size)
            lines = self._wrap_words(text, font, max_width, max_lines)
            if lines is not None:
                return [font.render(line, True, color) for line in lines]
        # 兜底：最小字号，不限行数
        font = fonts.get(16)
        lines = self._wrap_words(text, font, max_width, 99) or [text]
        return [font.render(line, True, color) for line in lines]

    def draw_victory(self, difficulty: str = 'normal') -> None:
        """通关画面：
        - 普通/困难模式显示该难度独有的密语（中文意译、长句自动缩放字号并折行）。
        - 简单模式只显示"恭喜通关"等引导话术，不显示密语。
        - 配置防御：show_secret_phrase 与 secret_phrase 双判断，避免简单模式误开 flag 时渲染空字符串。
        """
        self.screen.fill((30, 30, 50))
        font_big = fonts.get(44)
        font_small = fonts.get(24)

        diff = DIFFICULTY_CONFIGS[difficulty]
        phrase = diff.secret_phrase  # 普通/困难模式独有，普通有则非空
        show_phrase = diff.show_secret_phrase and bool(phrase)

        if show_phrase:
            # 普通/困难模式：显示该难度对应的密语（长句自动缩放字号并折行）
            line_surfs = self._fit_phrase_lines(phrase, WIDTH - 80)

            gap = 6
            total_h = sum(s.get_height() for s in line_surfs) + gap * (len(line_surfs) - 1)
            # 单行时与原有位置一致，多行时整体向上居中展开
            y = HEIGHT // 2 - 70 - (total_h - line_surfs[0].get_height()) // 2
            for surf in line_surfs:
                self.screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, y))
                y += surf.get_height() + gap

            sub = font_small.render("对老师说出这段神秘代码，会有惊喜。", True, (200, 180, 150))
            sub_y = max(HEIGHT // 2 + 15, HEIGHT // 2 - 70 + total_h + 25)
            self.screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, sub_y))
        else:
            # 简单模式（或配置误开 flag 但 secret_phrase 为空）：引导玩家尝试更高难度
            txt = font_big.render("恭喜通关！", True, (255, 220, 100))
            self.screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT // 2 - 70))

            sub = font_small.render("挑战更高难度可获得神秘奖励！", True, (200, 180, 150))
            self.screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, HEIGHT // 2 + 15))

    # ============================================================
    #  游戏主画面
    # ============================================================

    def draw_playing(
        self,
        path,
        towers,
        enemies,
        bullets,
        laser_manager,
        particle_pool,
        level_background,
        selected_tower_type,
        selected_tower,
        mouse_pos,
        money,
        tip_timer,
        tip_text,
        boss_warning_timer,
        boss_warning_text,
        red_flash_timer,
        hovered_tower,
        current_level,
        wave,
        lives,
        game_speed,
        paused,
        wave_preview_visible=False,
        wave_preview_text="",
        level_elapsed=0.0,
    ) -> None:
        self._draw_map(path, level_background, current_level)
        self._draw_towers(towers)
        laser_manager.draw(self.screen)
        self._draw_enemies(enemies)
        self._draw_bullets(bullets)
        particle_pool.draw(self.screen)
        self._draw_placement_preview(selected_tower_type, mouse_pos, money, path, towers)
        self._draw_selected_tower_range(selected_tower)
        self._draw_tip(tip_timer, tip_text)
        if wave_preview_visible:
            self._draw_wave_preview(wave_preview_text)
        self._draw_boss_warning(boss_warning_timer, boss_warning_text)
        self._draw_boss_hp_bar(enemies)
        self._draw_red_flash(red_flash_timer)
        self._draw_panel(
            current_level, wave, money, lives, game_speed, paused,
            selected_tower_type, selected_tower, mouse_pos,
            level_elapsed,
        )
        # 悬停塔信息框放在最后绘制，确保浮在侧栏面板之上
        self._draw_hover_tower_info(hovered_tower, mouse_pos)

    def _draw_map(self, path, level_background, current_level: int = 1) -> None:
        if level_background:
            self.screen.blit(level_background, (0, 0))
        else:
            self.screen.fill((40, 120, 60))
            pygame.draw.rect(self.screen, (30, 90, 45), (0, 0, MAP_W, HEIGHT))

        # 路径缓存：同一关内路径不变，预渲染到离屏 Surface
        if not hasattr(self, '_path_cache') or self._path_cache.get('_level') != current_level:
            self._path_cache = self._render_path_surface(path, current_level)

        self.screen.blit(self._path_cache['surface'], (0, 0))

        # 起点/终点标记（使用AI图标，回退到几何图形）
        from game.assets import images
        spawn_img = images.get_path_marker('spawn')
        exit_img = images.get_path_marker('exit')
        marker_size = 40

        if spawn_img:
            scaled = pygame.transform.scale(spawn_img, (marker_size, marker_size))
            self.screen.blit(scaled, (path[0][0] - marker_size // 2, path[0][1] - marker_size // 2))
        else:
            pygame.draw.circle(self.screen, (255, 255, 0), path[0], 15)
            pygame.draw.circle(self.screen, (200, 180, 0), path[0], 15, 2)

        if exit_img:
            scaled = pygame.transform.scale(exit_img, (marker_size, marker_size))
            self.screen.blit(scaled, (path[-1][0] - marker_size // 2, path[-1][1] - marker_size // 2))
        else:
            pygame.draw.rect(self.screen, (255, 255, 255), (path[-1][0] - 15, path[-1][1] - 15, 30, 30))
            pygame.draw.rect(self.screen, (200, 200, 200), (path[-1][0] - 15, path[-1][1] - 15, 30, 30), 2)

    def _render_path_surface(self, path, current_level: int) -> dict:
        """预渲染精细化路径到离屏 Surface。"""
        style = LEVEL_PATH_STYLES[current_level - 1] if current_level <= len(LEVEL_PATH_STYLES) else LEVEL_PATH_STYLES[0]
        surf = pygame.Surface((MAP_W, HEIGHT), pygame.SRCALPHA)

        pw = style.path_width
        bw = style.border_width
        pc = style.path_color
        bc = style.border_color
        gc = style.glow_color

        # 1. 发光层
        if gc:
            glow_w = pw + 16
            for i in range(len(path) - 1):
                pygame.draw.line(surf, (*gc, 60), path[i], path[i + 1], glow_w)
            for i in range(len(path) - 1):
                pygame.draw.line(surf, (*gc, 30), path[i], path[i + 1], glow_w + 8)

        # 2. 边框（深色描边）
        border_w = pw + bw * 2
        for i in range(len(path) - 1):
            pygame.draw.line(surf, bc, path[i], path[i + 1], border_w)

        # 3. 路径主体
        for i in range(len(path) - 1):
            pygame.draw.line(surf, pc, path[i], path[i + 1], pw)

        # 4. 关节处圆角过渡
        for p in path:
            pygame.draw.circle(surf, pc, p, pw // 2)
            pygame.draw.circle(surf, bc, p, pw // 2 + bw, bw)

        # 5. 高光线（偏移向光源方向，模拟立体感）
        highlight_color = tuple(min(255, c + 40) for c in pc)
        shadow_color = tuple(max(0, c - 35) for c in pc)
        for i in range(len(path) - 1):
            dx = path[i + 1][0] - path[i][0]
            dy = path[i + 1][1] - path[i][1]
            length = math.hypot(dx, dy)
            if length < 1:
                continue
            # 法向量（垂直于路径方向）
            nx, ny = -dy / length, dx / length
            offset = pw // 4
            # 高光线（左上偏移）
            h_start = (path[i][0] + nx * offset, path[i][1] + ny * offset)
            h_end = (path[i + 1][0] + nx * offset, path[i + 1][1] + ny * offset)
            pygame.draw.line(surf, highlight_color, h_start, h_end, max(1, pw // 6))
            # 阴影线（右下偏移）
            s_start = (path[i][0] - nx * offset, path[i][1] - ny * offset)
            s_end = (path[i + 1][0] - nx * offset, path[i + 1][1] - ny * offset)
            pygame.draw.line(surf, shadow_color, s_start, s_end, max(1, pw // 6))

        # 6. 路面纹理（随机散布小点模拟材质）
        rng = random.Random(current_level * 12345)  # 固定种子确保一致
        for i in range(len(path) - 1):
            seg_len = math.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
            n_dots = int(seg_len / 6)
            dx = path[i + 1][0] - path[i][0]
            dy = path[i + 1][1] - path[i][1]
            for _ in range(n_dots):
                t = rng.random()
                px = path[i][0] + dx * t
                py = path[i][1] + dy * t
                # 在路径宽度内随机偏移
                offset_dist = rng.uniform(-pw // 3, pw // 3)
                length = math.hypot(dx, dy)
                if length < 1:
                    continue
                nx_dir, ny_dir = -dy / length, dx / length
                dot_x = int(px + nx_dir * offset_dist)
                dot_y = int(py + ny_dir * offset_dist)
                # 随机深色或浅色纹理点
                if rng.random() > 0.5:
                    dot_color = tuple(min(255, c + rng.randint(10, 30)) for c in pc)
                else:
                    dot_color = tuple(max(0, c - rng.randint(10, 30)) for c in pc)
                r = rng.randint(1, 3)
                pygame.draw.circle(surf, dot_color, (dot_x, dot_y), r)

        # 7. 边缘碎石（沿路径两侧的小装饰）
        for i in range(len(path) - 1):
            seg_len = math.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
            n_stones = int(seg_len / 18)
            dx = path[i + 1][0] - path[i][0]
            dy = path[i + 1][1] - path[i][1]
            length = math.hypot(dx, dy)
            if length < 1:
                continue
            nx_dir, ny_dir = -dy / length, dx / length
            for _ in range(n_stones):
                t = rng.random()
                px = path[i][0] + dx * t
                py = path[i][1] + dy * t
                # 边缘偏移（路径宽度一半 + 少量）
                edge_offset = pw // 2 + rng.randint(1, 5)
                side = rng.choice([-1, 1])
                sx = int(px + nx_dir * edge_offset * side)
                sy = int(py + ny_dir * edge_offset * side)
                stone_r = rng.randint(2, 4)
                stone_color = tuple(max(0, min(255, c + rng.randint(-30, 10))) for c in bc)
                pygame.draw.circle(surf, stone_color, (sx, sy), stone_r)

        return {'surface': surf, '_level': current_level}

    def _draw_towers(self, towers) -> None:
        for t in towers:
            t.draw(self.screen)

    def _draw_enemies(self, enemies) -> None:
        font_small = fonts.get(18)
        for e in enemies:
            if e.invisible_timer > 0:
                if int(e.invisible_timer * 10) % 2 == 0:
                    if e.image:
                        temp = e.image.copy()
                        temp.set_alpha(100)
                        self.screen.blit(
                            temp,
                            (int(e.x - temp.get_width() // 2), int(e.y - temp.get_height() // 2)),
                        )
                    else:
                        temp = pygame.Surface((e.radius * 2, e.radius * 2), pygame.SRCALPHA)
                        pygame.draw.circle(temp, (*e.color, 100), (e.radius, e.radius), e.radius)
                        self.screen.blit(temp, (int(e.x) - e.radius, int(e.y) - e.radius))
                    if e.type == 'boss':
                        inv_text = font_small.render("隐身", True, (255, 0, 0))
                        self.screen.blit(inv_text, (e.x - inv_text.get_width() // 2, e.y - e.radius - 20))
            else:
                e.draw(self.screen)

            # 血条
            bw = e.radius * 2
            hp_ratio = e.hp / e.max_hp
            pygame.draw.rect(self.screen, (255, 0, 0), (e.x - bw // 2, e.y - e.radius - 8, bw, 4))
            pygame.draw.rect(self.screen, (0, 255, 0), (e.x - bw // 2, e.y - e.radius - 8, int(bw * hp_ratio), 4))

            # 护盾
            if e.shield_hp > 0:
                pygame.draw.circle(self.screen, (0, 255, 255), (int(e.x), int(e.y)), e.radius + 3, 2)

            # 技能视觉
            if e.skill == 'boost_aura':
                pulse_radius = CONFIG.skill_range + int(5 * math.sin(pygame.time.get_ticks() * 0.005))
                draw_dashed_circle(self.screen, (255, 255, 0), (int(e.x), int(e.y)), pulse_radius, dash=8, gap=6, width=2)
            elif e.skill == 'shield':
                pulse_radius = e.radius + 8 + int(4 * math.sin(pygame.time.get_ticks() * 0.005))
                draw_transparent_circle(self.screen, (0, 150, 255), (int(e.x), int(e.y)), pulse_radius, alpha=60)

    def _draw_bullets(self, bullets) -> None:
        for b in bullets:
            b.draw(self.screen)

    def _draw_placement_preview(self, selected_tower_type, mouse_pos, money, path, towers) -> None:
        if not selected_tower_type or mouse_pos[0] >= MAP_W:
            return
        from game.utils import point_near_path
        sp = snap_to_grid(mouse_pos)
        stats = CONFIG.tower_types[selected_tower_type]
        valid = (
            money >= stats.cost
            and not point_near_path(sp, path, 30)
            and 0 <= sp[0] <= MAP_W and 0 <= sp[1] <= HEIGHT
            and all(math.hypot(t.x - sp[0], t.y - sp[1]) >= GRID_SIZE * 0.8 for t in towers)
        )
        rect = pygame.Rect(sp[0] - GRID_SIZE // 2, sp[1] - GRID_SIZE // 2, GRID_SIZE, GRID_SIZE)
        if valid:
            draw_transparent_rect(self.screen, (0, 255, 0), rect, alpha=80)
            draw_transparent_circle(self.screen, (0, 255, 0), sp, stats.range, alpha=30)
        else:
            draw_transparent_rect(self.screen, (255, 0, 0), rect, alpha=80)
            draw_transparent_circle(self.screen, (255, 0, 0), sp, stats.range, alpha=20)
        pygame.draw.circle(self.screen, stats.color, sp, 14)
        pygame.draw.circle(self.screen, (255, 255, 255), sp, 14, 2)

    def _draw_selected_tower_range(self, selected_tower) -> None:
        if selected_tower:
            draw_dashed_circle(self.screen, (255, 255, 0), (selected_tower.x, selected_tower.y), selected_tower.range)

    def _draw_tip(self, tip_timer: float, tip_text: str) -> None:
        if tip_timer <= 0:
            return
        font_med = fonts.get(24)
        tip_surf = font_med.render(tip_text, True, (255, 255, 0))
        self.screen.blit(tip_surf, (MAP_W // 2 - tip_surf.get_width() // 2, 50))

    def _draw_wave_preview(self, text: str) -> None:
        """下一波预告：屏幕中央暗色面板，玩家点击任意位置关闭。

        每行一个特殊兵种（名字 + 属性标签），按 \\n 拆行展示。
        """
        if not text:
            return
        font_label = fonts.get(20)
        font_big = fonts.get(28)
        font_hint = fonts.get(16)

        # 面板最大宽度（地图区 720 - 左右留白）
        max_panel_w = MAP_W - 100
        pad_x, pad_y = 24, 14

        label_surf = font_label.render("下一波", True, (200, 200, 200))
        lines = text.split('\n')
        body_surfs = [font_big.render(ln.strip(), True, (255, 255, 255)) for ln in lines if ln.strip()]
        line_h = font_big.get_height()

        hint_surf = font_hint.render("点击任意位置关闭", True, (180, 180, 180))
        hint_h = hint_surf.get_height() + 6

        body_w = max((s.get_width() for s in body_surfs), default=0)
        panel_w = min(max(label_surf.get_width(), body_w, hint_surf.get_width()) + pad_x * 2, max_panel_w)
        panel_h = (
            label_surf.get_height()
            + line_h * len(body_surfs)
            + hint_h
            + pad_y * 2
            + 8
        )

        cx = MAP_W // 2
        cy = HEIGHT // 2 - 80
        panel_rect = pygame.Rect(0, 0, panel_w, panel_h)
        panel_rect.center = (cx, cy)

        # 暗色半透明背景 + 金色边框
        bg_surf = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        bg_surf.fill((0, 0, 0, 180))
        pygame.draw.rect(bg_surf, (180, 140, 60), bg_surf.get_rect(), 2)
        self.screen.blit(bg_surf, panel_rect.topleft)

        # "下一波"标签
        self.screen.blit(label_surf, (cx - label_surf.get_width() // 2, panel_rect.y + pad_y))
        # 主体文案（每行一个兵种，居中）
        body_y = panel_rect.y + pad_y + label_surf.get_height() + 8
        for s in body_surfs:
            self.screen.blit(s, (cx - s.get_width() // 2, body_y))
            body_y += line_h
        # 关闭提示
        self.screen.blit(hint_surf, (cx - hint_surf.get_width() // 2, panel_rect.bottom - pad_y - hint_h))

    def _draw_boss_warning(self, timer: float, text: str) -> None:
        if timer <= 0:
            return
        font_big = fonts.get(36)
        warn_surf = font_big.render(text, True, (255, 0, 0))
        if int(timer * 10) % 2 == 0:
            self.screen.blit(warn_surf, (MAP_W // 2 - warn_surf.get_width() // 2, HEIGHT // 2 - 100))

    def _draw_boss_hp_bar(self, enemies) -> None:
        boss = None
        for e in enemies:
            if e.type == 'boss' and e.alive:
                boss = e
                break
        if not boss:
            return

        font_med = fonts.get(24)
        bar_width, bar_height = 300, 20
        bar_x = WIDTH // 2 - bar_width // 2
        bar_y = 20
        hp_ratio = boss.hp / boss.max_hp

        pygame.draw.rect(self.screen, (50, 50, 50), (bar_x - 2, bar_y - 2, bar_width + 4, bar_height + 4))
        pygame.draw.rect(self.screen, (255, 0, 0), (bar_x, bar_y, bar_width, bar_height))
        pygame.draw.rect(self.screen, (0, 255, 0), (bar_x, bar_y, int(bar_width * hp_ratio), bar_height))
        boss_name = font_med.render("深渊领主", True, (255, 255, 255))
        self.screen.blit(boss_name, (bar_x, bar_y + bar_height + 5))

    def _draw_star_countdown(self, elapsed: float, current_level: int) -> None:
        """屏幕右下角星级倒计时：3星 → 2星 → 1星，1星走完后归 0 不再倒计时。

        注意：计时按真实时间走，暂停期间同样累计，界面上保持正常倒计时样式。
        """
        tier, remain = calc_star_countdown(elapsed, current_level)

        font_label = fonts.get(16)
        font_time = fonts.get(24)

        tier_colors = {3: (255, 200, 60), 2: (205, 205, 215), 1: (215, 140, 80)}
        if tier == 0:
            color = (120, 120, 132)
            label_text = "无星级"
            time_text = "0:00"
        else:
            color = tier_colors[tier]
            label_text = f"{tier}星倒计时"
            # 向上取整，避免最后一秒显示成 0:00
            secs = math.ceil(remain)
            time_text = f"{secs // 60}:{secs % 60:02d}"

        label_surf = font_label.render(label_text, True, color)
        time_surf = font_time.render(time_text, True, (255, 255, 255) if tier else (150, 150, 160))

        pad = 8
        w = max(label_surf.get_width(), time_surf.get_width()) + pad * 2
        h = label_surf.get_height() + time_surf.get_height() + pad * 2 + 2
        # 屏幕右下角（贴合边缘留 12px 安全边距）
        margin = 12
        rect = pygame.Rect(WIDTH - w - margin, HEIGHT - h - margin, w, h)

        bg = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(bg, (18, 18, 28, 195), pygame.Rect(0, 0, w, h), border_radius=8)
        self.screen.blit(bg, rect.topleft)
        pygame.draw.rect(self.screen, color, rect, 2, border_radius=8)

        cx = rect.centerx
        self.screen.blit(label_surf, (cx - label_surf.get_width() // 2, rect.y + pad))
        self.screen.blit(
            time_surf,
            (cx - time_surf.get_width() // 2, rect.y + pad + label_surf.get_height() + 2),
        )

    def _draw_red_flash(self, timer: float) -> None:
        if timer <= 0:
            return
        alpha = int(200 * (timer / 0.3))
        flash_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(flash_surf, (255, 0, 0, alpha), (0, 0, WIDTH, 15))
        pygame.draw.rect(flash_surf, (255, 0, 0, alpha), (0, HEIGHT - 15, WIDTH, 15))
        pygame.draw.rect(flash_surf, (255, 0, 0, alpha), (0, 0, 15, HEIGHT))
        pygame.draw.rect(flash_surf, (255, 0, 0, alpha), (WIDTH - 15, 0, 15, HEIGHT))
        self.screen.blit(flash_surf, (0, 0))

    # ============================================================
    #  侧边栏面板
    # ============================================================

    def _draw_panel(
        self,
        current_level, wave, money, lives,
        game_speed, paused,
        selected_tower_type, selected_tower,
        mouse_pos,
        level_elapsed=0.0,
    ) -> None:
        font_small = fonts.get(18)
        font_med = fonts.get(24)
        px = MAP_W

        # 背景
        pygame.draw.rect(self.screen, (50, 50, 70), (px, 0, SIDE_PANEL, HEIGHT))

        # 星级倒计时（屏幕右下角）：紧贴背景之后绘制，
        # 保证后续所有图层（升级按钮、升级属性预览、悬浮塔信息）都盖在它之上
        self._draw_star_countdown(level_elapsed, current_level)

        # 信息
        line1 = f"关卡 {current_level}  波次 {wave}/10"
        line2 = f"生命 {lives}  金币 {money}"
        self.screen.blit(font_small.render(line1, True, (255, 255, 255)), (px + 20, 20))
        self.screen.blit(font_small.render(line2, True, (255, 255, 255)), (px + 20, 45))

        # 速度按钮
        speed_rects = [
            (pygame.Rect(px + 20, 70, 40, 26), 1),
            (pygame.Rect(px + 65, 70, 40, 26), 2),
            (pygame.Rect(px + 110, 70, 40, 26), 3),
        ]
        for rect, mult in speed_rects:
            color = (100, 200, 255) if game_speed == mult else (60, 60, 80)
            pygame.draw.rect(self.screen, color, rect, border_radius=5)
            txt = font_small.render(f"{mult}x", True, (255, 255, 255))
            self.screen.blit(txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2))

        # 暂停按钮
        pause_rect = pygame.Rect(px + 155, 70, 40, 26)
        if paused:
            pygame.draw.rect(self.screen, (255, 200, 0), pause_rect, border_radius=5)
            txt = font_small.render("▶", True, (0, 0, 0))
        else:
            pygame.draw.rect(self.screen, (60, 60, 80), pause_rect, border_radius=5)
            txt = font_small.render("||", True, (255, 255, 255))
        self.screen.blit(txt, (pause_rect.centerx - txt.get_width() // 2, pause_rect.centery - txt.get_height() // 2))

        # 塔商店
        y = 105
        sorted_towers = sorted(CONFIG.tower_types.items(), key=lambda item: item[1].cost)
        for key, stats in sorted_towers:
            rect = pygame.Rect(px + 20, y, SIDE_PANEL - 40, 38)
            pygame.draw.rect(self.screen, (30, 30, 40), rect, border_radius=8)
            pygame.draw.rect(self.screen, stats.color, rect, 3, border_radius=8)
            name = font_small.render(f"{stats.name} {stats.cost}", True, (255, 255, 255))
            self.screen.blit(name, (rect.x + 10, rect.y + 8))
            if selected_tower_type == key:
                pygame.draw.rect(self.screen, (255, 255, 0), rect, 5, border_radius=8)
            y += 44

        # 开始波次按钮
        wave_btn = pygame.Rect(px + 20, 330, SIDE_PANEL - 40, 45)
        pygame.draw.rect(self.screen, (50, 150, 220), wave_btn, border_radius=10)
        txt = font_med.render("开始波次", True, (255, 255, 255))
        self.screen.blit(txt, (wave_btn.centerx - txt.get_width() // 2, wave_btn.centery - txt.get_height() // 2))

        # 选中塔信息
        if selected_tower:
            self._draw_selected_tower_panel(selected_tower, px, font_small, mouse_pos)

    def _draw_selected_tower_panel(self, t, px, font_small, mouse_pos) -> None:
        tower_name = CONFIG.tower_types[t.type].name
        info = font_small.render(f"{tower_name} 等级 {t.level}", True, (255, 255, 255))
        self.screen.blit(info, (px + 20, 390))
        sell_info = font_small.render(f"出售价: {t.get_sell_price()}", True, (255, 200, 100))
        self.screen.blit(sell_info, (px + 20, 410))

        # 暗黑魔幻主题配色：(主体暗色, 发光边框色, 文字色)
        upgrade_scheme = ((26, 46, 32), (110, 200, 130), (225, 255, 225))
        sell_scheme = ((50, 22, 22), (210, 85, 70), (255, 220, 210))

        if t.level < 3:
            up_btn = pygame.Rect(px + 20, 435, 90, 38)
            self._draw_action_button(
                up_btn, "升级", upgrade_scheme, font_small,
                sub_text=str(t.get_upgrade_cost()),
            )
            sell_btn = pygame.Rect(px + 130, 435, 90, 38)
        else:
            up_btn = None
            sell_btn = pygame.Rect(px + 20, 435, SIDE_PANEL - 40, 38)

        self._draw_action_button(sell_btn, "出售", sell_scheme, font_small)

        # 鼠标悬浮在升级按钮上时，显示升级后属性预览
        if up_btn is not None and up_btn.collidepoint(mouse_pos):
            self._draw_upgrade_preview(t, up_btn, px)

    def _draw_action_button(self, rect, text, scheme, font, sub_text=None) -> None:
        """绘制暗黑魔幻风格的操作按钮：阴影 + 暗色主体 + 顶部高光 + 发光边框。"""
        base, edge, text_color = scheme

        # 阴影
        pygame.draw.rect(self.screen, (0, 0, 0), rect.move(2, 3), border_radius=8)

        # 主体（暗色底）
        pygame.draw.rect(self.screen, base, rect, border_radius=8)

        # 顶部内高光（模拟立体受光）
        highlight = tuple(min(255, c + 32) for c in base)
        top_rect = pygame.Rect(rect.x + 2, rect.y + 2, rect.width - 4, rect.height // 2 - 2)
        pygame.draw.rect(self.screen, highlight, top_rect, border_radius=6)

        # 发光边框
        pygame.draw.rect(self.screen, edge, rect, 2, border_radius=8)

        if sub_text is None:
            # 居中文字（带阴影）
            txt_shadow = font.render(text, True, (0, 0, 0))
            txt = font.render(text, True, text_color)
            self.screen.blit(txt_shadow, (rect.centerx - txt_shadow.get_width() // 2 + 1, rect.centery - txt_shadow.get_height() // 2 + 1))
            self.screen.blit(txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2))
        else:
            # 主文字（顶部）+ 费用（底部，金色小字）
            txt_shadow = font.render(text, True, (0, 0, 0))
            txt = font.render(text, True, text_color)
            self.screen.blit(txt_shadow, (rect.centerx - txt_shadow.get_width() // 2 + 1, rect.y + 2))
            self.screen.blit(txt, (rect.centerx - txt.get_width() // 2, rect.y + 1))

            font_cost = fonts.get(14)
            sub_shadow = font_cost.render(sub_text, True, (0, 0, 0))
            sub = font_cost.render(sub_text, True, (255, 215, 0))
            sy = rect.y + rect.height - font_cost.get_height() - 2
            self.screen.blit(sub_shadow, (rect.centerx - sub_shadow.get_width() // 2 + 1, sy + 1))
            self.screen.blit(sub, (rect.centerx - sub.get_width() // 2, sy))

    def _draw_upgrade_preview(self, tower, up_btn, px) -> None:
        """鼠标悬浮升级按钮时，在按钮下方显示升级后属性预览。"""
        preview = tower.preview_upgrade_stats()
        if preview is None:
            return

        font_title = fonts.get(16)
        font_body = fonts.get(15)

        # 构造对比行（只有变化的属性才列出）
        rows = [(font_title, (255, 215, 0), f"升至 Lv.{preview['level']}")]
        if preview['damage'] != tower.damage:
            rows.append((font_body, (235, 235, 235), f"伤害 {tower.damage} → {preview['damage']}"))
        if preview['range'] != tower.range:
            rows.append((font_body, (235, 235, 235), f"射程 {tower.range} → {preview['range']}"))
        if abs(preview['fire_rate'] - tower.fire_rate) > 0.01:
            rows.append((font_body, (235, 235, 235),
                         f"攻速 {tower.fire_rate:.1f} → {preview['fire_rate']:.1f}/秒"))
        if abs(preview['crit_chance'] - tower.crit_chance) > 0.001:
            rows.append((font_body, (235, 235, 235),
                         f"暴击 {tower.crit_chance * 100:.0f}% → {preview['crit_chance'] * 100:.0f}%"))

        line_h = 19
        pad_x, pad_y = 10, 7
        height = len(rows) * line_h + pad_y * 2

        # 面板固定为侧栏宽度，左对齐
        w = SIDE_PANEL - 16
        x = px + 8
        y = up_btn.bottom + 8
        # 若下方空间不足，放到按钮上方
        if y + height > HEIGHT - 6:
            y = up_btn.top - 8 - height

        box = pygame.Surface((w, height), pygame.SRCALPHA)
        pygame.draw.rect(box, (15, 14, 24, 240), box.get_rect(), border_radius=6)
        # 边框用升级按钮的绿色系，视觉上呼应
        pygame.draw.rect(box, (110, 200, 130, 240), box.get_rect(), 1, border_radius=6)

        for i, (font, color, text) in enumerate(rows):
            surf = font.render(text, True, color)
            box.blit(surf, (pad_x, pad_y + i * line_h))

        self.screen.blit(box, (int(x), int(y)))

    # ============================================================
    #  悬浮提示
    # ============================================================

    def _draw_hover_tower_info(self, hovered_tower, mouse_pos) -> None:
        if hovered_tower is None:
            return

        font_small = fonts.get(18)
        stats = CONFIG.tower_types[hovered_tower]
        lines = [
            f"名称: {stats.name}",
            f"伤害: {stats.damage}",
            f"射程: {stats.range}",
            f"攻速: {stats.fire_rate}/秒",
        ]
        if stats.laser:
            lines.append("特殊: 激光射线，伤害递减")
        elif stats.venom:
            lines.append("特殊: 毒液持续伤害，可传染")
        elif stats.special == 'slow':
            lines.append("特殊: 减速敌人，概率冻结")
        elif stats.crit_chance > 0:
            lines.append(f"特殊: 暴击率 {stats.crit_chance * 100:.0f}%")
        elif stats.rapid_fire:
            lines.append("特殊: 连续攻击加速")

        upgrade_cost = CONFIG.upgrade_costs[hovered_tower][0]
        lines.append(f"升级费用: {upgrade_cost} (2级)")

        max_width = max(font_small.size(line)[0] for line in lines) + 20
        height = len(lines) * 20 + 20
        box = pygame.Surface((max_width, height), pygame.SRCALPHA)
        pygame.draw.rect(box, (0, 0, 0, 180), box.get_rect(), border_radius=8)
        for i, line in enumerate(lines):
            text = font_small.render(line, True, (255, 255, 255))
            box.blit(text, (10, 10 + i * 20))

        mx, my = mouse_pos
        x = mx - max_width - 10 if mx > MAP_W else mx + 10
        # 边界钳制：tooltip 不能超出屏幕左右/上下
        x = max(4, min(x, WIDTH - max_width - 4))
        y = max(4, my - height // 2)
        y = min(y, HEIGHT - height - 4)
        self.screen.blit(box, (int(x), int(y)))

    # ============================================================
    #  锁定画面
    # ============================================================

    def draw_lock_screen(self, window_screen: pygame.Surface) -> None:
        font_big = fonts.get(36)
        font_med = fonts.get(24)
        font_small = fonts.get(18)

        window_screen.fill((0, 0, 0))
        text1 = font_big.render("游戏已被锁定", True, (255, 0, 0))
        text2 = font_med.render("超出运行期限，无法启动", True, (255, 255, 255))
        text3 = font_small.render("点击任意位置或关闭窗口退出", True, (200, 200, 200))
        window_screen.blit(text1, (WIDTH // 2 - text1.get_width() // 2, HEIGHT // 2 - 60))
        window_screen.blit(text2, (WIDTH // 2 - text2.get_width() // 2, HEIGHT // 2))
        window_screen.blit(text3, (WIDTH // 2 - text3.get_width() // 2, HEIGHT // 2 + 40))
