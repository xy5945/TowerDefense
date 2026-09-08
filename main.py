"""
塔防游戏 - 主入口
重构版本：模块化架构，存档系统，配置外置。
"""
import sys
import datetime

import pygame

from game.config import WIDTH, HEIGHT, LOCK_DATE
from game.assets import audio, images
from game.game import Game
from game.renderer import Renderer


def is_locked() -> bool:
    lock = datetime.datetime.strptime(LOCK_DATE, "%Y-%m-%d")
    return datetime.datetime.now() > lock


def show_lock_window(window_screen: pygame.Surface, renderer: Renderer) -> None:
    renderer.draw_lock_screen(window_screen)
    pygame.display.flip()
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type in (pygame.QUIT, pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                waiting = False
    pygame.quit()
    sys.exit()


def main() -> None:
    pygame.init()
    pygame.mixer.init()
    pygame.mixer.set_num_channels(16)

    window_screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("守护稚码王国")
    clock = pygame.time.Clock()
    canvas = pygame.Surface((WIDTH, HEIGHT))

    renderer = Renderer(canvas)

    # 锁定检测
    if is_locked():
        show_lock_window(window_screen, renderer)

    # 加载资源
    audio.load_sounds()
    images.load_enemy_images()
    images.load_tower_sprites()
    images.load_path_markers()
    images.load_logo()
    if images.get_logo_small():
        pygame.display.set_icon(images.get_logo_small())

    # 数据目录
    import os
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

    # 创建游戏实例
    game = Game(data_dir)

    # 主循环
    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                window_screen = pygame.display.set_mode(
                    (event.w, event.h), pygame.RESIZABLE
                )
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                scale_x = WIDTH / window_screen.get_width()
                scale_y = HEIGHT / window_screen.get_height()
                canvas_x = mx * scale_x
                canvas_y = my * scale_y
                game.handle_click((canvas_x, canvas_y), event.button)
            elif event.type == pygame.MOUSEMOTION:
                mx, my = event.pos
                scale_x = WIDTH / window_screen.get_width()
                scale_y = HEIGHT / window_screen.get_height()
                canvas_x = mx * scale_x
                canvas_y = my * scale_y
                game.update_hover((canvas_x, canvas_y))
            elif event.type == pygame.KEYDOWN:
                game.handle_debug_key(event.key)
            elif event.type == pygame.MOUSEWHEEL:
                game.handle_scroll(event.y)

        game.update(dt)
        game.draw(renderer)

        # 缩放输出到窗口
        scaled_surface = pygame.transform.scale(
            canvas, (window_screen.get_width(), window_screen.get_height())
        )
        window_screen.blit(scaled_surface, (0, 0))
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
