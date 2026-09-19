"""
授权模块 —— 机器绑定的激活码（与《代码幸存者》共用同一套发码工具）

设计目标
    一套工具管所有游戏：每款游戏一个编号 + 一把独立密钥。激活码同时绑定
    「哪款游戏」和「哪台电脑」，所以
      · 别的游戏用不了   —— 游戏编号不匹配
      · 别的电脑用不了   —— 机器码不匹配
      · 学生自己编不出来 —— 有 HMAC 校验码兜着
      · 同一张码只能用一次 —— 本机用过的码记在指纹表里

激活码的构成（12 字节，Base32 编码后 20 个字符）
    game_id   1 字节   游戏编号（tools/keygen 那边分配：塔防 = 2）
    machine   5 字节   学生报来的机器码原文
    days      2 字节   授权天数，大端序；0 表示永久
    mac       4 字节   HMAC-SHA256(secret, 前 8 字节) 的前 4 字节

机器指纹（关键：必须与 Godot 端算出来一模一样）
    Godot 的 OS.get_unique_id() 在 Windows 上取的不是 MachineGuid，而是
        HKLM\\SYSTEM\\CurrentControlSet\\Control\\IDConfigDB\\Hardware Profiles\\0001
    里的 HwProfileGuid；处理器名取 HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0
    的 ProcessorNameString。这里照抄同一套来源、同一个公式 SHA256(uid + "|" + cpu)[:5]
    —— 已实测两端在本机都算出 GZTX-WIP2，所以同一个申请码两款游戏通用，
    学生报一次码就能同时给两款游戏发授权。

存储（两份，互为备份）
    主记录   %APPDATA%/TowerDefense/license.json
    第二埋点 %LOCALAPPDATA%/TowerDefense/.state
    放在两个不同的根目录下：学生删掉一份，另一份还在。
    任何一步读写失败都只是少一道防线，绝不抛异常、绝不影响游戏运行。
"""
import hashlib
import hmac
import json
import os
import sys
import time
from datetime import date

# ---------------------------------------------------------------- 常量

GAME_ID = 2
GAME_NAME = "守护稚码王国"

CODE_BYTES = 12          # game_id 1 + machine 5 + days 2 + mac 4
MACHINE_BYTES = 5
CODE_CHARS = 20
MACHINE_CHARS = 8
SECRET_BYTES = 32
FINGERPRINT_BYTES = 4

# Base32 字母表：故意不含 0、1、8、9 —— 手抄时最容易被认错的那四个
B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
HEX_CHARS = "0123456789abcdef"

TRIAL_DAYS = 7           # 未激活时的试用天数
MAX_VIOLATIONS = 3       # 回拨几次算恶意
CLOCK_TOLERANCE = 3600   # 回拨容差（秒）：NTP 校时可能往回走几分钟
MAX_SANE_DAYS = 3650     # 跨度超过十年 → 判定为时钟坏了，不拿它锁人
DAY_PERMANENT = 0

# 授权文件所在的目录名。**它是机器全局的，与游戏项目无关** ——
# 每款游戏必须用自己的名字，否则两款游戏的「起算日」会互相污染：
# 玩过 A 之后再装 B，B 的试用会直接继承 A 的起算日、一开局就过期。
DIR_NAME = "TowerDefense"

_EPOCH_ORDINAL = date(1970, 1, 1).toordinal()

_secret_cache = None


# ---------------------------------------------------------------- 字符串处理

def clean(text: str) -> str:
    """统一用户输入：去分隔符、转大写、纠正手抄易混字符。

    Base32 里没有 0 和 1，所以出现它们一定是要写 O 和 I。
    """
    s = (text or "").strip().upper()
    for j in ("-", " ", "_", "\t", "\r", "\n"):
        s = s.replace(j, "")
    return s.replace("0", "O").replace("1", "I")


