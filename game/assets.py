"""
资源管理模块 - 统一管理音效、图片、字体等资源的加载与访问。
"""
import os
from typing import Dict, List, Optional

import pygame

from game.utils import resource_path


class AudioManager:
    """音效与背景音乐管理器"""

    def __init__(self):
        self._sounds: Dict[str, Optional[pygame.mixer.Sound]] = {}
        self._current_bgm: str = ""

    def load_sounds(self) -> None:
        """加载所有音效文件。"""
        sound_dir = resource_path("assets/sounds")
        sound_files = {
            'machine_shot': 'machine_shot.mp3',
            'cannon_shot': 'cannon_shot.mp3',
            'ice_shot': 'ice_shot.mp3',
            'laser_shot': 'laser_shot.mp3',
            'venom_shot': 'venom_shot.mp3',
            'enemy_death': 'enemy_death.mp3',
            'boss_warning': 'boss_warning.mp3',
            'enemy_reach': 'enemy_reach.mp3',
            'level_complete': 'level_complete.mp3',
        }
        for key, filename in sound_files.items():
            try:
                path = os.path.join(sound_dir, filename)
                self._sounds[key] = pygame.mixer.Sound(path)
                print(f"音效加载成功: {filename}")
            except pygame.error as e:
                print(f"音效加载失败 {filename}: {e}")
                self._sounds[key] = None

    def play(self, name: str) -> None:
        """播放指定音效。"""
        sound = self._sounds.get(name)
        if sound is not None:
            sound.play()

    def play_bgm(self, track_name: str, loop: int = -1) -> None:
        """播放背景音乐。若指定音轨不存在，降级复用第一关 BGM。"""
        resolved = self._resolve_bgm(track_name)
        if resolved is None:
            return
        if self._current_bgm == resolved:
            return
        self._current_bgm = resolved
        try:
            pygame.mixer.music.stop()
            path = resource_path(f"assets/music/{resolved}.mp3")
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0.5)
            pygame.mixer.music.play(loop)
        except pygame.error as e:
            print(f"背景音乐加载失败 {resolved}: {e}")

    def _resolve_bgm(self, track_name: str) -> Optional[str]:
        """解析可用的背景音乐音轨名：文件不存在时回退到 level_1_bgm。"""
        music_dir = resource_path("assets/music")
        if os.path.exists(os.path.join(music_dir, f"{track_name}.mp3")):
            return track_name
        fallback = "level_1_bgm"
        if os.path.exists(os.path.join(music_dir, f"{fallback}.mp3")):
            return fallback
        return None


