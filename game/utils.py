"""
工具函数模块 - 路径计算、网格对齐、绘图辅助等通用函数。
"""
import math
import sys
import os
from typing import Tuple, List

import pygame

from game.config import GRID_SIZE, MAP_W, HEIGHT


def resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径，兼容 PyInstaller 打包后的环境。"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def point_near_path(pos: Tuple[int, int], path: List[Tuple[int, int]], threshold: int = 30) -> bool:
    """判断一个点是否靠近路径的任意线段。"""
    px, py = pos
    for i in range(len(path) - 1):
        ax, ay = path[i]
        bx, by = path[i + 1]
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            d = math.hypot(px - ax, py - ay)
        else:
            t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
            t = max(0, min(1, t))
            proj_x = ax + t * dx
            proj_y = ay + t * dy
            d = math.hypot(px - proj_x, py - proj_y)
        if d < threshold:
            return True
    return False


def snap_to_grid(pos: Tuple[float, float]) -> Tuple[int, int]:
    """将坐标对齐到网格。"""
    x, y = pos
    gs = GRID_SIZE
    gx = round(x / gs) * gs
    gy = round(y / gs) * gs
    gx = max(gs // 2, min(gx, MAP_W - gs // 2))
    gy = max(gs // 2, min(gy, HEIGHT - gs // 2))
    return gx, gy


# ---------- 绘图辅助函数 ----------

def draw_transparent_circle(
    surface: pygame.Surface,
    color: Tuple[int, int, int],
    center: Tuple[int, int],
    radius: int,
    alpha: int = 100,
) -> None:
    """绘制半透明圆形。"""
    temp = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(temp, (*color, alpha), (radius, radius), radius)
    surface.blit(temp, (center[0] - radius, center[1] - radius))


def draw_transparent_rect(
    surface: pygame.Surface,
    color: Tuple[int, int, int],
    rect: pygame.Rect,
    alpha: int = 100,
) -> None:
    """绘制半透明矩形。"""
    temp_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(temp_surf, (*color, alpha), temp_surf.get_rect())
    surface.blit(temp_surf, rect.topleft)


def draw_dashed_circle(
    surface: pygame.Surface,
    color: Tuple[int, int, int],
    center: Tuple[int, int],
    radius: int,
    dash: int = 12,
    gap: int = 8,
    width: int = 2,
) -> None:
    """绘制虚线圆。"""
    circ = 2 * math.pi * radius
    if circ <= 0:
        return
    total = dash + gap
    n = int(circ / total) + 1
    rect = pygame.Rect(center[0] - radius, center[1] - radius, radius * 2, radius * 2)
    for i in range(n):
        a1 = (i * total / circ) * 2 * math.pi
        a2 = ((i * total + dash) / circ) * 2 * math.pi
        a1 %= 2 * math.pi
        a2 %= 2 * math.pi
        pygame.draw.arc(surface, color, rect, a1, a2, width)


def draw_glow(
    surface: pygame.Surface,
    pos: Tuple[int, int],
    color: Tuple[int, int, int],
    radius: int,
    max_alpha: int = 128,
) -> None:
    """绘制发光效果。"""
    for r, alpha in [
        (radius, max_alpha // 4),
        (radius * 2 // 3, max_alpha // 2),
        (radius // 2, max_alpha),
    ]:
        draw_transparent_circle(surface, color, pos, r, alpha=alpha)