def group(text: str, n: int = 4) -> str:
    """每 n 个字符插一个连字符：方便念、方便抄。"""
    return "-".join(text[i:i + n] for i in range(0, len(text), n))


def format_input(text: str) -> str:
    """输入框里的内容按 4 位分组显示。

    先把连字符、空格之类的噪声清掉再分组 —— 不然用户粘贴进来一串带连字符的
    码，会被分组成错位的乱码（界面上看着像抄错了）。
    """
    return group("".join(c for c in clean(text) if c in B32))


# ---------------------------------------------------------------- Base32

def b32_encode(data: bytes) -> str:
    out = []
    buf = 0
    bits = 0
    for b in data:
        buf = (buf << 8) | b
        bits += 8
        while bits >= 5:
            bits -= 5
            out.append(B32[(buf >> bits) & 31])
            buf &= (1 << bits) - 1
    if bits > 0:
        out.append(B32[(buf << (5 - bits)) & 31])
    return "".join(out)


def b32_decode(text: str) -> bytes:
    """解码失败一律返回 b""（长度不对、有非法字符、填充位不是 0）。

    最后那条「填充位必须为 0」是必须的：Base32 末尾几位是凑长度的填充，
    不检查的话，改动末尾字符能解出同样的字节 —— 篡改检测会漏掉一个字符。
    """
    s = clean(text)
    out = bytearray()
    buf = 0
    bits = 0
    for ch in s:
        v = B32.find(ch)
        if v < 0:
            return b""
        buf = (buf << 5) | v
        bits += 5
        while bits >= 8:
            bits -= 8
            out.append((buf >> bits) & 0xFF)
            buf &= (1 << bits) - 1
    if bits > 0 and buf != 0:
        return b""
    return bytes(out)


# ---------------------------------------------------------------- 密钥

def secret() -> bytes:
    """读 game/license_key.py 里的 SECRET_HEX。

    用 try/except 而不是直接 import —— 文件缺失时（公开仓库里就是这个状态）
    游戏还能正常启动，只是激活功能不可用。
    """
    global _secret_cache
    if _secret_cache is not None:
        return _secret_cache
    _secret_cache = b""
    try:
        from game.license_key import SECRET_HEX  # noqa: WPS433
    except Exception:
        return _secret_cache
    try:
        raw = bytes.fromhex(str(SECRET_HEX).strip())
    except ValueError:
        return _secret_cache
    if len(raw) == SECRET_BYTES:
        _secret_cache = raw
    return _secret_cache


def has_secret() -> bool:
    return len(secret()) == SECRET_BYTES


# ---------------------------------------------------------------- 机器码

def _reg_read(path: str, name: str):
    """读一个注册表值；非 Windows 或读不到都返回 None。"""
    if not sys.platform.startswith("win"):
        return None
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
        try:
            value = winreg.QueryValueEx(key, name)[0]
        finally:
            winreg.CloseKey(key)
        return str(value)
    except Exception:
        return None


def _unique_raw() -> str:
    """机器唯一号的原始串 —— 必须与 Godot 的 OS.get_unique_id() 完全一致。

    Godot 在 Windows 上取的是「硬件配置文件 GUID」（HwProfileGuid），
    不是 Cryptography 里的 MachineGuid（两者在本机实测就是不同的值）。
    0001 找不到时，退而求其次扫一遍 Hardware Profiles 下的子键。
    """
    base = r"SYSTEM\CurrentControlSet\Control\IDConfigDB\Hardware Profiles"
    for sub in ("0001", "0000", "Current"):
        got = _reg_read(base + "\\" + sub, "HwProfileGuid")
        if got:
            return got
    # 扫一遍子键，挑第一个有 HwProfileGuid 的
    if sys.platform.startswith("win"):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base)
            try:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(key, i)
                    except OSError:
                        break
                    i += 1
                    got = _reg_read(base + "\\" + sub, "HwProfileGuid")
                    if got:
                        return got
            finally:
                winreg.CloseKey(key)
        except Exception:
            pass
    # 最后兜底：MachineGuid，再不行用机器名
    for path, name in (
        (r"SOFTWARE\Microsoft\Cryptography", "MachineGuid"),
        (r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "ProductId"),
    ):
        got = _reg_read(path, name)
        if got:
            return got
    return os.environ.get("COMPUTERNAME", "") + os.environ.get("USERNAME", "")


