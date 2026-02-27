import tkinter as tk
from tkinter import ttk, messagebox
import csv
import time
import os
import json
import threading
import re   # ★ 禁止文字除去に必要
import html  # ★ HTMLエンティティのデコードなどに使用
from typing import Optional, Dict
from settings_page import SettingsPage

import sys
import requests
import struct
import platform
from pathlib import Path

def fetch_game_title_prefer_jp(appid: int, timeout: int = 10):
    base = "https://store.steampowered.com/api/appdetails?appids={appid}&l={lang}"
    for lang in ("japanese", "english"):
        url = base.format(appid=appid, lang=lang)
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            data = r.json()
        except Exception:
            continue

        block = data.get(str(appid), {})
        if not block.get("success"):
            continue

        app = block.get("data") or {}
        name = app.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None



# -----------------------------
# タイトル取得（日本語優先 + キャッシュ）
# -----------------------------
_TITLE_CACHE_LOCK = threading.Lock()
_TITLE_CACHE = None  # type: Optional[dict]

def _load_title_cache() -> dict:
    try:
        with open(TITLE_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _save_title_cache(cache: dict) -> None:
    try:
        with open(TITLE_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        # キャッシュは補助機能なので保存失敗しても落とさない
        pass

def get_game_title_prefer_jp_cached(appid: int, timeout: int = 10) -> Optional[str]:
    """Store API から日本語→英語の順でタイトルを取得し、結果をキャッシュする。"""
    global _TITLE_CACHE
    key = str(appid)

    with _TITLE_CACHE_LOCK:
        if _TITLE_CACHE is None:
            _TITLE_CACHE = _load_title_cache()
        cached = _TITLE_CACHE.get(key)
        if isinstance(cached, str) and cached.strip():
            return cached.strip()

    title = fetch_game_title_prefer_jp(appid, timeout=timeout)
    if isinstance(title, str) and title.strip():
        with _TITLE_CACHE_LOCK:
            if _TITLE_CACHE is None:
                _TITLE_CACHE = {}
            _TITLE_CACHE[key] = title.strip()
            _save_title_cache(_TITLE_CACHE)
        return title.strip()

    return None

def resource_path(relative_path):
    """PyInstaller で exe 化した後でもリソースファイルにアクセスできるようにする"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


# -----------------------------
# 設定
# -----------------------------
CONFIG_PATH = "config.json"

APP_TITLE = "Steam 実績エクスポーター"
DEFAULT_OUTPUT = os.path.join("C:\\", "steam_export", "steam_achievements_jp.csv")
USE_JP_TITLE = True
# 日本語タイトルのキャッシュ（Store API 連打を避ける）
TITLE_CACHE_PATH = "title_cache.json"

# カラー
BG_ROOT = "#232120"
BG_PANEL = "#32302F"
BG_ENTRY = "#32302F"
FG_MAIN = "#e5e7eb"
SEARCH_BG = "#3d3b3a"
BORDER_SOFT = "#4a4847"  # 枠線（ダークになじむ）

# 進捗ゲージ用カラー（黒ベースのグレー系）
GAUGE_TRACK_COLOR = "#3a3a3a"   # ゲージ背景（トラック / 灰色）
GAUGE_BAR_COLOR   = "#ffffff"   # ゲージ本体（バー / 白）


# =========================================================
# ★★ ファイル名を完全安全化する関数
# =========================================================
def safe_filename(name: str) -> str:
    # Windows で使えない文字を全部 "_" に
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    # 末尾のピリオドと空白を削除
    name = name.rstrip(". ")
    # 非表示 / 制御文字を削除
    name = "".join(ch for ch in name if ch.isprintable())
    return name if name else "game"


# -----------------------------
# API
# -----------------------------
def get_owned_games(api_key, steam_id):
    if not api_key or not steam_id:
        raise ValueError("API Key と SteamID64 を設定タブで入力してください。")

    url = (
        "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
        f"?key={api_key}&steamid={steam_id}"
        "&include_appinfo=1&include_played_free_games=1"
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", {}).get("games", [])


# -----------------------------
# 実績：追加情報（hidden説明の補完）
# -----------------------------

def get_game_achievements_master(api_key: str, appid: int, lang: str = "japanese", timeout: int = 15) -> dict:
    """hidden でも description が入ることがある master を取得（apiname -> {displayName, description}）。
    非公式寄りだが広く使われている IPlayerService/GetGameAchievements を試す。
    """
    if not api_key:
        return {}

    url = (
        "https://api.steampowered.com/IPlayerService/GetGameAchievements/v1/"
        f"?key={api_key}&appid={appid}&language={lang}"
    )
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json() or {}
    except Exception:
        return {}

    # 形式が複数あり得るので安全に辿る
    container = data.get("response") or data
    achievements = container.get("achievements", [])
    out = {}
    if isinstance(achievements, list):
        for a in achievements:
            api = a.get("name")
            if not isinstance(api, str):
                continue
            out[api] = {
                "displayName": a.get("displayName") or "",
                "description": a.get("description") or "",
            }
    return out


def get_global_achievement_descriptions_from_community(appid: int, lang: str = "japanese", timeout: int = 15) -> dict:
    """Steam Community の「Global Achievements」ページを軽くパースして、
    表示名(displayName) -> 説明(description) を返す（apiname は取れないので displayName キー）。
    IPlayerService でも取れない場合の最後の保険。
    """
    url = f"https://steamcommunity.com/stats/{appid}/achievements?l={lang}"
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        html_text = resp.text
    except Exception:
        return {}

    # achieveRow の中に h3(タイトル) と h5(説明) がある想定で抽出（構造変化に備えてゆるく）
    # 例: <div class="achieveTxt"><h3 class="ellipsis">...</h3><h5>...</h5>
    pairs = re.findall(r"<h3[^>]*>(.*?)</h3>.*?<h5[^>]*>(.*?)</h5>", html_text, flags=re.S | re.I)
    out = {}
    for raw_title, raw_desc in pairs:
        title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
        desc = html.unescape(re.sub(r"<[^>]+>", "", raw_desc)).strip()
        if title:
            out[title] = desc
    return out

# -----------------------------
# hidden 実績説明の最終手段（ローカル Steam キャッシュ）
# -----------------------------
# Steam クライアントは各ゲームの「実績/統計のスキーマ」を
# <SteamRoot>/appcache/stats/UserGameStatsSchema_<AppID>.bin にキャッシュします。
# ここには hidden 実績の説明が入っていることがあり、Web API で空のときの最後の保険になります。
_LOCAL_SCHEMA_CACHE_LOCK = threading.Lock()
_LOCAL_SCHEMA_CACHE: Dict[str, dict] = {}  # key = f"{appid}:{lang}" -> {apiname: {displayName, description}}

def _read_config_steam_path() -> Optional[str]:
    """config.json に steam_path / steam_root があれば利用（UIはまだ無いので手編集用）。"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f) or {}
        for k in ("steam_path", "steam_root", "steam_dir"):
            v = cfg.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    except Exception:
        return None
    return None

def _detect_steam_root() -> Optional[str]:
    # 1) env
    for k in ("STEAM_PATH", "STEAM_ROOT", "STEAMDIR", "STEAM_HOME"):
        v = os.environ.get(k)
        if isinstance(v, str) and v.strip() and os.path.isdir(v.strip()):
            return v.strip()

    # 2) config.json（任意）
    cfg_path = _read_config_steam_path()
    if cfg_path and os.path.isdir(cfg_path):
        return cfg_path

    sysname = platform.system().lower()
    candidates = []

    if "windows" in sysname:
        # レジストリ
        try:
            import winreg  # type: ignore
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive, r"Software\Valve\Steam") as key:
                        val, _ = winreg.QueryValueEx(key, "SteamPath")
                        if isinstance(val, str) and val:
                            candidates.append(val)
                except Exception:
                    pass
        except Exception:
            pass

        candidates += [
            r"C:\\Program Files (x86)\\Steam",
            r"C:\\Program Files\\Steam",
        ]
        localapp = os.environ.get("LOCALAPPDATA")
        if localapp:
            candidates.append(os.path.join(localapp, "Steam"))

    elif "darwin" in sysname or "mac" in sysname:
        candidates += [os.path.expanduser("~/Library/Application Support/Steam")]
    else:
        candidates += [
            os.path.expanduser("~/.steam/steam"),
            os.path.expanduser("~/.steam/root"),
            os.path.expanduser("~/.local/share/Steam"),
        ]

    for c in candidates:
        if isinstance(c, str) and c and os.path.isdir(c):
            return c
    return None

def _get_usergamestats_schema_path(appid: int) -> Optional[str]:
    root = _detect_steam_root()
    if not root:
        return None

    stats_dir = os.path.join(root, "appcache", "stats")
    if not os.path.isdir(stats_dir):
        return None

    # まずは一般的なファイル名（SteamID無し）
    exact = os.path.join(stats_dir, f"UserGameStatsSchema_{appid}.bin")
    if os.path.isfile(exact):
        return exact

    # Steam クライアント/環境によっては SteamID 付きで生成されることがあるので拾う
    try:
        import glob
        pats = [
            os.path.join(stats_dir, f"UserGameStatsSchema_*_{appid}.bin"),
            os.path.join(stats_dir, f"UserGameStatsSchema*{appid}*.bin"),
        ]
        cand = []
        for p in pats:
            cand.extend(glob.glob(p))
        cand = [p for p in cand if os.path.isfile(p)]
        if not cand:
            return None
        # 一番新しいものを採用
        cand.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return cand[0]
    except Exception:
        return None

def _read_cstring(buf: bytes, pos: int):
    end = buf.find(b"\x00", pos)
    if end < 0:
        end = len(buf)
    s = buf[pos:end].decode("utf-8", errors="replace")
    pos = end + 1 if end < len(buf) else end
    return s, pos

def _read_wstring(buf: bytes, pos: int):
    end = buf.find(b"\x00\x00", pos)
    if end < 0:
        end = len(buf) - (len(buf) % 2)
    s = buf[pos:end].decode("utf-16-le", errors="replace")
    pos = end + 2 if end + 2 <= len(buf) else end
    return s, pos

class _BinaryVDFReader:
    """Valve の Binary VDF(KeyValues) の最小実装。
    よく出る型:
      0x00 map, 0x01 string, 0x02 int32, 0x03 float32, 0x07 uint64, 0x08 end
    """

    def __init__(self, buf: bytes):
        self.buf = buf
        self.pos = 0
        self.n = len(buf)

    def _need(self, size: int):
        if self.pos + size > self.n:
            raise EOFError("binary vdf: unexpected EOF")

    def read_byte(self) -> int:
        self._need(1)
        b = self.buf[self.pos]
        self.pos += 1
        return b

    def peek_byte(self) -> int:
        self._need(1)
        return self.buf[self.pos]

    def read_bytes(self, size: int) -> bytes:
        self._need(size)
        b = self.buf[self.pos:self.pos+size]
        self.pos += size
        return b

    def read_cstring(self) -> str:
        s, self.pos = _read_cstring(self.buf, self.pos)
        return s

    def read_wstring(self) -> str:
        s, self.pos = _read_wstring(self.buf, self.pos)
        return s

    def read_u32(self) -> int:
        self._need(4)
        v = struct.unpack_from("<I", self.buf, self.pos)[0]
        self.pos += 4
        return int(v)

    def read_u64(self) -> int:
        self._need(8)
        v = struct.unpack_from("<Q", self.buf, self.pos)[0]
        self.pos += 8
        return int(v)

    def read_f32(self) -> float:
        self._need(4)
        v = struct.unpack_from("<f", self.buf, self.pos)[0]
        self.pos += 4
        return float(v)

    def read_map(self, depth: int = 0) -> dict:
        if depth > 64:
            raise ValueError("binary vdf: too deep")
        out: dict = {}
        while self.pos < self.n:
            t = self.read_byte()
            if t == 0x08:  # end of map
                break

            key = self.read_cstring()

            try:
                if t == 0x00:
                    val = self.read_map(depth + 1)
                elif t == 0x01:
                    val = self.read_cstring()
                elif t == 0x02:
                    val = self.read_u32()
                elif t == 0x03:
                    val = self.read_f32()
                elif t == 0x04:  # ptr (扱いはu32で十分)
                    val = self.read_u32()
                elif t == 0x05:  # wide string
                    val = self.read_wstring()
                elif t == 0x06:  # color (RGBA)
                    val = int.from_bytes(self.read_bytes(4), "little", signed=False)
                elif t == 0x07:
                    val = self.read_u64()
                else:
                    # 未知の型は壊れやすいので、ここで打ち切る（部分データは返す）
                    break
            except Exception:
                break

            out[key] = val
        return out

def _parse_binary_vdf(buf: bytes) -> dict:
    r = _BinaryVDFReader(buf)
    try:
        # 先頭が map のときは「name -> map」が続くパターンが多い
        if r.peek_byte() == 0x00:
            r.read_byte()
            root_name = r.read_cstring()
            root_val = r.read_map()
            return {root_name: root_val}
        # それ以外は暗黙の root map として読む
        return r.read_map()
    except Exception:
        return {}

def _get_ci(d: dict, key: str):
    if key in d:
        return d.get(key)
    lk = key.lower()
    for k, v in d.items():
        if isinstance(k, str) and k.lower() == lk:
            return v
    return None

def _pick_lang(v, prefer: str = "japanese") -> Optional[str]:
    # 文字列ならそのまま
    if isinstance(v, str):
        s = v.strip()
        return s if s else None

    # dict なら language 別かもしれない
    if isinstance(v, dict):
        # まず直接キー
        for k in (prefer, prefer.lower(), "japanese", "english", "en", "ja"):
            vv = v.get(k)
            if isinstance(vv, str) and vv.strip():
                return vv.strip()
        # それでも無ければ、値の中で最初に見つかった文字列を使う
        for vv in v.values():
            s = _pick_lang(vv, prefer)
            if s:
                return s
    return None

def get_achievement_details_from_local_schema(appid: int, prefer_lang: str = "japanese") -> dict:
    """UserGameStatsSchema_<appid>.bin から apiname->(displayName,description) を拾う。

    Steam Web API では hidden 実績の説明が空になるゲームがあり、
    その場合 Steam クライアントのキャッシュ(UserGameStatsSchema_*.bin) に
    本文が入っていることがあるので最後の保険として使う。

    ※このファイルは Steam クライアントが一度「実績」ページを開いたとき等に生成されます。
    """
    cache_key = f"{appid}:{prefer_lang}"
    with _LOCAL_SCHEMA_CACHE_LOCK:
        cached = _LOCAL_SCHEMA_CACHE.get(cache_key)
        if isinstance(cached, dict):
            return cached

    schema_path = _get_usergamestats_schema_path(int(appid))
    if not schema_path:
        with _LOCAL_SCHEMA_CACHE_LOCK:
            _LOCAL_SCHEMA_CACHE[cache_key] = {}
        return {}

    try:
        data = Path(schema_path).read_bytes()
    except Exception:
        with _LOCAL_SCHEMA_CACHE_LOCK:
            _LOCAL_SCHEMA_CACHE[cache_key] = {}
        return {}

    kv = _parse_binary_vdf(data)
    out: dict = {}

    def _pick_localized_from_display(display_dict: dict):
        # SAM の構造: display -> { name:{lang:...}, desc:{lang:...}, ... }
        name_node = _get_ci(display_dict, "name") or _get_ci(display_dict, "displayName") or _get_ci(display_dict, "title")
        desc_node = _get_ci(display_dict, "desc") or _get_ci(display_dict, "description")
        dn = _pick_lang(name_node, prefer_lang)
        ds = _pick_lang(desc_node, prefer_lang)
        return dn, ds

    def visit(node):
        if isinstance(node, dict):
            api = _get_ci(node, "name") or _get_ci(node, "apiname") or _get_ci(node, "id")
            if isinstance(api, str) and api.strip():
                display = _get_ci(node, "display")
                dn = ds = None
                if isinstance(display, dict):
                    dn, ds = _pick_localized_from_display(display)

                # フォールバック（構造が違うゲーム向け）
                if not dn:
                    dn = _pick_lang(_get_ci(node, "displayName") or _get_ci(node, "displayname") or _get_ci(node, "title"), prefer_lang)
                if not ds:
                    ds = _pick_lang(_get_ci(node, "description") or _get_ci(node, "desc"), prefer_lang)

                if dn or ds:
                    cur = out.get(api) or {}
                    if dn and not (cur.get("displayName") or "").strip():
                        cur["displayName"] = dn
                    if ds and not (cur.get("description") or "").strip():
                        cur["description"] = ds
                    out[api] = cur

            for v in node.values():
                visit(v)

        elif isinstance(node, list):
            for v in node:
                visit(v)

    visit(kv)

    with _LOCAL_SCHEMA_CACHE_LOCK:
        _LOCAL_SCHEMA_CACHE[cache_key] = out
    return out


def get_schema_and_achievements(api_key, steam_id, appid):
    """指定 AppID の実績マスタ（表示名/説明）＋取得状況を返す。

    Steam Web API は hidden 実績の description を空で返すゲームがあるため、
    できる限り以下の順で補完します。

      1) GetSchemaForGame (japanese)
      2) GetSchemaForGame (english)  ※日本語が空のときのフォールバック
      3) IPlayerService/GetGameAchievements (japanese/english)
      4) Steam Community (Global Achievements) (japanese/english) ※取れるゲームのみ
      5) ローカル Steam キャッシュ UserGameStatsSchema_<AppID>.bin (japanese/english)

    返り値: (title, achievements(list[dict]), achievements_status(dict apiname->achieved))
    """

    # --- ユーザー側の取得状況 ---
    stats_url = (
        "https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/"
        f"?key={api_key}&steamid={steam_id}&appid={appid}"
    )
    stats_resp = requests.get(stats_url, timeout=15).json()
    if "playerstats" not in stats_resp or "achievements" not in stats_resp["playerstats"]:
        return None, None, None

    achievements_status = {
        a.get("apiname"): a.get("achieved")
        for a in stats_resp["playerstats"]["achievements"]
        if isinstance(a, dict) and isinstance(a.get("apiname"), str)
    }

    def _fetch_schema(lang: str) -> list:
        url = (
            "https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/"
            f"?key={api_key}&appid={appid}&l={lang}"
        )
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            js = r.json()
        except Exception:
            return []
        game = js.get("game", {}) if isinstance(js, dict) else {}
        achs = (game.get("availableGameStats", {}) or {}).get("achievements", []) or []
        return achs if isinstance(achs, list) else []

    # --- マスタ（schema）: 日本語優先、足りないところは英語で補完 ---
    achievements = _fetch_schema("japanese")
    if not achievements:
        achievements = _fetch_schema("english")

    # 日本語タイトル優先（キャッシュあり）
    title = get_game_title_prefer_jp_cached(int(appid)) or f"AppID:{appid}"

    # schema 英語フォールバック（description/displayName が空のとき）
    need_schema_en = any(
        isinstance(a, dict) and (not (a.get("description") or "").strip() or not (a.get("displayName") or "").strip())
        for a in achievements
    )
    schema_en_map = {}
    if need_schema_en:
        for a in _fetch_schema("english"):
            if isinstance(a, dict) and isinstance(a.get("name"), str):
                schema_en_map[a["name"]] = a

    # IPlayerService master（hidden を埋められるゲームがある）
    master_jp = get_game_achievements_master(api_key, int(appid), lang="japanese")
    master_en = None  # 遅延
    master_en_map = None

    # Community（取れるゲームのみ / 文字列キー）
    community_jp = {}
    community_en = {}
    need_community = any(isinstance(a, dict) and not (a.get("description") or "").strip() for a in achievements)
    if need_community:
        community_jp = get_global_achievement_descriptions_from_community(int(appid), lang="japanese") or {}
        community_en = get_global_achievement_descriptions_from_community(int(appid), lang="english") or {}

    # ローカル schema（Steam クライアントのキャッシュ）: apiname キー
    need_local_schema = any(isinstance(a, dict) and not (a.get("description") or "").strip() for a in achievements)
    local_schema_jp = {}
    local_schema_en = {}
    if need_local_schema:
        local_schema_jp = get_achievement_details_from_local_schema(int(appid), prefer_lang="japanese") or {}
        # 日本語が空のときに英語で補完できるように取っておく
        local_schema_en = get_achievement_details_from_local_schema(int(appid), prefer_lang="english") or {}

    # --- 補完処理 ---
    for a in achievements:
        if not isinstance(a, dict):
            continue
        api = a.get("name")

        # 1) schema 由来
        if (a.get("description") or "").strip():
            a["_desc_source"] = "schema_jp"

        # 2) schema 英語で補完（最優先：日本語を埋められないゲーム対策）
        if isinstance(api, str) and schema_en_map:
            se = schema_en_map.get(api)
            if isinstance(se, dict):
                if not (a.get("displayName") or "").strip():
                    dn = se.get("displayName")
                    if isinstance(dn, str) and dn.strip():
                        a["displayName"] = dn.strip()
                if not (a.get("description") or "").strip():
                    ds = se.get("description")
                    if isinstance(ds, str) and ds.strip():
                        a["description"] = ds.strip()
                        a["_desc_source"] = "schema_en"

        # 3) master (IPlayerService) で補完
        if isinstance(api, str) and isinstance(master_jp, dict):
            m = master_jp.get(api)
            if isinstance(m, dict):
                if not (a.get("displayName") or "").strip():
                    dn = m.get("displayName")
                    if isinstance(dn, str) and dn.strip():
                        a["displayName"] = dn.strip()
                if not (a.get("description") or "").strip():
                    ds = m.get("description")
                    if isinstance(ds, str) and ds.strip():
                        a["description"] = ds.strip()
                        a["_desc_source"] = "master_jp"

        # master 英語フォールバック
        if isinstance(api, str) and not (a.get("description") or "").strip():
            if master_en is None:
                master_en = get_game_achievements_master(api_key, int(appid), lang="english")
                master_en_map = master_en if isinstance(master_en, dict) else {}
            m = (master_en_map or {}).get(api) if isinstance(master_en_map, dict) else None
            if isinstance(m, dict):
                ds = m.get("description")
                if isinstance(ds, str) and ds.strip():
                    a["description"] = ds.strip()
                    a["_desc_source"] = "master_en"
                if not (a.get("displayName") or "").strip():
                    dn = m.get("displayName")
                    if isinstance(dn, str) and dn.strip():
                        a["displayName"] = dn.strip()

        # 4) Community（displayName キー）
        if not (a.get("description") or "").strip():
            disp = (a.get("displayName") or "").strip()
            if disp:
                cd = None
                if isinstance(community_jp, dict):
                    cd = community_jp.get(disp)
                if (not cd) and isinstance(community_en, dict):
                    cd = community_en.get(disp)
                if isinstance(cd, str) and cd.strip():
                    a["description"] = cd.strip()
                    a["_desc_source"] = "community"

        # 5) ローカル schema（apiname キー）
        if isinstance(api, str) and not (a.get("description") or "").strip():
            ls = local_schema_jp.get(api) if isinstance(local_schema_jp, dict) else None
            if not (isinstance(ls, dict) and (ls.get("description") or "").strip()):
                ls = local_schema_en.get(api) if isinstance(local_schema_en, dict) else ls

            if isinstance(ls, dict):
                if not (a.get("displayName") or "").strip():
                    dn = ls.get("displayName")
                    if isinstance(dn, str) and dn.strip():
                        a["displayName"] = dn.strip()
                ds = ls.get("description")
                if isinstance(ds, str) and ds.strip():
                    a["description"] = ds.strip()
                    a["_desc_source"] = "local_schema"

        if not (a.get("description") or "").strip():
            a.setdefault("_desc_source", "none")

    return title, achievements, achievements_status


# -----------------------------
# GUI：丸チェック
# -----------------------------
# GUI：丸チェック
# -----------------------------
class RoundCheck(tk.Frame):
    def __init__(self, master, name_text, appid_text="", command=None):
        super().__init__(master, bg=BG_PANEL)

        self.command = command
        self.var = tk.BooleanVar(value=False)
        self.visible = True

        self.columnconfigure(1, weight=1)

        self.canvas = tk.Canvas(
            self,
            width=18,
            height=18,
            bg=BG_PANEL,
            highlightthickness=0,
            borderwidth=0,
        )
        self.canvas.grid(row=0, column=0, padx=(0, 6))

        self.label_name = tk.Label(
            self,
            text=name_text,
            anchor="w",
            bg=BG_PANEL,
            fg=FG_MAIN,
            font=("NotoSansJP", 10),
        )
        self.label_name.grid(row=0, column=1, sticky="we")

        self.label_appid = tk.Label(
            self,
            text=f"AppID: {appid_text}",
            anchor="e",
            bg=BG_PANEL,
            fg="#9ca3af",
            font=("NotoSansJP", 9),
        )
        self.label_appid.grid(row=0, column=2, padx=(8, 20))

        self.canvas.bind("<Button-1>", self.toggle)
        self.label_name.bind("<Button-1>", self.toggle)
        self.label_appid.bind("<Button-1>", self.toggle)

        self._draw()

    def _draw(self):
        self.canvas.delete("all")
        self.canvas.create_oval(2, 2, 16, 16, outline="#9ca3af", width=2)
        if self.var.get():
            self.canvas.create_oval(5, 5, 13, 13, fill="#f9fafb", outline="")

    def toggle(self, _):
        self.var.set(not self.var.get())
        self._draw()
        if self.command:
            self.command()

    def get(self):
        return self.var.get()

    def set(self, value: bool):
        self.var.set(value)
        self._draw()


# -----------------------------
# GUI：Pill ボタン
# -----------------------------
class PillButton(tk.Canvas):
    def __init__(
        self,
        master,
        text,
        command=None,
        width=120,
        height=30,
        bg="#3f3e3d",
        fg="#ffffff",
        hover="#4b4a49",
        active="#2f2e2d",
    ):

        super().__init__(
            master,
            width=width,
            height=height,
            bg=BG_PANEL,
            highlightthickness=0,
            bd=0,
        )

        self.text = text
        self.command = command
        self.bg_color = bg
        self.fg_color = fg
        self.hover_color = hover
        self.active_color = active
        self.current_color = bg
        self.radius = height // 2
        self.enabled = True

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", lambda e: self._draw())
        self._draw()

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        if enabled:
            self.fg_color = "#ffffff"
            self.current_color = self.bg_color
        else:
            self.fg_color = "#9ca3af"
            self.current_color = "#2b2a29"
        self._draw()

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()

        r = self.radius
        # 左の丸
        self.create_oval(0, 0, h, h, fill=self.current_color, outline=self.current_color)
        # 右の丸
        self.create_oval(w - h, 0, w, h, fill=self.current_color, outline=self.current_color)
        # 中央の長方形
        self.create_rectangle(
            r,
            0,
            w - r,
            h,
            fill=self.current_color,
            outline=self.current_color,
        )

        self.create_text(
            w // 2,
            h // 2,
            text=self.text,
            fill=self.fg_color,
            font=("NotoSansJP", 11, "bold"),
        )

    def _on_enter(self, _):
        if not self.enabled:
            return
        self.current_color = self.hover_color
        self._draw()

    def _on_leave(self, _):
        if not self.enabled:
            return
        self.current_color = self.bg_color
        self._draw()

    def _on_press(self, _):
        if not self.enabled:
            return
        self.current_color = self.active_color
        self._draw()

    def _on_release(self, _):
        if not self.enabled:
            return
        self.current_color = self.hover_color
        self._draw()
        if self.command:
            self.command()


# -----------------------------
# 丸端ゲージ（Canvas ベース）
# -----------------------------
class RoundedProgressBar(tk.Canvas):
    def __init__(
        self,
        master,
        variable: tk.DoubleVar,
        track_color=GAUGE_TRACK_COLOR,
        bar_color=GAUGE_BAR_COLOR,
        height=8,
        *args,
        **kwargs,
    ):
        super().__init__(
            master,
            height=height,
            bg=BG_PANEL,
            highlightthickness=0,
            bd=0,
            *args,
            **kwargs,
        )
        self.variable = variable
        self.track_color = track_color
        self.bar_color = bar_color

        # フェード用 after id
        self._fade_after = None

        # 値／サイズが変わったら再描画
        self.variable.trace_add("write", lambda *_: self._draw())
        self.bind("<Configure>", lambda e: self._draw())

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()

        if w <= 2 or h <= 2:
            return

        # トラック（背景）
        self._draw_capsule(0, 0, w, h, self.track_color)

        # 値に応じてバー
        try:
            value = float(self.variable.get())
        except Exception:
            value = 0.0

        value = max(0.0, min(100.0, value))
        if value <= 0:
            return

        fill_len = w * (value / 100.0)
        if fill_len <= 0:
            return

        self._draw_capsule(0, 0, fill_len, h, self.bar_color)

    def _draw_capsule(self, x0, y0, x1, y1, color):
        """左右が丸いカプセル状のバーを描画"""
        w = x1 - x0
        h = y1 - y0
        r = h / 2
        if w <= 0 or h <= 0:
            return

        if w <= h:
            # 幅が高さより小さいときは単純な丸
            self.create_oval(x0, y0, x0 + w, y0 + h, fill=color, outline=color)
            return

        # 左丸
        self.create_oval(
            x0,
            y0,
            x0 + h,
            y0 + h,
            fill=color,
            outline=color,
        )
        # 右丸
        self.create_oval(
            x1 - h,
            y0,
            x1,
            y0 + h,
            fill=color,
            outline=color,
        )
        # 中央の四角
        self.create_rectangle(
            x0 + r,
            y0,
            x1 - r,
            y0 + h,
            fill=color,
            outline=color,
        )

    def animate_to_zero(self, duration=300):
        """ゲージをふわっと減衰させながら 0 に戻すアニメーション"""
        # すでにフェード中なら完全停止
        if self._fade_after is not None:
            try:
                self.after_cancel(self._fade_after)
            except Exception:
                pass
            self._fade_after = None

        start_value = float(self.variable.get())
        if start_value <= 0:
            self.variable.set(0.0)
            self._draw()
            return

        steps = 20
        step_time = max(1, duration // steps)

        def step(i):
            t = i / steps
            eased = (1 - t) ** 2  # ふわっと落ちるイージング
            new_value = start_value * eased
            self.variable.set(new_value)
            self._draw()
            if i < steps:
                self._fade_after = self.after(step_time, lambda: step(i + 1))
            else:
                self._fade_after = None
                self.variable.set(0.0)
                self._draw()

        step(0)


# -----------------------------
# メイン GUI
# -----------------------------

# -----------------------------
# 丸み付きスクロールバー（Canvas製 / つかみやすい）
# -----------------------------
class RoundedScrollbar(tk.Canvas):
    """
    ttk.Scrollbar では丸みが出せないため Canvas で自前実装。
    widget.configure(yscrollcommand=scrollbar.set)
    scrollbar.configure(command=widget.yview) と同等に使える。
    """
    def __init__(
        self,
        master,
        orient: str = "vertical",
        command=None,
        width: int = 12,
        pad: int = 2,
        radius: int = 6,
        trough_color: str = BG_PANEL,
        thumb_color: str = "#5a5857",
        thumb_hover: str = "#777574",
        thumb_active: str = "#9a9897",
        min_thumb: int = 44,
        **kwargs,
    ):
        super().__init__(
            master,
            width=width,
            highlightthickness=0,
            bd=0,
            bg=trough_color,
            **kwargs,
        )
        self.orient = orient
        self.command = command
        self.pad = pad
        self.radius = radius
        self.trough_color = trough_color
        self.thumb_color = thumb_color
        self.thumb_hover = thumb_hover
        self.thumb_active = thumb_active
        self.min_thumb = min_thumb

        self._first = 0.0
        self._last = 1.0
        self._dragging = False
        self._drag_offset = 0
        self._hover = False
        self._active = False

        # 描画・イベント
        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Motion>", self._on_motion)
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

    # ttk.Scrollbar互換
    def set(self, first, last):
        try:
            self._first = float(first)
            self._last = float(last)
        except Exception:
            self._first, self._last = 0.0, 1.0
        self._redraw()

    def get(self):
        return (self._first, self._last)

    def configure(self, cnf=None, **kw):
        if "command" in kw:
            self.command = kw.pop("command")
        return super().configure(cnf, **kw)

    # 内部描画
    def _set_hover(self, v: bool):
        self._hover = v
        self._redraw()

    def _on_motion(self, event):
        # つまみ上にいるかで hover 色を切替
        if self.orient != "vertical":
            return
        x, y = event.x, event.y
        x1, y1, x2, y2 = self._thumb_bbox()
        inside = (x1 <= x <= x2 and y1 <= y <= y2)
        if inside != self._hover:
            self._hover = inside
            self._redraw()

    def _thumb_bbox(self):
        w = max(1, int(self.winfo_width()))
        h = max(1, int(self.winfo_height()))
        pad = self.pad
        track = max(1, h - pad * 2)

        frac = max(0.0, min(1.0, self._last - self._first))
        thumb_len = max(self.min_thumb, int(frac * track))
        thumb_len = min(thumb_len, track)

        max_top = track - thumb_len
        top = int(self._first * track)
        top = max(0, min(max_top, top))

        x1 = pad
        x2 = w - pad
        y1 = pad + top
        y2 = y1 + thumb_len
        return x1, y1, x2, y2

    def _round_rect(self, x1, y1, x2, y2, r, color):
        # rが大きすぎる場合に備えて
        r = max(0, min(r, int((x2 - x1) / 2), int((y2 - y1) / 2)))
        if r == 0:
            self.create_rectangle(x1, y1, x2, y2, fill=color, outline="")
            return
        # 中央
        self.create_rectangle(x1 + r, y1, x2 - r, y2, fill=color, outline="")
        self.create_rectangle(x1, y1 + r, x2, y2 - r, fill=color, outline="")
        # 角（円）
        self.create_oval(x1, y1, x1 + 2*r, y1 + 2*r, fill=color, outline="")
        self.create_oval(x2 - 2*r, y1, x2, y1 + 2*r, fill=color, outline="")
        self.create_oval(x1, y2 - 2*r, x1 + 2*r, y2, fill=color, outline="")
        self.create_oval(x2 - 2*r, y2 - 2*r, x2, y2, fill=color, outline="")

    def _redraw(self):
        self.delete("all")
        # 背景（トラック）
        w = max(1, int(self.winfo_width()))
        h = max(1, int(self.winfo_height()))
        self.create_rectangle(0, 0, w, h, fill=self.trough_color, outline="")

        # つまみ
        if self.orient == "vertical":
            x1, y1, x2, y2 = self._thumb_bbox()
            color = self.thumb_color
            if self._active:
                color = self.thumb_active
            elif self._hover:
                color = self.thumb_hover
            self._round_rect(x1, y1, x2, y2, self.radius, color)

    def _on_press(self, event):
        if self.orient != "vertical":
            return
        x, y = event.x, event.y
        x1, y1, x2, y2 = self._thumb_bbox()
        if x1 <= x <= x2 and y1 <= y <= y2:
            # つまみをドラッグ
            self._dragging = True
            self._active = True
            self._drag_offset = y - y1
            self._redraw()
            return

        # トラッククリック：その位置に移動（つまみ中央合わせ）
        if self.command:
            w = max(1, int(self.winfo_width()))
            h = max(1, int(self.winfo_height()))
            pad = self.pad
            track = max(1, h - pad * 2)
            frac = max(0.0, min(1.0, self._last - self._first))
            thumb_len = max(self.min_thumb, int(frac * track))
            thumb_len = min(thumb_len, track)
            max_top = track - thumb_len
            target_top = (y - pad) - thumb_len / 2
            target_top = max(0, min(max_top, target_top))
            moveto = target_top / track
            try:
                self.command("moveto", moveto)
            except Exception:
                try:
                    self.command("moveto", str(moveto))
                except Exception:
                    pass

    def _on_drag(self, event):
        if not self._dragging or self.orient != "vertical" or not self.command:
            return
        h = max(1, int(self.winfo_height()))
        pad = self.pad
        track = max(1, h - pad * 2)

        frac = max(0.0, min(1.0, self._last - self._first))
        thumb_len = max(self.min_thumb, int(frac * track))
        thumb_len = min(thumb_len, track)

        max_top = track - thumb_len
        target_top = (event.y - pad) - self._drag_offset
        target_top = max(0, min(max_top, target_top))
        moveto = target_top / track
        try:
            self.command("moveto", moveto)
        except Exception:
            self.command("moveto", str(moveto))

    def _on_release(self, _event):
        self._dragging = False
        self._active = False
        self._redraw()

class SteamAchievementsGUI:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        root.configure(bg=BG_ROOT)
        root.geometry("1100x720")

        # アイコンパス（exe 内にも対応）
        icon_path = resource_path("steam_achi_multi.ico")
        try:
            root.iconbitmap(icon_path)
        except Exception as e:
            print("icon load error:", e)

        root.option_add("*Font", "NotoSansJP 10")

        self.api_key = tk.StringVar()
        self.steam_id = tk.StringVar()
        self.steam_path = tk.StringVar()
        self.output_path = tk.StringVar(value=DEFAULT_OUTPUT)

        self.games = []
        self.round_checks = []
        self.search_var = tk.StringVar()

        self.loading_label = None
        self.loading_text_var = tk.StringVar()
        self._loading_after_id = None
        self._loading = False
        self._loading_anim_step = 0

        # 日本語タイトル補完のキャンセル用トークン
        self._title_update_token = 0

        # Export 状態
        self._exporting = False
        self._cancel_export = False

        # 進捗ゲージ用
        self.progress_var = tk.DoubleVar(value=0.0)
        self._progress_anim_after = None
        self._progress_current = 0.0

        self._setup_style()
        self._build_layout()
        self.load_config()

        root.after(400, self.on_fetch_games)

    # -------------------------
    # スタイル
    # -------------------------
    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Crystal.TNotebook",
            background=BG_ROOT,
            borderwidth=0,
            highlightthickness=0,
            padding=0,
            bordercolor=BG_ROOT,
        )
        style.configure(
            "Crystal.TNotebook.Tab",
            font=("NotoSansJP", 10, "bold"),
            padding=(18, 8),
            background=BG_PANEL,
            foreground="#e5e7eb",
            borderwidth=0,
        )
        style.map(
            "Crystal.TNotebook.Tab",
            background=[("selected", "#3b3a39"), ("active", BG_PANEL)],
            foreground=[("selected", "#ffffff"), ("active", "#f9fafb")],
        )

                # スクロールバー（ChatGPT風のミニマル表示）
        style.configure(
            "Crystal.Vertical.TScrollbar",
            gripcount=0,
            width=10,
            background="#4b5563",   # つまみ
            troughcolor=BG_ROOT,    # レール
            bordercolor=BG_ROOT,
            arrowcolor=BG_ROOT,
            relief="flat",
        )
        style.map(
            "Crystal.Vertical.TScrollbar",
            background=[("!active", "#4b5563"), ("active", "#6b7280"), ("pressed", "#9ca3af")],
        )
        # 矢印を消す（レイアウトから除去）
        style.layout(
            "Crystal.Vertical.TScrollbar",
            [
                (
                    "Vertical.Scrollbar.trough",
                    {
                        "sticky": "ns",
                        "children": [
                            ("Vertical.Scrollbar.thumb", {"sticky": "nswe", "expand": "1"})
                        ],
                    },
                )
            ],
        )

        style.configure(
            "Crystal.Horizontal.TScrollbar",
            gripcount=0,
            width=10,
            background="#4b5563",
            troughcolor=BG_ROOT,
            bordercolor=BG_ROOT,
            arrowcolor=BG_ROOT,
            relief="flat",
        )
        style.map(
            "Crystal.Horizontal.TScrollbar",
            background=[("!active", "#4b5563"), ("active", "#6b7280"), ("pressed", "#9ca3af")],
        )
        style.layout(
            "Crystal.Horizontal.TScrollbar",
            [
                (
                    "Horizontal.Scrollbar.trough",
                    {
                        "sticky": "we",
                        "children": [
                            ("Horizontal.Scrollbar.thumb", {"sticky": "nswe", "expand": "1"})
                        ],
                    },
                )
            ],
        )


        # Treeview（プレビュー）をダーク寄せ
        style.configure(
            "Crystal.Treeview",
            background=BG_ENTRY,
            fieldbackground=BG_ENTRY,
            foreground=FG_MAIN,
            bordercolor=BG_PANEL,
            lightcolor=BG_PANEL,
            darkcolor=BG_PANEL,
            rowheight=24,
        )
        style.map(
            "Crystal.Treeview",
            background=[("selected", "#4b4a49")],
            foreground=[("selected", "#ffffff")],
        )
        style.configure(
            "Crystal.Treeview.Heading",
            background=BG_PANEL,
            foreground="#ffffff",
            relief="flat",
        )
        style.map(
            "Crystal.Treeview.Heading",
            background=[("active", "#3b3a39")],
            foreground=[("active", "#ffffff")],
        )

        # Treeview（プレビューをダークテーマに）
        style.configure(
            "Crystal.Treeview",
            background=BG_ENTRY,
            fieldbackground=BG_ENTRY,
            foreground=FG_MAIN,
            bordercolor=BG_PANEL,
            lightcolor=BG_PANEL,
            darkcolor=BG_PANEL,
            rowheight=24,
            relief="flat",
        )
        style.map(
            "Crystal.Treeview",
            background=[("selected", "#4b4a49")],
            foreground=[("selected", "#ffffff")],
        )
        style.configure(
            "Crystal.Treeview.Heading",
            background=BG_PANEL,
            foreground="#ffffff",
            relief="flat",
            bordercolor=BG_PANEL,
        )
        style.map(
            "Crystal.Treeview.Heading",
            background=[("active", "#3b3a39")],
            foreground=[("active", "#ffffff")],
        )

    # -----------------------------
    # UI レイアウト
    # -----------------------------
    def _build_layout(self):
        outer = tk.Frame(
            self.root,
            bg=BG_ROOT,
            highlightthickness=0,
            bd=0,
            highlightbackground=BG_ROOT,
        )
        outer.pack(fill="both", expand=True, padx=12, pady=12)

        hud = tk.Frame(
            outer,
            bg=BG_PANEL,
            highlightthickness=0,
            bd=0,
            highlightbackground=BG_PANEL,
        )
        hud.pack(fill="both", expand=True, padx=4, pady=4)

        self.notebook = ttk.Notebook(hud, style="Crystal.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=0, pady=0)

        self.achievements_frame = tk.Frame(self.notebook, bg=BG_PANEL)
        self.settings_frame = tk.Frame(self.notebook, bg=BG_PANEL)

        self.notebook.add(self.achievements_frame, text="実績")
        self.notebook.add(self.settings_frame, text="設定")

        self._build_achievements_tab()

        self.settings_page = SettingsPage(
            self.settings_frame,
            api_key_var=self.api_key,
            steam_id_var=self.steam_id,
            steam_path_var=self.steam_path,
            output_path_var=self.output_path,
            save_config_callback=self.save_config,
        )
        self.settings_page.pack(fill="both", expand=True)

    # -----------------------------
    # 実績タブ
    # -----------------------------
    def _build_achievements_tab(self):
        f = self.achievements_frame

        top = tk.Frame(f, bg=BG_PANEL)
        top.pack(fill="x", padx=16, pady=(16, 8))

        # ボタン群
        self.export_button = PillButton(top, "CSVで出力", self.on_export_achievements)
        self.export_button.pack(side="left", padx=(0, 10))

        PillButton(top, "すべて選択", self.select_all_games).pack(
            side="left", padx=(0, 10)
        )
        PillButton(top, "選択解除", self.clear_all_games).pack(side="left")

        PillButton(top, "リスト更新", self.on_fetch_games).pack(side="right")

        center = tk.Frame(f, bg=BG_PANEL)
        center.pack(fill="both", expand=True, padx=16, pady=(4, 8))

        games_frame = tk.Frame(center, bg=BG_PANEL)
        games_frame.pack(side="left", fill="both", expand=True)
        # --- 右側：実績プレビュー（ゲームを右クリックで表示） ---
        details_frame = tk.Frame(center, bg=BG_PANEL, width=450)
        details_frame.pack(side="right", fill="y", padx=(12, 8), pady=(0, 6))
        details_frame.pack_propagate(False)

        self.preview_title_var = tk.StringVar(value="プレビュー（チェックしたゲームを表示）")
        tk.Label(
            details_frame,
            textvariable=self.preview_title_var,
            bg=BG_PANEL,
            fg="#ffffff",
            font=("NotoSansJP", 12, "bold"),
            anchor="w",
            wraplength=430,
            justify="left",
        ).pack(fill="x", padx=(4, 4), pady=(2, 10))
        # 実績一覧（Treeview）
        tree_box = tk.Frame(details_frame, bg=BG_PANEL)
        tree_box.pack(fill="both", expand=True, padx=(4, 4), pady=(0, 6))

        cols = ("achieved", "name")
        self.preview_tree = ttk.Treeview(
            tree_box,
            columns=cols,
            show="headings",
            height=12,
            style="Crystal.Treeview",
        )
        self.preview_tree.heading("achieved", text="取得")
        self.preview_tree.heading("name", text="実績名")
        self.preview_tree.column("achieved", width=50, anchor="center", stretch=False)
        self.preview_tree.column("name", width=320, anchor="w", stretch=True)

        pv_scroll = RoundedScrollbar(
            tree_box,
            orient="vertical",
            command=self.preview_tree.yview,
            trough_color=BG_PANEL,
            width=12,
            radius=6,
            min_thumb=44,
        )
        self.preview_tree.configure(yscrollcommand=pv_scroll.set)

        self.preview_tree.pack(side="left", fill="both", expand=True)
        pv_scroll.pack(side="right", fill="y", padx=(4, 0))

        self.preview_tree.bind("<Enter>", lambda e: self.preview_tree.focus_set())

        # マウスホイールが左のゲーム一覧(Canvas)に伝播して一緒にスクロールしてしまうのを防ぐ
        def _preview_tree_mousewheel(event):
            if hasattr(event, "delta") and event.delta:
                self.preview_tree.yview_scroll(int(-event.delta / 120), "units")
                return "break"
        self.preview_tree.bind("<MouseWheel>", _preview_tree_mousewheel)
        # Linux
        self.preview_tree.bind("<Button-4>", lambda e: (self.preview_tree.yview_scroll(-1, "units"), "break")[1])
        self.preview_tree.bind("<Button-5>", lambda e: (self.preview_tree.yview_scroll(1, "units"), "break")[1])
        # 内容（説明）表示：内容のみ（ダークになじむ枠）
        content_outer = tk.Frame(
            details_frame,
            bg=BG_PANEL,
            highlightthickness=1,
            highlightbackground=BORDER_SOFT,
        )
        content_outer.pack(fill="x", padx=(4, 4), pady=(8, 0))

        tk.Label(
            content_outer,
            text="内容",
            bg=BG_PANEL,
            fg="#cbd5e1",
            font=("NotoSansJP", 9, "bold"),
            anchor="w",
        ).pack(fill="x", padx=8, pady=(6, 0))

        desc_box = tk.Frame(content_outer, bg=BG_PANEL)
        desc_box.pack(fill="both", expand=True, padx=8, pady=(6, 8))

        self.preview_desc = tk.Text(
            desc_box,
            height=4,  # 少し狭め
            bg=BG_ENTRY,
            fg="#e5e7eb",
            relief="flat",
            wrap="word",
            font=("NotoSansJP", 10),
            insertbackground="#e5e7eb",
        )
        desc_scroll = RoundedScrollbar(
            desc_box,
            orient="vertical",
            command=self.preview_desc.yview,
            trough_color=BG_PANEL,
            width=12,
            radius=6,
            min_thumb=44,
        )
        self.preview_desc.configure(yscrollcommand=desc_scroll.set)
        self.preview_desc.pack(side="left", fill="both", expand=True)
        desc_scroll.pack(side="right", fill="y", padx=(4, 0))
        self.preview_desc.configure(state="disabled")


        self.preview_tree.bind("<<TreeviewSelect>>", self._on_preview_select)

        self._preview_all_rows = []
        self._preview_current_appid = None
        self._preview_fetch_token = 0
        self._clear_preview_panel()

        header = tk.Frame(games_frame, bg=BG_PANEL)
        header.pack(fill="x", pady=(0, 10))

        search_wrap = tk.Frame(header, bg=BG_PANEL)
        search_wrap.pack(side="left")

        self.search_canvas = tk.Canvas(
            search_wrap,
            height=28,
            bg=BG_PANEL,
            highlightthickness=0,
            bd=0,
        )
        self.search_canvas.pack()

        def _resize_search_bar(_=None):
            pw = header.winfo_width()
            self.search_canvas.configure(width=int(pw * 0.4))

        header.bind("<Configure>", _resize_search_bar)
        search_wrap.bind("<Configure>", _resize_search_bar)

        self.search_entry = tk.Entry(
            self.search_canvas,
            textvariable=self.search_var,
            bg=SEARCH_BG,
            fg="#9ca3af",
            relief="flat",
            bd=0,
            insertbackground="#ffffff",
            font=("NotoSansJP", 10),
        )

        def redraw(_=None):
            self.search_canvas.delete("all")
            w = self.search_canvas.winfo_width()
            h = self.search_canvas.winfo_height()
            if w <= 1 or h <= 1:
                return
            r = 14

            self.search_canvas.create_oval(
                0, 0, h, h, fill=SEARCH_BG, outline=SEARCH_BG
            )
            self.search_canvas.create_oval(
                w - h, 0, w, h, fill=SEARCH_BG, outline=SEARCH_BG
            )
            self.search_canvas.create_rectangle(
                r, 0, w - r, h, fill=SEARCH_BG, outline=SEARCH_BG
            )

            lens_color = "#9ca3af"
            self.search_canvas.create_oval(
                6, 6, 18, 18, outline=lens_color, width=2
            )
            self.search_canvas.create_line(
                16, 16, 22, 22, fill=lens_color, width=2
            )

            self.search_canvas.create_window(
                (w // 2) + 10,
                h // 2,
                window=self.search_entry,
                width=w - 40,
                height=h - 8,
            )

        self.search_canvas.bind("<Configure>", redraw)

        canvas = tk.Canvas(
            games_frame,
            bg=BG_PANEL,
            highlightthickness=0,
            bd=0,
        )
        canvas.pack(side="left", fill="both", expand=True)

        scrollbar = RoundedScrollbar(
            games_frame,
            orient="vertical",
            command=canvas.yview,
            trough_color=BG_PANEL,
            width=12,
            radius=6,
            min_thumb=44,
        )
        scrollbar.pack(side="right", fill="y", padx=(8, 0))

        canvas.configure(yscrollcommand=scrollbar.set)
        self.games_canvas = canvas

        self.games_inner = tk.Frame(canvas, bg=BG_PANEL)
        win = canvas.create_window(0, 0, window=self.games_inner, anchor="nw")

        def _cfg(_=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win, width=canvas.winfo_width())

        self.games_inner.bind("<Configure>", _cfg)
        canvas.bind("<Configure>", _cfg)
        def _games_mousewheel(event):
            # Windows / macOS: MouseWheel, Linux: Button-4/5
            if hasattr(event, "delta") and event.delta:
                canvas.yview_scroll(int(-event.delta / 120), "units")
                return "break"

        canvas.bind("<MouseWheel>", _games_mousewheel)
        self.games_inner.bind("<MouseWheel>", _games_mousewheel)
        canvas.bind("<Enter>", lambda e: canvas.focus_set())
        self.games_inner.bind("<Enter>", lambda e: canvas.focus_set())
        # Linux
        canvas.bind("<Button-4>", lambda e: (canvas.yview_scroll(-1, "units"), "break")[1])
        canvas.bind("<Button-5>", lambda e: (canvas.yview_scroll(1, "units"), "break")[1])
        self.games_inner.bind("<Button-4>", lambda e: (canvas.yview_scroll(-1, "units"), "break")[1])
        self.games_inner.bind("<Button-5>", lambda e: (canvas.yview_scroll(1, "units"), "break")[1])

        # --- 下部：4行程度のコンパクト表示（ログ4行 + 進捗/中止を同一行に集約） ---
        # ここを小さくして上部の表示領域を確保する
        bottom_frame = tk.Frame(f, bg=BG_PANEL)
        bottom_frame.pack(fill="x", padx=16, pady=(0, 4))

        # 横並び：左=ログ(4行) / 右=進捗ゲージ+中止
        bottom_row = tk.Frame(bottom_frame, bg=BG_PANEL)
        bottom_row.pack(fill="x")

        bottom_row.grid_columnconfigure(0, weight=1)
        bottom_row.grid_columnconfigure(1, weight=0)

        # ログはスクロール無しで直近4行だけ表示（高さを抑える）
        self._log_lines = []
        self.log_label = tk.Label(
            bottom_row,
            text="",
            bg=BG_ENTRY,
            fg="#e5e7eb",
            justify="left",
            anchor="nw",
            font=("NotoSansJP", 10),
            height=4,
            padx=8,
            pady=3,
        )
        self.log_label.grid(row=0, column=0, sticky="nsew")

        right_box = tk.Frame(bottom_row, bg=BG_PANEL)
        right_box.grid(row=0, column=1, sticky="ns", padx=(10, 0))

        tk.Label(
            right_box,
            text="進捗",
            bg=BG_PANEL,
            fg=FG_MAIN,
            font=("NotoSansJP", 9),
        ).pack(side="left", padx=(0, 6))

        self.progress_bar = RoundedProgressBar(
            right_box,
            variable=self.progress_var,
            track_color=GAUGE_TRACK_COLOR,
            bar_color=GAUGE_BAR_COLOR,
            height=8,
            width=220,
        )
        self.progress_bar.pack(side="left", fill="x", expand=False)

        # 右端：中止
        self.cancel_button = PillButton(
            right_box,
            "中止",
            self.on_cancel_export,
            bg="#4b5563",
            width=70,
            height=22,
        )
        self.cancel_button.pack(side="left", padx=(8, 0))
        self.cancel_button.set_enabled(False)

        # 右側のゲージ幅をウィンドウ幅に追従（小さくなり過ぎないように下限あり）
        def _resize_progress_bar(_=None):
            total_w = bottom_row.winfo_width()
            if total_w <= 0:
                return
            # 右側(進捗 + 中止)に割ける幅をざっくり確保
            right_w = max(220, int(total_w * 0.35))
            gauge_w = max(160, right_w - 110)  # 「進捗」ラベル+中止+余白分
            try:
                self.progress_bar.configure(width=gauge_w)
            except Exception:
                pass

        bottom_row.bind("<Configure>", _resize_progress_bar)

        self._init_search_placeholder()
        self.search_var.trace_add("write", lambda *_: self.filter_games())

    # -----------------------------
    # 検索プレースホルダー
    # -----------------------------
    def _init_search_placeholder(self):
        """検索バーのプレースホルダー設定（ゲーム検索）"""
        self._search_placeholder = "ゲーム検索"

        if not self.search_var.get():
            self.search_var.set(self._search_placeholder)
            self.search_entry.configure(fg="#9ca3af")

        def focus_in(_):
            if self.search_var.get() == self._search_placeholder:
                self.search_var.set("")
                self.search_entry.configure(fg="#ffffff")

        def focus_out(_):
            if not self.search_var.get():
                self.search_var.set(self._search_placeholder)
                self.search_entry.configure(fg="#9ca3af")

        self.search_entry.bind("<FocusIn>", focus_in)
        self.search_entry.bind("<FocusOut>", focus_out)

    # -----------------------------
    # Log & filter
    # -----------------------------
    def _clear_log(self):
        """下部表示のログ（直近4行）をクリア"""
        try:
            self._log_lines = []
        except Exception:
            self._log_lines = []
        w = getattr(self, "log_label", None)
        if w is None:
            return
        try:
            if w.winfo_exists():
                w.configure(text="")
        except Exception:
            pass

    def log(self, msg):
        """下部のコンパクト表示に直近4行だけ出す"""
        try:
            lines = getattr(self, "_log_lines", [])
            lines.append(str(msg))
            lines = lines[-4:]
            self._log_lines = lines
        except Exception:
            self._log_lines = [str(msg)]

        w = getattr(self, "log_label", None)
        if w is None:
            return
        try:
            if w.winfo_exists():
                w.configure(text="\n".join(self._log_lines))
        except Exception:
            pass

    def _log_from_thread(self, msg: str):
        """別スレッドから安全にログを追加"""
        self.root.after(0, lambda m=msg: self.log(m))

    def clear_games_list(self):
        for w in self.games_inner.winfo_children():
            w.destroy()
        self.round_checks.clear()


    def select_all_games(self):
        for _appid, _name, rc in self.round_checks:
            rc.set(True)
        self._sync_preview_with_checked()

    def clear_all_games(self):
        for _appid, _name, rc in self.round_checks:
            rc.set(False)
        self._sync_preview_with_checked()

    def _sync_preview_with_checked(self):
        """チェック状態に合わせてプレビューを整合させる（バルク操作用）。"""
        checked = [(a, n) for a, n, rc in self.round_checks if rc.get()]
        if not checked:
            self._clear_preview_panel()
            return

        # 既にプレビュー中のゲームがチェック済みなら何もしない
        if self._preview_current_appid is not None:
            for a, _n in checked:
                try:
                    if int(a) == int(self._preview_current_appid):
                        return
                except Exception:
                    pass

        a, n = checked[0]
        try:
            self.on_preview_game(int(a), n)
        except Exception:
            pass

    def filter_games(self):
        keyword = self.search_var.get().lower().strip()

        if keyword == "" or keyword == "ゲーム検索":
            keyword = None

        for appid, name, rc in self.round_checks:
            if keyword is None:
                if not rc.visible:
                    rc.pack(anchor="w", fill="x", pady=2)
                    rc.visible = True
                continue

            match = keyword in name.lower()

            if match and not rc.visible:
                rc.pack(anchor="w", fill="x", pady=2)
                rc.visible = True
            elif not match and rc.visible:
                rc.pack_forget()
                rc.visible = False


    def _clear_preview_panel(self):
        """プレビューを初期状態に戻す（チェックが0件のとき等）"""
        self._preview_current_appid = None
        self._preview_all_rows = []
        try:
            self.preview_title_var.set("（ゲームにチェックを入れるとプレビューします）")
        except Exception:
            pass
        try:
            for item in self.preview_tree.get_children():
                self.preview_tree.delete(item)
        except Exception:
            pass
        self._set_preview_desc("")

    def _on_game_check_changed(self, appid: int):
        """ゲームのチェック状態が変わった時に呼ばれる。
        - チェックON: そのゲームの実績をプレビュー
        - チェックOFF: もしプレビュー中のゲームなら、他のチェック済みへ切替 or クリア
        """
        # round_checks: [appid, name, rc]
        current_item = None
        for a, n, rc in self.round_checks:
            if int(a) == int(appid):
                current_item = (a, n, rc)
                break
        if not current_item:
            return

        a, n, rc = current_item
        if rc.get():
            # チェックを入れたゲームをそのままプレビュー
            self.on_preview_game(int(a), n)
            return

        # チェックを外した
        if self._preview_current_appid == int(a):
            # まだチェックされている別ゲームがあればそちらを表示
            for a2, n2, rc2 in self.round_checks:
                if rc2.get():
                    self.on_preview_game(int(a2), n2)
                    return
            # 0件ならクリア
            self._clear_preview_panel()

    # -----------------------------
    # プレビュー（右側ペイン）
    # -----------------------------
    def on_preview_game(self, appid: int, fallback_name: str = ""):
        api_key = self.api_key.get().strip()
        steam_id = self.steam_id.get().strip()
        if not api_key or not steam_id:
            messagebox.showinfo("設定不足", "設定タブで API Key と SteamID64 を入力してください。")
            return

        self._preview_fetch_token += 1
        token = self._preview_fetch_token
        self._preview_current_appid = int(appid)

        disp = fallback_name or get_game_title_prefer_jp_cached(int(appid)) or "不明なゲーム"
        self.preview_title_var.set(f"{disp} 読み込み中…")

        # UI を空に
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)
        self._set_preview_desc("")

        def worker():
            try:
                title, achs, status = get_schema_and_achievements(api_key, steam_id, int(appid))
                if token != self._preview_fetch_token:
                    return

                rows = []
                if isinstance(achs, list) and isinstance(status, dict):
                    for a in achs:
                        if not isinstance(a, dict):
                            continue
                        api = a.get("name")
                        if not isinstance(api, str):
                            continue
                        name = (a.get("displayName") or api).strip()
                        desc = (a.get("description") or "").strip()
                        achieved = bool(status.get(api))
                        rows.append({
                            "api": api,
                            "name": name,
                            "desc": desc,
                            "achieved": achieved,
                        })

                def ui():
                    if token != self._preview_fetch_token:
                        return
                    self.preview_title_var.set(f"{title}")
                    self._preview_all_rows = rows
                    self._filter_preview()

                self.root.after(0, ui)

            except Exception as e:
                if token != self._preview_fetch_token:
                    return
                self.root.after(0, lambda: self.preview_title_var.set(f"{disp} 取得エラー: {e}"))

        threading.Thread(target=worker, daemon=True).start()


    def _filter_preview(self):
        """プレビュー行を描画（検索なし）。"""
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)

        rows = self._preview_all_rows if isinstance(self._preview_all_rows, list) else []
        for r in rows:
            if not isinstance(r, dict):
                continue
            api = r.get("api", "") or ""
            name = r.get("name", "") or ""
            achieved = "✓" if r.get("achieved") else ""

            # Treeview の iid はユニークである必要があるため、重複時は自動採番
            iid = api if api and not self.preview_tree.exists(api) else ""
            if iid:
                self.preview_tree.insert("", "end", iid=iid, values=(achieved, name), tags=(api,))
            else:
                self.preview_tree.insert("", "end", values=(achieved, name), tags=(api,))

    def _on_preview_select(self, _event=None):
        sel = self.preview_tree.selection()
        if not sel:
            return
        item = sel[0]
        tags = self.preview_tree.item(item, "tags") or ()
        api = tags[0] if tags else ""
    
        desc = ""
        for r in self._preview_all_rows:
            if isinstance(r, dict) and r.get("api") == api:
                desc = (r.get("desc", "") or "").strip()
                break
    
        # 内容が取れないケースの案内（空白のままだと原因が分かりにくいので）
        if not desc:
            appid = self._preview_current_appid
            schema_path = _get_usergamestats_schema_path(int(appid)) if appid else None
            if not schema_path:
                desc = "（内容が取得できませんでした。Steamクライアントでこのゲームの『実績』ページを一度開くと、ローカルキャッシュが生成されて内容を取得できる場合があります。）"
            else:
                desc = "（内容が取得できませんでした。このゲームはSteam Web APIではhidden実績の内容が空になる場合があります。）"
    
        self._set_preview_desc(desc)
    def _set_preview_desc(self, text: str):
        self.preview_desc.configure(state="normal")
        self.preview_desc.delete("1.0", "end")
        self.preview_desc.insert("end", text)
        self.preview_desc.configure(state="disabled")

    def _open_local_schema_for_preview(self):
        appid = self._preview_current_appid
        if not appid:
            return
        p = _get_usergamestats_schema_path(int(appid))
        if not p or not os.path.exists(p):
            messagebox.showinfo("参照", "ローカルスキーマファイルが見つかりません。\nSteamで一度そのゲームの実績ページを開くと生成されることがあります。")
            return
        try:
            if platform.system().lower().startswith("win"):
                os.startfile(os.path.dirname(p))
            else:
                os.startfile(p)
        except Exception:
            pass
    # -----------------------------
    # Loading
    # -----------------------------
    def _show_loading(self):
        self.clear_games_list()

        self.loading_text_var.set("Now Loading")
        self.loading_label = tk.Label(
            self.games_inner,
            textvariable=self.loading_text_var,
            bg=BG_PANEL,
            fg="#9ca3af",
            font=("NotoSansJP", 11, "bold"),
        )
        self.loading_label.pack(expand=True, pady=40)

        self._loading_anim_step = 0
        self._animate_loading()

    def _animate_loading(self):
        dots = "." * (self._loading_anim_step % 4)
        self.loading_text_var.set("Now Loading" + dots)
        self._loading_anim_step += 1
        self._loading_after_id = self.root.after(400, self._animate_loading)

    def _hide_loading(self):
        if self._loading_after_id is not None:
            try:
                self.root.after_cancel(self._loading_after_id)
            except Exception:
                pass
        self._loading_after_id = None

        if self.loading_label is not None:
            self.loading_label.destroy()
            self.loading_label = None

    # -----------------------------
    # Fetch games
    # -----------------------------
    def on_fetch_games(self):
        if self._loading:
            return

        api_key = self.api_key.get().strip()
        steam_id = self.steam_id.get().strip()

        # 既存の日本語タイトル補完スレッドをキャンセル
        self._title_update_token += 1
        token = self._title_update_token

        self._clear_log()
        self.log("所有ゲームを取得中...")
        self._show_loading()
        self._loading = True

        def worker():
            try:
                games = get_owned_games(api_key, steam_id)

                # ここでは高速に一覧を出すため、GetOwnedGames の name をそのまま使用
                # 日本語タイトルは一覧表示後にバックグラウンドで順次補完する
                games = sorted(games, key=lambda g: (g.get("name") or "").lower())
                error = None
            except Exception as e:
                games = []
                error = e

            self.root.after(0, lambda: self._on_fetch_games_done(games, error, token))

        threading.Thread(target=worker, daemon=True).start()

    def _on_fetch_games_done(self, games, error, token):
        self._hide_loading()
        self._loading = False

        if error is not None:
            messagebox.showerror("エラー", f"所有ゲームの取得に失敗しました:\n{error}")
            self.log(f"エラー: {error}")
            return

        self.games = games
        self.log(f"取得したゲーム数: {len(games)}")

        # 既存リストをクリア（リスト更新で重複しないように）
        self.clear_games_list()

        for g in games:
            appid = g.get("appid")
            name = g.get("name", f"AppID {appid}")

            rc = RoundCheck(
                self.games_inner,
                name_text=name,
                appid_text=str(appid),
                command=lambda a=appid: self._on_game_check_changed(a),
            )
            rc.pack(anchor="w", fill="x", pady=2)
            self.round_checks.append([appid, name, rc])

        self.filter_games()

        # 日本語タイトルはバックグラウンドで順次補完（UIは即表示）
        if USE_JP_TITLE:
            self._start_title_update_thread(token)


    def _start_title_update_thread(self, token: int):
        """一覧表示後に、日本語タイトルを順次取得して表示を更新する（UIブロック回避）。"""
        def worker():
            updated = 0
            # round_checks は [appid, name, rc] の可変リスト
            for item in list(self.round_checks):
                # 新しい更新が走ったら中断
                if token != self._title_update_token:
                    return

                try:
                    appid = item[0]
                    current_name = item[1]
                    rc = item[2]
                except Exception:
                    continue

                if not isinstance(appid, int):
                    continue

                # キャッシュあり。Store API は落ちることもあるので短めのタイムアウト。
                jp = get_game_title_prefer_jp_cached(appid, timeout=6)
                if token != self._title_update_token:
                    return

                if isinstance(jp, str) and jp.strip():
                    new_name = jp.strip()
                    if new_name != current_name:
                        def apply(item=item, rc=rc, new_name=new_name):
                            if token != self._title_update_token:
                                return
                            # round_checks の name と表示を更新
                            try:
                                item[1] = new_name
                            except Exception:
                                pass
                            try:
                                rc.label_name.configure(text=new_name)
                            except Exception:
                                pass

                        self.root.after(0, apply)
                        updated += 1

                        # フィルタ中なら見え方が変わるので、たまに再フィルタ
                        if updated % 25 == 0:
                            self.root.after(0, self.filter_games)

                # 叩き過ぎ防止（小さくスロットル）
                time.sleep(0.08)

            # 最後に1回フィルタ
            self.root.after(0, self.filter_games)

        threading.Thread(target=worker, daemon=True).start()

    # -----------------------------
    # 進捗ゲージ制御
    # -----------------------------
    def _stop_progress_anim(self):
        """root.after を使った進捗アニメーションを完全停止"""
        if self._progress_anim_after is not None:
            try:
                self.root.after_cancel(self._progress_anim_after)
            except Exception:
                pass
            self._progress_anim_after = None

    def _reset_progress(self):
        # 上昇アニメーションを完全停止
        self._stop_progress_anim()

        self._progress_current = 0.0
        self.progress_var.set(0.0)

    def _start_progress_anim(self, target: float):
        # すでにアニメーション中なら完全停止
        self._stop_progress_anim()

        start = self._progress_current
        diff = target - start

        # ゆっくり「すーっ」と伸びるアニメーション
        duration = 900  # ms

        def ease_in_out_cubic(t):
            if t < 0.5:
                return 4 * t * t * t
            else:
                return 1 - ((-2 * t + 2) ** 3) / 2

        start_time = time.time()

        def step():
            elapsed = (time.time() - start_time) * 1000.0
            t = min(elapsed / duration, 1.0)
            eased = ease_in_out_cubic(t)

            new_val = start + diff * eased
            self._progress_current = new_val
            self.progress_var.set(new_val)

            if t >= 1.0:
                self._progress_anim_after = None
            else:
                self._progress_anim_after = self.root.after(16, step)

        step()

    def _set_progress(self, current: int, total: int):
        if total <= 0:
            target = 0.0
        else:
            target = (current / total) * 100.0
        self.root.after(0, lambda t=target: self._start_progress_anim(t))

    # -----------------------------
    # Export 関連
    # -----------------------------
    def on_cancel_export(self):
        if not self._exporting:
            return
        self._cancel_export = True
        self._log_from_thread("中止要求を受け付けました。しばらくお待ちください。")

    def on_export_achievements(self):
        # 連打防止
        if self._exporting:
            return

        api_key = self.api_key.get().strip()
        steam_id = self.steam_id.get().strip()

        if not api_key or not steam_id:
            messagebox.showwarning(
                "注意", "API Key と SteamID を設定タブで入力してください。"
            )
            return

        selected = [(appid, name) for appid, name, rc in self.round_checks if rc.get()]
        if not selected:
            messagebox.showinfo("情報", "書き出すゲームにチェックを入れてください。")
            return

        # 単品出力 → 完全安全なファイル名を使用
        if len(selected) == 1:
            raw_name = selected[0][1]
            name = safe_filename(raw_name)
            auto_name = f"{name}_achievements.csv"
        else:
            auto_name = "SteamGames_achievements.csv"

        base_dir = os.path.dirname(self.output_path.get())
        if not base_dir:
            base_dir = os.path.dirname(DEFAULT_OUTPUT)

        if not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)

        output_path = os.path.join(base_dir, auto_name)

        # 状態初期化
        self._clear_log()
        self.log("実績取得を開始...")
        self._reset_progress()
        self._cancel_export = False
        self._exporting = True
        self.export_button.set_enabled(False)
        self.cancel_button.set_enabled(True)

        # 非同期で実績取得＆CSV書き出し（逐次書き込み）
        thread = threading.Thread(
            target=self._export_worker,
            args=(api_key, steam_id, selected, output_path),
            daemon=True,
        )
        thread.start()

    def _export_worker(self, api_key, steam_id, selected, output_path):
        total = len(selected)
        canceled = False
        had_rows = False

        # CSV を開いて、1 行ずつ書き込む
        try:
            f = open(output_path, "w", newline="", encoding="utf-8-sig")
        except Exception as e:
            self._log_from_thread(f"書き出しエラー: {e}")
            self.root.after(
                0,
                lambda: self._export_done(output_path, e, wrote=False, canceled=False),
            )
            return

        writer = csv.DictWriter(
            f,
            fieldnames=["ゲーム名", "取得状況", "実績名", "説明"],
        )
        writer.writeheader()

        try:
            for idx, (appid, base_name) in enumerate(selected, start=1):
                if self._cancel_export:
                    canceled = True
                    break

                self._log_from_thread(f"{base_name} (AppID: {appid}) 取得中...")
                try:
                    title, achievements, status = get_schema_and_achievements(
                        api_key, steam_id, appid
                    )
                    if achievements is None or status is None:
                        self._log_from_thread("  ⚠ 情報なし")
                        self._set_progress(idx, total)
                        continue

                    game_name = title or base_name

                    for a in achievements:
                        api = a.get("name")
                        display = a.get("displayName", "")
                        desc = a.get("description", "")
                        achieved = "✅" if status.get(api) == 1 else "❌"

                        writer.writerow(
                            {
                                "ゲーム名": game_name,
                                "取得状況": achieved,
                                "実績名": display,
                                "説明": desc,
                            }
                        )
                        had_rows = True

                except Exception as e:
                    self._log_from_thread(f"  エラー: {e}")

                # 進捗更新（すーっとアニメーション）
                self._set_progress(idx, total)

        finally:
            f.close()

        # 結果ゼロ
        if not had_rows:
            self.root.after(
                0,
                lambda: self._export_done(
                    output_path, None, wrote=False, canceled=canceled
                ),
            )
            return

        # 正常完了 or 中止（部分的に出力）
        self.root.after(
            0,
            lambda: self._export_done(
                output_path, None, wrote=True, canceled=canceled
            ),
        )

    def _export_done(self, output_path, error, wrote: bool, canceled: bool):
        """Export 完了時（メインスレッド側で実行）"""
        self._exporting = False
        self.export_button.set_enabled(True)
        self.cancel_button.set_enabled(False)

        # ★ 解決ポイント：
        #  1) 上昇アニメーションを完全停止
        #  2) その時点の値からゲージをふわっと 0 に戻す
        self._stop_progress_anim()
        self._progress_current = float(self.progress_var.get())
        self.progress_bar.animate_to_zero()

        if error is not None:
            messagebox.showerror("エラー", f"書き出し失敗:\n{error}")
            return

        if canceled:
            if wrote:
                messagebox.showinfo(
                    "中止",
                    f"処理を中止しましたが、一部は書き出されています。\n→ {output_path}",
                )
                self.log(f"中止（部分的に出力）→ {output_path}")
            else:
                messagebox.showinfo("中止", "処理を中止しました。CSV は出力されていません。")
                self.log("中止されました。")
            return

        if not wrote:
            messagebox.showinfo("情報", "実績が取得できませんでした。")
            return

        self.log(f"完了 → {output_path}")
        messagebox.showinfo("完了", "CSV 書き出しが完了しました。")

    # -----------------------------
    # Config Save / Load
    # -----------------------------
    def save_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "api_key": self.api_key.get(),
                        "steam_id": self.steam_id.get(),
                        "steam_path": self.steam_path.get(),
                        "output_path": self.output_path.get(),
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception:
            pass

    def load_config(self):
        if not os.path.exists(CONFIG_PATH):
            return
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                self.api_key.set(cfg.get("api_key", ""))
                self.steam_id.set(cfg.get("steam_id", ""))
                self.steam_path.set(cfg.get("steam_path", cfg.get("steam_root", "")))
                self.output_path.set(cfg.get("output_path", DEFAULT_OUTPUT))
        except Exception:
            pass


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = SteamAchievementsGUI(root)
    root.mainloop()
