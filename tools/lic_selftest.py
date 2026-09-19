# -*- coding: utf-8 -*-
"""
授权体系自检 —— 用法：python main.py --lictest

不开窗口、不碰玩家的真实授权文件（全部走临时目录），跑完自己清理。
覆盖：申请码、跨语言一致性、四类拒绝、激活/续期/一码一用、天数判定、
时钟回拨、密钥缺失降级、删档防复用、埋点老格式兼容。

改动这一块之后一定要跑一遍 —— 授权出问题时症状都很安静
（比如"某个学生怎么都激活不了"），靠肉眼读代码基本看不出来。
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import license as lic  # noqa: E402

# 以下三个常量都是发码工具真实产出的码，专门用来验「两端算法有没有对上」。
#   python keygen.py -g tower_defense  -m GZTX-WIP2 -d 30
#   python keygen.py -g tower_defense  -m GZTX-WIP2 -d 90
#   python keygen.py -g code_survivors -m GZTX-WIP2 -d 30   （别款游戏的码）
TOOL_MACHINE = "GZTX-WIP2"
TOOL_CODE = "AI3G-O6ZB-7IAB-5KHZ-3PPA"    # 本机 · 30 天
TOOL_CODE2 = "AI3G-O6ZB-7IAF-UBG5-HMOQ"   # 本机 · 90 天
OTHER_GAME_CODE = "AE3G-O6ZB-7IAB-4V66-BIAQ"   # 《代码幸存者》的码

_ok_count = 0
_fail_count = 0


def _ok(flag: bool) -> str:
    global _ok_count, _fail_count
    if flag:
        _ok_count += 1
        return "OK"
    _fail_count += 1
    return "失败"


def _make_code(gid: int, machine5: bytes, days: int) -> str:
    """用游戏端自己的算法造一个码 —— 扮演发码工具，专门测拒绝分支。"""
    import hashlib
    import hmac as _hmac
    payload = bytes([gid]) + machine5 + days.to_bytes(2, "big")
    mac = _hmac.new(lic.secret(), payload, hashlib.sha256).digest()[:4]
    return lic.group(lic.b32_encode(payload + mac))


def _temp_state(tmpdir, name="lic.json", aux=".state", use_aux=True):
    """造一个写到临时目录的授权状态，并把模块单例指过去。"""
    lic.state = lic.LicenseState(
        main_path=os.path.join(tmpdir, name),
        aux_path=os.path.join(tmpdir, aux),
        use_aux=use_aux,
    )
    return lic.state


def _set_state(start: int, days: int, licensed: bool = True) -> None:
    lic.state.start_day = start
    lic.state.days = days
    lic.state.licensed = licensed


# ---------------------------------------------------------------- 各项用例

def _t_machine() -> None:
    a = lic.machine_code()
    b = lic.machine_code()
    raw = lic.machine_bytes()
    ok = (a == b and len(lic.clean(a)) == lic.MACHINE_CHARS
          and len(raw) == lic.MACHINE_BYTES
          and len(lic.b32_decode(a)) == lic.MACHINE_BYTES)
    print("  1 申请码 · 本机 %s · 两次一致=%s · 8 字符=%s · %s" % (
        a, "是" if a == b else "否",
        "是" if len(lic.clean(a)) == 8 else "否（%d）" % len(lic.clean(a)),
        _ok(ok)))


def _t_tool_code() -> None:
    saved = lic._machine_cache
    lic._machine_cache = lic.b32_decode(TOOL_MACHINE)
    r = lic.verify(TOOL_CODE)
    lic._machine_cache = lic.b32_decode("A3K7-M2XT")
    r_other = lic.verify(TOOL_CODE)
    lic._machine_cache = lic.b32_decode(TOOL_MACHINE)
    ok = bool(r["ok"]) and int(r["days"]) == 30 and not bool(r_other["ok"])
    print("  2 工具真码 · 本机=%s（%d 天）· 换台机器=%s · %s" % (
        "通过" if r["ok"] else "被拒(%s)" % r["reason"], int(r["days"]),
        "被拒" if not r_other["ok"] else "竟然通过", _ok(ok)))
    lic._machine_cache = saved


def _t_reject() -> None:
    flat = lic.clean(TOOL_CODE)
    i = len(flat) - 3
    ch = flat[i]
    tampered = flat[:i] + ("A" if ch != "A" else "B") + flat[i + 1:]
    r1 = lic.verify(tampered)
    r2 = lic.verify("AE")
    r3 = lic.verify(OTHER_GAME_CODE)
    m5 = lic.b32_decode(TOOL_MACHINE)
    saved = lic._machine_cache
    lic._machine_cache = m5
    r4 = lic.verify(_make_code(lic.GAME_ID, m5, 30))
    lic._machine_cache = saved
    ok = (not r1["ok"] and not r2["ok"] and not r3["ok"] and bool(r4["ok"]))
    print("  3 边界 · 改一位=%s · 太短=%s · 别款游戏=%s · 本机自造=%s · %s" % (
        "拒" if not r1["ok"] else "过", "拒" if not r2["ok"] else "过",
        "拒" if not r3["ok"] else "过", "过" if r4["ok"] else "拒", _ok(ok)))


def _t_apply() -> None:
    st = lic.state
    st.licensed = False
    # 首装：7 天试用
    t_left = st.days_left()
    t_lock = st.is_expired()
    # 激活 30 天
    a_ok = st.activate(30, TOOL_CODE)
    a_left = st.days_left()
    # 同一张码再输一次：必须被拒，且天数不能变
    again = lic.verify(TOOL_CODE)
    again_left = st.days_left()
    # 换一张新码：正常续期到 90 天
    b_ok = st.activate(90, TOOL_CODE2)
    b_left = st.days_left()
    # 重新读一遍盘，授权必须还在
    st2 = _temp_state(os.path.dirname(st.main_path_override))
    st2.load()
    after_reload = st2.days_left()
    ok = (t_left == 7 and not t_lock and a_ok and a_left == 30 and a_ok
          and not bool(again["ok"]) and again_left == 30
          and b_ok and b_left == 90 and after_reload == 90)
    print("  4 激活 · 首装试用 %d 天 · 首激活 %d 天 · 同码再输=%s（仍 %d 天）"
          "· 换新码 %d 天 · 重开 %d 天 · %s" % (
              t_left, a_left, "拒" if not bool(again["ok"]) else "竟然通过",
              again_left, b_left, after_reload, _ok(ok)))


def _t_expire() -> None:
    today = lic.today_index()
    _set_state(today, 7, False)
    d0 = lic.state.days_left() == 7 and not lic.state.is_expired()
    _set_state(today - 6, 7, False)
    d6 = lic.state.days_left() == 1 and not lic.state.is_expired()
    _set_state(today - 7, 7, False)
    d7 = lic.state.is_expired()
    _set_state(today - 100, 7, False)
    old = lic.state.is_expired()
    _set_state(today - 500, 0, True)
    perm = lic.state.is_permanent() and not lic.state.is_expired()
    ok = d0 and d6 and d7 and old and perm
    print("  5 天数判定 · 第 1 天剩 7 · 第 7 天剩 1 · 第 8 天锁 · 久过期锁 · 永久不锁 · %s"
          % _ok(ok))


def _t_clock() -> None:
    st = lic.state
    today = lic.today_index()
    _set_state(today - 10, 7, False)
    st.last_seen_day = 0
    used = st.days_used()
    st.last_seen_day = today + 5          # 系统说今天是 X，上次运行却在 X+5 → 时钟被拨回
    used_rollback = st.days_used()
    st.violations = 0
    st.last_seen_ts = lic.now_ts() + 7200  # 上次运行在 2 小时后
    st._clock_check()
    v = st.violations
    ok = (used == 10 and used_rollback == 15 and v == 1)
    print("  6 时钟防护 · 正常用掉 10 天 · 拨回后仍算 15 天（不缩水）· 记违规 %d 次 · %s"
          % (v, _ok(ok)))


def _t_no_secret() -> None:
    saved = lic._secret_cache
    lic._secret_cache = b""
    r = lic.verify(TOOL_CODE)
    ok = (not bool(r["ok"])) and "密钥" in str(r["reason"])
    print("  7 密钥缺失 · 提示「%s」· %s" % (str(r["reason"]), _ok(ok)))
    lic._secret_cache = saved


def _t_delete_save(tmpdir) -> None:
    st = _temp_state(tmpdir, name="d.json", aux="d.state")
    st.load()
    st.activate(30, TOOL_CODE)
    os.remove(st.main_path_override)              # 学生把主记录删了
    st2 = _temp_state(tmpdir, name="d.json", aux="d.state")
    st2.load()                                    # 只剩第二埋点
    r = lic.verify(TOOL_CODE)
    ok = (not st2.licensed) and (not bool(r["ok"]))
    print("  8 删档防复用 · 删主记录后授权已丢=%s · 旧码仍被拒=%s（%s）· %s" % (
        "是" if not st2.licensed else "否",
        "是" if not bool(r["ok"]) else "否", str(r["reason"]), _ok(ok)))


def _t_aux_legacy(tmpdir) -> None:
    """老格式的埋点文件只有一行（起算日），读的时候必须容忍。"""
    path = os.path.join(tmpdir, "old.state")
    today = lic.today_index()
    with open(path, "w", encoding="utf-8") as f:
        f.write("%d\n" % (today - 5))
    st = _temp_state(tmpdir, name="old.json", aux="old.state")
    st.load()
    ok = (st.start_day == today - 5 and st.days_used() == 5
          and lic.today_index() == today)
    print("  9 埋点老格式 · 只有一行也能读 · 起算日捞回 %d（已用 %d 天）· %s" % (
        st.start_day, st.days_used(), _ok(ok)))


# ---------------------------------------------------------------- 界面接线

def _t_menu_flow(tmpdir) -> None:
    """界面接线：到期拦开局、点击进激活页、键盘进得去、提交后状态真的变了。

    这一段最容易悄悄坏掉 —— 逻辑全对但按钮没接上，学生在界面上就是按不动。
    """
    try:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame
        pygame.init()
        pygame.display.set_mode((960, 600))
        from game.assets import audio, images
        from game.game import Game
        from game.config import menu_button_rect
        audio.play_bgm = lambda *a, **k: None      # 无头环境别去碰音频设备
        images.load_logo()
        game = Game(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "data"))
    except Exception as exc:                        # 环境缺 SDL 之类 → 跳过，不算失败
        print(" 10 界面接线 · 跳过（%s: %s）" % (type(exc).__name__, exc))
        return

    bx, by, bw, bh = menu_button_rect(0)
    center = (bx + bw // 2, by + bh // 2)
    today = lic.today_index()

    # 到期：点「开始游戏」不能放行，要把人送到激活页
    _set_state(today - 30, lic.TRIAL_DAYS, False)
    game.state = 'menu'
    game._handle_menu_click(*center)
    blocked = game.state == 'license'

    # 试用中：点「开始游戏」正常进关卡
    _set_state(today, lic.TRIAL_DAYS, False)
    game.state = 'menu'
    game._handle_menu_click(*center)
    allowed = game.state == 'level_intro'

    # 键盘要能进输入框，退格要能删
    game._open_license()
    game.handle_keydown(pygame.event.Event(
        pygame.KEYDOWN, {"key": pygame.K_a, "unicode": "a", "mod": 0}))
    typed = game.license_input
    game.handle_keydown(pygame.event.Event(
        pygame.KEYDOWN, {"key": pygame.K_BACKSPACE, "unicode": "", "mod": 0}))
    erased = game.license_input == ""

    # 提交真码 → 授权生效；同一张码再提交 → 被拒
    game.license_input = lic.clean(TOOL_CODE)
    game._submit_license()
    activated = lic.state.licensed and lic.state.days == 30 and "成功" in game.license_msg
    game.license_input = lic.clean(TOOL_CODE)
    game._submit_license()
    refused = "用过" in game.license_msg

    ok = blocked and allowed and typed == "A" and erased and activated and refused
    print(" 10 界面接线 · 到期点开始=%s · 试用中点开始=%s · 打键进框=%s · 退格=%s "
          "· 提交=%s · 同码再提交=%s · %s" % (
              "拦到激活页" if blocked else "竟然放行",
              "进关卡" if allowed else "没反应",
              "是" if typed == "A" else "否（%r）" % typed,
              "是" if erased else "否",
              "成功" if activated else "失败",
              "被拒" if refused else "没拦住",
              _ok(ok)))


# ---------------------------------------------------------------- 入口

def run() -> int:
    global _ok_count, _fail_count
    _ok_count = 0
    _fail_count = 0

    print("")
    print("=== 授权 · 机器绑定 · 激活码（塔防）===")
    print("全程走临时目录，玩家真实授权文件不会被碰")
    print("")

    tmpdir = tempfile.mkdtemp(prefix="td_lic_")
    saved_state = lic.state
    saved_machine = lic._machine_cache
    lic._machine_cache = b""
    try:
        _temp_state(tmpdir).load()
        _t_machine()
        _t_tool_code()
        _t_reject()
        _t_apply()
        _t_expire()
        _t_clock()
        _t_no_secret()
        _t_delete_save(tmpdir)
        _t_aux_legacy(tmpdir)
        _t_menu_flow(tmpdir)
    finally:
        lic.state = saved_state
        lic._machine_cache = saved_machine
        shutil.rmtree(tmpdir, ignore_errors=True)

    print("")
    if _fail_count == 0:
        print("自检 %d/%d 项通过。" % (_ok_count, _ok_count))
    else:
        print("自检 %d/%d 项通过，%d 项失败。" % (_ok_count, _ok_count + _fail_count, _fail_count))
    print("")
    return 0 if _fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