class ImageManager:
    """图片资源管理器"""

    def __init__(self):
        self._enemy_frames: Optional[Dict[str, List[pygame.Surface]]] = None
        self._tower_sprites: Optional[Dict[str, pygame.Surface]] = None
        self._logo: Optional[pygame.Surface] = None
        self._logo_small: Optional[pygame.Surface] = None

    def load_enemy_images(self) -> None:
        """加载敌人动画帧（每种敌人3帧行走动画）。"""
        frames: Dict[str, List[pygame.Surface]] = {}
        base_path = resource_path("assets/enemies")
        try:
            for name in ('normal', 'fast', 'tank', 'boss', 'flying'):
                frame_list = []
                for i in range(3):
                    path = os.path.join(base_path, f"{name}_{i}.png")
                    img = pygame.image.load(path).convert_alpha()
                    frame_list.append(img)
                frames[name] = frame_list
            self._enemy_frames = frames
            print("敌人动画帧加载成功")
        except pygame.error as e:
            print(f"敌人动画帧加载失败: {e}，将使用圆形代替")
            self._enemy_frames = None

    def get_enemy_frames(self, enemy_type: str) -> Optional[List[pygame.Surface]]:
        """获取指定类型敌人的动画帧列表。"""
        if self._enemy_frames is None:
            return None
        return self._enemy_frames.get(enemy_type)

    def get_enemy_image(self, enemy_type: str) -> Optional[pygame.Surface]:
        """获取指定类型敌人的第一帧图片（兼容接口）。"""
        frames = self.get_enemy_frames(enemy_type)
        if frames:
            return frames[0]
        return None

    def load_tower_sprites(self) -> None:
        """加载防御塔精灵图。"""
        sprites: Dict[str, pygame.Surface] = {}
        base_path = resource_path("assets/towers")
        try:
            for name in ('machine', 'cannon', 'ice', 'sniper', 'venom'):
                sprites[name] = pygame.image.load(
                    os.path.join(base_path, f"{name}.png")
                ).convert_alpha()
            self._tower_sprites = sprites
            print("防御塔精灵加载成功")
        except pygame.error as e:
            print(f"防御塔精灵加载失败: {e}，将使用几何图形代替")
            self._tower_sprites = None

    def get_tower_sprite(self, tower_type: str) -> Optional[pygame.Surface]:
        """获取指定类型防御塔的精灵图。"""
        if self._tower_sprites is None:
            return None
        return self._tower_sprites.get(tower_type)

    def load_path_markers(self) -> None:
        """加载路径起点/终点图标。"""
        self._path_markers: Dict[str, pygame.Surface] = {}
        base_path = resource_path("assets/backgrounds")
        try:
            for name in ('spawn', 'exit'):
                self._path_markers[name] = pygame.image.load(
                    os.path.join(base_path, f"path_{name}.png")
                ).convert_alpha()
            print("路径图标加载成功")
        except pygame.error as e:
            print(f"路径图标加载失败: {e}")
            self._path_markers = {}

    def get_path_marker(self, name: str) -> Optional[pygame.Surface]:
        """获取路径标记图片（spawn 或 exit）。"""
        markers = getattr(self, '_path_markers', None)
        if not markers:
            return None
        return markers.get(name)

    def load_logo(self) -> None:
        """加载游戏 Logo（大尺寸菜单用 + 小尺寸窗口图标用）。"""
        try:
            path = resource_path("assets/images/logo.png")
            self._logo = pygame.image.load(path).convert_alpha()
            self._logo_small = pygame.transform.smoothscale(self._logo, (64, 64))
            print("游戏 Logo 加载成功")
        except pygame.error as e:
            print(f"游戏 Logo 加载失败: {e}")
            self._logo = None
            self._logo_small = None

    def get_logo(self) -> Optional[pygame.Surface]:
        """获取大尺寸 Logo（菜单用）。"""
        return self._logo

    def get_logo_small(self) -> Optional[pygame.Surface]:
        """获取小尺寸 Logo（窗口图标用）。"""
        return self._logo_small

    def load_background(self, level: int, map_w: int, height: int) -> Optional[pygame.Surface]:
        """加载关卡背景图片。"""
        try:
            path = resource_path(f"assets/backgrounds/level_{level}.png")
            bg = pygame.image.load(path).convert()
            bg = pygame.transform.scale(bg, (map_w, height))
            print(f"加载背景: {path}")
            return bg
        except pygame.error as e:
            print(f"背景图片加载失败: {e}，使用默认背景")
            return None


class FontManager:
    """字体管理器，缓存已创建的字体实例。"""

    def __init__(self):
        self._cache: Dict[int, pygame.font.Font] = {}

    def get(self, size: int) -> pygame.font.Font:
        """获取指定大小的字体（带缓存）。"""
        if size in self._cache:
            return self._cache[size]

        font_path = resource_path("assets/fonts/simhei.ttf")
        font: pygame.font.Font
        try:
            font = pygame.font.Font(font_path, size)
        except Exception:
            try:
                font = pygame.font.SysFont("simhei", size)
            except Exception:
                font = pygame.font.Font(None, size)

        self._cache[size] = font
        return font


# ---------- 全局资源实例 ----------
audio = AudioManager()
images = ImageManager()
fonts = FontManager()
