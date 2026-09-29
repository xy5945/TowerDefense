# -*- coding: utf-8 -*-
"""打码出题与校验（塔防版）。

算法与《代码幸存者》的 core/code_challenge.gd 是同一套，题库也是同一份
（code_db.py 由那边 tools/gen_code_challenge_db.py --py 产出）。
改校验规则时两边要一起改，否则同一段代码在这边过、在那边不过。

两条必须守住的规矩：

1. 校验宽容的是「空格的数量」，不是「代码的内容」。
   全角标点、多打少打空格、行尾空白都放过 —— 那是输入法问题，不是代码问题。
   但行首缩进必须真的打出来（见 match_state 里那处 break），
   否则孩子可以直接不打缩进，缩进这块就白练了。

2. 塔防没有「升级项」这个概念，所以 Lv4 以上不按主题出题，
   而是在全部主题里随机抽一个再随机抽变体 —— 跟那边「救我一命」的取题方式一致。
"""
import random

from game.code_db import FRAG, TIPS, KW

# 上次抽到的关键字下标。连续两次抽到同一个，孩子会觉得「又来了」。
_last_kw = -1

# 测试要可复现，就得能钉住种子
_seeded = False


def set_seed(s: int) -> None:
    global _seeded
    random.seed(s)
    _seeded = True


# ---------------------------------------------------------------- 字符归一化

def normalize_char(c: str) -> str:
    """全角 -> 半角。FF01-FF5E 整体偏移 0xFEE0 就是对应的半角字符。"""
    if len(c) != 1:
        return c
    v = ord(c)
    if v == 0x3000:          # 全角空格不在这个区间里，单独处理
        return " "
    if 0xFF01 <= v <= 0xFF5E:
        return chr(v - 0xFEE0)
    if v == 9:               # Tab 当空格看，孩子按 Tab 和按空格都算数
        return " "
    return c


def _is_space(c: str) -> bool:
    return c == " "


# ---------------------------------------------------------------- 出题

def _build_keyword(lv: int, variant: int) -> dict:
    """前 3 级：从关键字池随机抽一条。variant >= 0 时钉住下标（测试用）。"""
    global _last_kw
    n = len(KW)
    if n == 0:
        return {"theme": "keyword", "level": lv, "variant": 0,
                "lines": [""], "text": "", "tip": ""}
    ki = variant if variant >= 0 else random.randrange(n)
    if variant < 0 and n > 1 and ki == _last_kw:
        ki = (ki + 1) % n
    ki = max(0, min(n - 1, ki))
    _last_kw = ki
    code, tip = KW[ki]
    return {"theme": "keyword", "level": lv, "variant": ki,
            "lines": [code], "text": code, "tip": tip}


def build(level: int, variant: int = -1) -> dict:
    """出一道题。variant 传 -1（默认）表示随机抽变体。

    返回的 text 是带换行的整段代码，校验时拿它当目标串。
    """
    lv = max(1, min(8, int(level)))
    if lv <= 3:
        return _build_keyword(lv, variant)

    themes = list(FRAG.keys())
    random.shuffle(themes)
    pool = []
    th = "general"
    for t in themes:
        cand = FRAG.get(t, {}).get(lv) or []
        if cand:
            th, pool = t, cand
            break
    if not pool:
        pool = FRAG.get("general", {}).get(lv) or []
        th = "general"
    if not pool:
        return _build_keyword(lv, variant)

    vi = variant if variant >= 0 else random.randrange(len(pool))
    vi = max(0, min(len(pool) - 1, vi))
    lines = list(pool[vi])
    tips = TIPS.get(th, {}).get(lv) or []
    tip = tips[vi] if vi < len(tips) else ""
    return {"theme": th, "level": lv, "variant": vi,
            "lines": lines, "text": "\n".join(lines), "tip": tip}


# ---------------------------------------------------------------- 校验

def match_state(target: str, typed: str) -> dict:
    """逐字符比对，返回渲染需要的一切。

    tpos  目标已匹配到第几个字符
    ipos  输入已匹配到第几个
    err   是否打错
    done  是否全部打对
    """
    i = 0
    t = 0
    ni = len(typed)
    nt = len(target)
    err = False

    while i < ni and t < nt:
        ic = normalize_char(typed[i])
        tc = normalize_char(target[t])
        if ic == tc:
            i += 1
            t += 1
            continue
        if _is_space(ic) and _is_space(tc):
            i += 1
            t += 1
            continue
        # 行首缩进不许跳过：放过去的话孩子永远不用按空格
        if _is_space(tc) and (t == 0 or target[t - 1] == "\n"):
            err = True
            break
        if _is_space(ic):
            i += 1
            continue
        if _is_space(tc):
            t += 1
            continue
        err = True
        break

    # 两头多余的空白不计较
    while i < ni and _is_space(normalize_char(typed[i])):
        i += 1
    while t < nt and _is_space(normalize_char(target[t])):
        t += 1

    # 目标打完了但输入还有剩：那也是错，而且是最难受的一种 ——
    # 不算完成、也不报错，孩子只会看到进度条卡住不知道自己多打了。
    if t >= nt and i < ni:
        err = True

    return {"tpos": t, "ipos": i, "err": err, "done": (t >= nt and i >= ni)}


def pos_to_line_col(target: str, pos: int) -> tuple:
    """出错位置换算成「第几行第几列」（从 1 开始），提示给孩子看。"""
    line = 1
    col = 1
    i = 0
    while i < pos and i < len(target):
        if target[i] == "\n":
            line += 1
            col = 1
        else:
            col += 1
        i += 1
    return line, col


# ---------------------------------------------------------------- 输入辅助

def leading_spaces(s: str) -> int:
    n = 0
    while n < len(s) and s[n] == " ":
        n += 1
    return n


def indent_after_newline(typed: str) -> str:
    """回车后要自动补的缩进：上一行以 { 结尾就多缩进一层。

    不打缩进也能过的话这块就练不到，所以帮着补；
    但补多补少不追究 —— 校验那边本来就宽容空格数量。
    """
    lines = typed.split("\n")
    prev = lines[-2] if len(lines) >= 2 else ""
    ind = leading_spaces(prev)
    if prev.strip().endswith("{"):
        ind += 4
    return " " * ind