def _cpu_name() -> str:
    got = _reg_read(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
                    "ProcessorNameString")
    if got:
        return got.strip()
    return ""


_machine_cache = b""


def machine_bytes() -> bytes:
    """机器指纹 → 5 字节。学生看到的 8 个字符就是它。"""
    global _machine_cache
    if _machine_cache:
        return _machine_cache
    raw = (_unique_raw() + "|" + _cpu_name()).encode("utf-8")
    _machine_cache = hashlib.sha256(raw).digest()[:MACHINE_BYTES]
    return _machine_cache


def machine_code() -> str:
    """学生要发给作者的「申请码」，形如 A3K7-M2XQ。只跟硬件有关，不含隐私。"""
    return group(b32_encode(machine_bytes()))


def code_fingerprint(code: str) -> str:
    """激活码指纹：存「这张码在本机用过了」，只留 4 字节。

    哈希的是**归一化之后**的码 —— 带不带连字符、全小写、把 O 抄成 0
    都算同一张，否则学生换个写法就能再用一次。
    """
    digest = hashlib.sha256(clean(code).encode("utf-8")).digest()
    out = []
    for b in digest[:FINGERPRINT_BYTES]:
        out.append(HEX_CHARS[(b >> 4) & 0xF])
        out.append(HEX_CHARS[b & 0xF])
    return "".join(out)


# ---------------------------------------------------------------- 验码

def _payload(game_id: int, machine5: bytes, days: int) -> bytes:
    return bytes([game_id]) + machine5 + days.to_bytes(2, "big")


def verify(code: str) -> dict:
    """校验激活码。返回 {ok, reason, days, permanent}。

    reason 是给人看的一句话，UI 直接显示 —— 学生抄错、拿错码、用别人的码、
    重复用同一张码，四种情况要能分清楚，否则电话里没法判断问题出在哪。
    """
    res = {"ok": False, "reason": "", "days": 0, "permanent": False}
    sec = secret()
    if len(sec) != SECRET_BYTES:
        res["reason"] = "本机没有配置激活密钥，请联系作者"
        return res

    raw = b32_decode(code)
    if len(raw) != CODE_BYTES:
        res["reason"] = "激活码应该是 20 个字符，请看看是不是抄漏了"
        return res

    gid = raw[0]
    machine5 = raw[1:1 + MACHINE_BYTES]
    days = int.from_bytes(raw[6:8], "big")
    mac = raw[8:CODE_BYTES]

    # 四道关卡，按代价从低到高排
    if gid != GAME_ID:
        res["reason"] = "这个激活码属于另一款游戏（编号 %d），用不到《%s》上" % (gid, GAME_NAME)
        return res

    expect = hmac.new(sec, _payload(gid, machine5, days), hashlib.sha256).digest()
    if expect[:4] != mac:
        res["reason"] = "激活码校验不通过，多半是有字符抄错了"
        return res

    if machine5 != machine_bytes():
        res["reason"] = "这个激活码是发给另一台电脑的，本机用不了"
        return res

    if state.has_used_code(code_fingerprint(code)):
        res["reason"] = "这张激活码已经在本机用过了，请找作者要一张新的"
        return res

    res["ok"] = True
    res["days"] = days
    res["permanent"] = days == DAY_PERMANENT
    return res


# ---------------------------------------------------------------- 授权状态

def today_index() -> int:
    """本地日历日的序号（1970-01-01 起算）。

    与 Godot 端同一口径，方便两个游戏对着存档看问题时数字能对上。
    """
    return date.today().toordinal() - _EPOCH_ORDINAL


