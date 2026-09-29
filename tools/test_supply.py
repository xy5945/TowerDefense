# -*- coding: utf-8 -*-
"""打码补给的端到端逻辑测试（不弹窗口，直接驱动 Game 状态机）。

跑法：SDL_VIDEODRIVER=dummy venv/Scripts/python.exe tools/test_supply.py

测的是规则本身：什么时候弹、给多少钱、代码难度对不对、打对了发不发、
放弃了给不给、漏怪 7 次弹不弹。渲染不在测试范围内（那要人眼看着）。
"""
import os
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from game.game import Game  # noqa: E402
from game.config import (  # noqa: E402
    CODE_LEVEL_BY_WAVE, LEAK_RESCUE_AT, LEAK_RESCUE_HEAL,
    SUPPLY_FIRST_WAVE, SUPPLY_LAST_WAVE, SUPPLY_POPUP_DELAY, supply_gold,
)

PASS = 0
FAIL = 0


def check(name, got, want):
    global PASS, FAIL
    ok = got == want
    if ok:
        PASS += 1
        print('  [OK]   %-42s %r' % (name, got))
    else:
        FAIL += 1
        print('  [FAIL] %-42s 得到 %r，应为 %r' % (name, got, want))


def new_game(level=1):
    pygame.init()
    pygame.display.set_mode((960, 600))
    g = Game('data')
    g.current_level = level
    g.reset_game()
    g.state = 'playing'
    return g


def end_wave(g, wave, settle=True):
    """模拟第 wave 波打完清场。

    settle=True 时把「清场到弹窗」那一秒缓冲也走完，等价于玩家什么都不做等着。
    """
    g.wave = wave
    g.wave_active = True
    g.enemies = []
    g.spawn_queue = []
    g.update(0.016)
    if settle and g.supply_delay > 0:
        g.update(SUPPLY_POPUP_DELAY)


def type_text(g, text):
    """走真正的输入通道把一段代码打进去。

    可见字符走 TEXTINPUT（中文输入法就是这条路），回车/退格/ESC 走 KEYDOWN。
    """
    for ch in text:
        if ch == '\n':
            ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode='\r')
            g._handle_supply_key(ev)
        elif ch == '\x08':
            ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, unicode='')
            g._handle_supply_key(ev)
        else:
            g.handle_textinput(ch)


print('=' * 70)
print('一、什么时候弹（第 1 波起每波都弹）')
print('=' * 70)

g = new_game(1)
end_wave(g, 1)
check('第 1 波打完就弹', g.state, 'supply')
check('第 1 波是金币补给', g.supply_kind, 'gold')
check('第 1 关起手 = 10 金币', g.supply_gold, 10)

g = new_game(1)
end_wave(g, 2)
check('第 2 波打完弹出来', g.state, 'supply')
check('第 2 波是金币补给', g.supply_kind, 'gold')
check('第 1 关第 2 波 = 20 金币', g.supply_gold, 20)

print()
print('=' * 70)
print('二、金币：(关数-1)×10 + 波数×10')
print('=' * 70)

# 第 1 关：第 1 波 10，一路 +10 到 90
g = new_game(1)
prev = 0
for wave in range(1, 10):
    g = new_game(1)
    end_wave(g, wave)
    want = supply_gold(1, wave)
    check('第 1 关第 %d 波 = %d' % (wave, want), g.supply_gold, want)
    if prev:
        check('　第 %d 波比第 %d 波多 10' % (wave, wave - 1),
              g.supply_gold - prev, 10)
    prev = g.supply_gold

check('第 2 关第 1 波 20', supply_gold(2, 1), 20)
check('第 3 关第 1 波 30', supply_gold(3, 1), 30)
check('第 5 关第 1 波 50', supply_gold(5, 1), 50)
check('第 10 关第 9 波 180', supply_gold(10, 9), 180)

# 走一遍真实流程，确认game 里拿到的钱跟公式一致（不是另一套算法）
for level, wave in ((2, 1), (2, 5), (3, 1), (4, 7)):
    g = new_game(level)
    end_wave(g, wave)
    check('第 %d 关第 %d 波实发金额' % (level, wave),
          g.supply_gold, supply_gold(level, wave))

g = new_game(1)
end_wave(g, 1)
gold_w1 = g.supply_gold
g._decline_supply()          # 放弃，好接着测下一波
end_wave(g, 2)
check('放弃了不原地踏步', g.supply_gold, gold_w1 + 10)

print()
print('=' * 70)
print('三、代码难度档位')
print('=' * 70)

for wave, want in sorted(CODE_LEVEL_BY_WAVE.items()):
    g = new_game(1)
    end_wave(g, wave)
    check('第 %d 波 -> Lv%d' % (wave, want), g.supply_level, want)

print()
print('=' * 70)
print('四、打对了就发奖')
print('=' * 70)

g = new_game(1)
end_wave(g, 1)
money_before = g.money
g._start_typing()
check('进入打码阶段', g.supply_phase, 'typing')
target = g.supply_challenge['text']
check('题目非空', bool(target), True)
type_text(g, target)
check('全部打对', g.supply_match['done'], True)
g.update(0.5)                # 收尾计时 0.45 秒后进发奖
check('金币到账', g.money - money_before, supply_gold(1, 1))
check('回到游戏', g.state, 'playing')
check('已领次数 +1', g.supply_taken, 1)

print()
print('=' * 70)
print('五、放弃了什么都不给')
print('=' * 70)

g = new_game(1)
end_wave(g, 2)
money_before = g.money
g._decline_supply()
check('金币没变', g.money - money_before, 0)
check('已领次数没变', g.supply_taken, 0)
check('回到游戏', g.state, 'playing')

