"""
特效模块 - 粒子系统与激光效果，使用对象池避免频繁 GC。
"""
import math
from typing import Tuple

import pygame

from game.config import MAP_W, HEIGHT


class Particle:
    """单个粒子"""

    __slots__ = ('active', 'x', 'y', 'vx', 'vy', 'life', 'max_life', 'color', 'radius')

    def __init__(self):
        self.active: bool = False
        self.x: float = 0.0
        self.y: float = 0.0
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.life: float = 0.0
        self.max_life: float = 0.0
        self.color: Tuple[int, int, int] = (0, 0, 0)
        self.radius: int = 0

    def update(self, dt: float) -> None:
        if not self.active:
            return
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        self.vx *= 0.98
        self.vy *= 0.98
        if self.life <= 0:
            self.active = False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.active or self.life <= 0:
            return
        alpha = max(0, int(255 * (self.life / self.max_life)))
        r = max(1, int(self.radius * (self.life / self.max_life)))
        temp = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(temp, (*self.color, alpha), (r, r), r)
        surface.blit(temp, (int(self.x) - r, int(self.y) - r))


class ParticlePool:
    """粒子对象池，预分配固定数量的粒子。"""

    def __init__(self, size: int = 600):
        self.pool = [Particle() for _ in range(size)]
        self._index: int = 0

    def spawn(
        self, x: float, y: float, vx: float, vy: float,
        life: float, color: Tuple[int, int, int], radius: int,
    ) -> None:
        p = self.pool[self._index]
        self._index = (self._index + 1) % len(self.pool)
        p.active = True
        p.x, p.y = x, y
        p.vx, p.vy = vx, vy
        p.life = life
        p.max_life = life
        p.color = color
        p.radius = radius

    def update(self, dt: float) -> None:
        for p in self.pool:
            if p.active:
                p.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        for p in self.pool:
            if p.active:
                p.draw(surface)


class LaserEffect:
    """单条激光效果"""

    __slots__ = ('active', 'x', 'y', 'angle', 'length', 'color', 'age', 'life')

    def __init__(self):
        self.active: bool = False
        self.x: float = 0.0
        self.y: float = 0.0
        self.angle: float = 0.0
        self.length: float = 0.0
        self.color: Tuple[int, int, int] = (0, 0, 0)
        self.age: float = 0.0
        self.life: float = 0.15

    def update(self, dt: float) -> None:
        self.age += dt
        if self.age >= self.life:
            self.active = False


class LaserManager:
    """激光对象池。"""

    def __init__(self, max_lasers: int = 30):
        self.pool = [LaserEffect() for _ in range(max_lasers)]
        self._index: int = 0

    def add(self, x: float, y: float, angle: float, length: float, color: Tuple[int, int, int]) -> None:
        e = self.pool[self._index]
        self._index = (self._index + 1) % len(self.pool)
        e.active = True
        e.x, e.y = x, y
        e.angle = angle
        e.length = length
        e.color = color
        e.age = 0

    def update(self, dt: float) -> None:
        for e in self.pool:
            if e.active:
                e.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        temp = pygame.Surface((MAP_W, HEIGHT), pygame.SRCALPHA)
        for e in self.pool:
            if not e.active:
                continue
            end_x = e.x + math.cos(e.angle) * e.length
            end_y = e.y + math.sin(e.angle) * e.length
            pygame.draw.line(temp, (*e.color, 40), (e.x, e.y), (end_x, end_y), 12)
            pygame.draw.line(temp, (*e.color, 80), (e.x, e.y), (end_x, end_y), 8)
            pygame.draw.line(temp, e.color, (e.x, e.y), (end_x, end_y), 4)
            pygame.draw.line(temp, (255, 255, 255), (e.x, e.y), (end_x, end_y), 2)
        surface.blit(temp, (0, 0))