def now_ts() -> int:
    return int(time.time())


class LicenseState:
    """试用与授权状态：起算日、有效期、已用码指纹、时钟体检。"""

    def __init__(self, main_path=None, aux_path=None, use_aux=True):
        self.start_day = 0
        self.days = TRIAL_DAYS
        self.licensed = False
        self.violations = 0
        self.last_seen_day = 0
        self.last_seen_ts = 0
        self.used_codes = []
        self._loaded = False

        # 测试用：写到别的文件去，别把玩家的真授权冲掉
        self.main_path_override = main_path
        self.use_aux = use_aux
        self.aux_path_override = aux_path

    # ------------------------------------------------ 路径

    def main_path(self) -> str:
        if self.main_path_override:
            return self.main_path_override
        base = os.environ.get("APPDATA") or os.environ.get("USERPROFILE") or ""
        if not base:
            return ""
        return os.path.join(base, DIR_NAME, "license.json")

    def aux_path(self) -> str:
        if self.aux_path_override:
            return self.aux_path_override
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("USERPROFILE") or ""
        if not base:
            return ""
        return os.path.join(base, DIR_NAME, ".state")

    # ------------------------------------------------ 读写

    def load(self) -> None:
        """读授权记录 + 第二埋点，然后做一次体检。失败一律按"没有记录"处理。"""
        self.start_day = 0
        self.days = TRIAL_DAYS
        self.licensed = False
        self.violations = 0
        self.last_seen_day = 0
        self.last_seen_ts = 0
        self.used_codes = []
        try:
            path = self.main_path()
            if path and os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.start_day = int(data.get("start_day", 0) or 0)
                    self.days = int(data.get("days", TRIAL_DAYS))
                    self.licensed = bool(data.get("licensed", False))
                    self.violations = int(data.get("violations", 0) or 0)
                    self.last_seen_day = int(data.get("last_seen_day", 0) or 0)
                    self.last_seen_ts = int(data.get("last_seen_ts", 0) or 0)
                    for c in (data.get("used_codes") or []):
                        s = str(c)
                        if s:
                            self.used_codes.append(s)
        except Exception:
            pass
        self._loaded = True
        self._bootstrap()

    def save(self) -> None:
        try:
            path = self.main_path()
            if not path:
                return
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = {
                "start_day": self.start_day,
                "days": self.days,
                "licensed": self.licensed,
                "violations": self.violations,
                "last_seen_day": self.last_seen_day,
                "last_seen_ts": self.last_seen_ts,
                "used_codes": list(self.used_codes),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    def _write_aux(self) -> None:
        """第二埋点：两行 —— 第 1 行起算日，第 2 行用过的激活码指纹。

        第 2 行是后加的，读的时候必须容忍老文件只有一行。
        """
        if not self.use_aux:
            return
        try:
            path = self.aux_path()
            if not path:
                return
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("%d\n" % self.start_day)
                f.write(",".join(self.used_codes) + "\n")
        except Exception:
            pass

    def _read_aux(self):
        """返回 (起算日, 指纹列表)。读不到就给 (0, [])。"""
        if not self.use_aux:
            return 0, []
        try:
            path = self.aux_path()
            if not path or not os.path.isfile(path):
                return 0, []
            with open(path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            start = 0
            codes = []
            if len(lines) >= 1:
                try:
                    start = int(lines[0].strip())
                except ValueError:
                    start = 0
            if len(lines) >= 2:
                for c in lines[1].split(","):
                    s = c.strip()
                    if s:
                        codes.append(s)
            return start, codes
        except Exception:
            return 0, []

    # ------------------------------------------------ 体检

    def _bootstrap(self) -> None:
        aux_start, aux_codes = self._read_aux()
        if aux_start > 0 and (self.start_day == 0 or aux_start < self.start_day):
            self.start_day = aux_start       # 主记录被删过？以更早的那份为准
        for c in aux_codes:
            if c not in self.used_codes:
                self.used_codes.append(c)    # 用过的码同样要捞回来

        today = today_index()
        if self.start_day == 0:
            self.start_day = today           # 第一次运行，试用从今天开始
        # 时钟明显不对劲时不拿它锁人（起算日在未来，或跨度超过十年）：
        # 主板电池没电、系统时间停在几年前，都会撞上这条，直接挪回今天。
        if self.start_day > today or today - self.start_day > MAX_SANE_DAYS:
            self.start_day = today
            self.violations = 0
        self._clock_check()
        self.last_seen_day = max(self.last_seen_day, today)
        self.save()
        self._write_aux()

    def _clock_check(self) -> None:
        """回拨检测：这次运行的时间比上次还早（超过容差）→ 记一笔违规。"""
        now = now_ts()
        if self.last_seen_ts > 0 and now < self.last_seen_ts - CLOCK_TOLERANCE:
            self.violations += 1
        self.last_seen_ts = max(self.last_seen_ts, now)

    def _ensure(self) -> None:
        if not self._loaded:
            self.load()

    # ------------------------------------------------ 查询

    def effective_today(self) -> int:
        """把「上次运行的日期」也算进去：拨回时钟不会让已用天数缩水。"""
        self._ensure()
        return max(today_index(), self.last_seen_day)

    def days_used(self) -> int:
        if self.start_day == 0:
            return 0
        return max(0, self.effective_today() - self.start_day)

    def is_permanent(self) -> bool:
        return self.licensed and self.days == DAY_PERMANENT

    def days_left(self) -> int:
        if self.is_permanent():
            return 9999
        return max(0, self.days - self.days_used())

    def is_expired(self) -> bool:
        if self.is_permanent():
            return False
        return self.days_used() >= self.days

    def status_text(self) -> str:
        """菜单上显示的那一行。"""
        self._ensure()
        if self.is_permanent():
            return "已授权　永久有效"
        left = self.days_left()
        if left <= 0:
            return "授权已到期" if self.licensed else "试用已结束"
        kind = "授权" if self.licensed else "试用"
        if left <= 2:
            return "%s剩余 %d 天　快到期了" % (kind, left)
        return "%s剩余 %d 天" % (kind, left)

    # ------------------------------------------------ 激活

    def has_used_code(self, fingerprint: str) -> bool:
        if not fingerprint:
            return False
        self._ensure()
        return fingerprint in self.used_codes

    def activate(self, days: int, code: str = "") -> bool:
        """激活 / 续期：起算日重置为今天，有效期换成 days（0 = 永久）。

        故意不做加法 —— 同一个码输两次，结果和输一次一样。但「重置」同时也
        意味着"输一次就把天数重新装满"，所以必须把指纹记下来、拒绝重复使用，
        否则学生拿自己那一张码就能无限续期。想续期就得再要一张新码。
        """
        self._ensure()
        fingerprint = code_fingerprint(code) if code else ""
        if fingerprint and fingerprint in self.used_codes:
            return False
        if fingerprint:
            self.used_codes.append(fingerprint)
        self.start_day = today_index()
        self.days = days
        self.licensed = True
        self.violations = 0
        self.last_seen_day = self.start_day
        self.last_seen_ts = now_ts()
        self.save()
        self._write_aux()
        return True


# 全局单例：游戏里直接用 license.state
state = LicenseState()


def debug_info() -> dict:
    """给自己看的诊断信息（--lictest 用）。"""
    return {
        "game_id": GAME_ID,
        "game_name": GAME_NAME,
        "machine_code": machine_code(),
        "machine_bytes": machine_bytes().hex(),
        "has_secret": has_secret(),
        "secret_len": len(secret()),
        "status": state.status_text(),
    }


if __name__ == "__main__":
    for k, v in debug_info().items():
        print("%-14s %s" % (k, v))