print()
print('=' * 70)
print('六、漏怪补救：累计 7 次弹一次，回 2 血')
print('=' * 70)

g = new_game(1)
g.leak_count = LEAK_RESCUE_AT - 1
end_wave(g, 2)
check('漏 6 次：先弹金币补给', g.supply_kind, 'gold')
g._decline_supply()

g = new_game(1)
g.leak_count = LEAK_RESCUE_AT
end_wave(g, 3)
check('漏 7 次：先弹补救', g.supply_kind, 'heal')
check('补救用最高级代码', g.supply_level, 8)
lives_before = g.lives
g._start_typing()
type_text(g, g.supply_challenge['text'])
g.update(0.5)
check('回了 2 点血', g.lives - lives_before, LEAK_RESCUE_HEAL)
check('漏怪计数清零', g.leak_count, 0)
check('补救完接着弹金币补给', g.supply_kind, 'gold')

g = new_game(1)
g.leak_count = LEAK_RESCUE_AT
end_wave(g, 3)
lives_before = g.lives
g._decline_supply()
check('补救放弃了不回血', g.lives - lives_before, 0)
check('放弃了也清零（不纠缠）', g.leak_count, 0)

print()
print('=' * 70)
print('七、没有开关：1-9 波每波都弹，第 10 波直接通关')
print('=' * 70)

for wave in range(1, 11):
    g = new_game(1)
    end_wave(g, wave)
    if SUPPLY_FIRST_WAVE <= wave <= SUPPLY_LAST_WAVE:
        want = 'supply'
    else:
        want = 'level_complete'
    check('第 %d 波 = %s' % (wave, want), g.state, want)

print()
print('=' * 70)
print('八、第 10 波打完直接通关，不再弹补给')
print('=' * 70)

g = new_game(1)
g.wave = 10
g.wave_active = True
g.enemies = []
g.spawn_queue = []
g.update(0.016)
check('第 10 波不弹补给', g.state, 'level_complete')
check('没排任何补给', g.supply_queue, [])

print()
print('=' * 70)
print('九、打错要能报错')
print('=' * 70)

g = new_game(1)
end_wave(g, 7)               # 多行档
g._start_typing()
target = g.supply_challenge['text']
type_text(g, target[:3] + 'X')
check('打错会标错', g.supply_match['err'], True)
check('打错不发奖', g.supply_done_t, -1.0)
type_text(g, '\x08')         # 退格删掉那个 X
check('退格后回到正轨', g.supply_match['err'], False)

print()
print('=' * 70)
print('十、清场后先缓一秒再弹窗')
print('=' * 70)

g = new_game(1)
end_wave(g, 2, settle=False)
check('刚清场：还没弹窗', g.state, 'playing')
check('缓冲计时已启动', g.supply_delay > 0, True)
g.update(SUPPLY_POPUP_DELAY * 0.5)
check('半秒时仍未弹窗', g.state, 'playing')
g.update(SUPPLY_POPUP_DELAY * 0.6)
check('一秒后弹出来', g.state, 'supply')

g = new_game(1)
end_wave(g, 2, settle=False)
g.start_wave()                  # 缓冲没走完就点了开战
check('提前开战：补给照弹', g.state, 'supply')
check('金额仍按旧波次算', g.supply_gold, supply_gold(1, 2))
check('没被算成下一波的金额',
      g.supply_gold == supply_gold(1, 3), False)
check('波次已经开出来', g.wave_active, True)

print()
print('=' * 70)
print('十一、中文输入法：能打进去，也能删掉')
print('=' * 70)

g = new_game(1)
end_wave(g, 2)
g._start_typing()
check('开了系统文本输入', g.text_input_on, True)
g.handle_textediting('nihao')    # 拼音拼到一半
check('拼字只回显不算输入', g.supply_typed, '')
check('拼字显示在回显行', g.supply_ime, 'nihao')
g.handle_textinput('你')         # 上屏一个汉字
check('汉字上屏了', g.supply_typed, '你')
check('上屏后回显清空', g.supply_ime, '')
check('汉字算打错（题目是英文代码）', g.supply_match['err'], True)
ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, unicode='')
g._handle_supply_key(ev)
check('汉字能退格删掉', g.supply_typed, '')
check('删完回到正轨', g.supply_match['err'], False)

print()
print('=' * 70)
print('十二、KEYDOWN 兜底不会重复上屏')
print('=' * 70)

g = new_game(1)
g._ime_ok = True                # 模拟「TEXTINPUT 通道已确认可用」
end_wave(g, 2)
g._start_typing()
ev = pygame.event.Event(pygame.KEYDOWN, key=0, unicode='i')
g._handle_supply_key(ev)
g.handle_textinput('i')
check('只上屏一个 i，没有变成 ii', g.supply_typed, 'i')

g = new_game(1)
end_wave(g, 2)
g._start_typing()
ev = pygame.event.Event(pygame.KEYDOWN, key=0, unicode='i')
g._handle_supply_key(ev)        # 只发 KEYDOWN，TEXTINPUT 始终不来
g.update(0.016)                 # 下一帧兜底补上
check('TEXTINPUT 不来时 KEYDOWN 兜底', g.supply_typed, 'i')
g.update(0.016)
check('兜底只补一次', g.supply_typed, 'i')

print()
print('=' * 70)
print('十三、状态栏不再报字符计数')
print('=' * 70)

g = new_game(1)
end_wave(g, 7)
g._start_typing()
type_text(g, g.supply_challenge['text'][:3])
check('提示里没有 X/Y 计数', '/' in g.supply_status, False)
check('多行题提示换行键', g.supply_status, '换行按回车')

print()
print('=' * 70)
print('通过 %d 项，失败 %d 项' % (PASS, FAIL))
print('=' * 70)
sys.exit(1 if FAIL else 0)
