# -*- coding: utf-8 -*-
"""
以撒的结合 · 控制台指令查询站 —— 数据构建脚本

数据全部来自本机已解包的原版游戏资源，不抓取任何第三方站点：

  stringtable.sta      -> 官方英文名 + 官方简体中文名（<language id="13">）
  items.xml            -> 道具 / 饰品 的 ID、内部名
  items_metadata.xml   -> 道具品质
  pocketitems.xml      -> 卡牌 / 符文 / 胶囊 的 ID 与内部名
  gfx/items/**         -> 道具与饰品图标

指令语法对照《以撒的结合：忏悔》调试控制台本身，交叉校对灰机wiki
《控制台》与 Project:译名表/实体 两页。

用法：
    python build.py            # 生成 docs/ 站点
    python build.py --report   # 只打印数据体检报告
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pypinyin import Style, lazy_pinyin

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

GAME_ROOT = Path(r"D:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth")
RES = GAME_ROOT / "extracted_resources" / "resources"
HERE = Path(__file__).resolve().parent
# 构建产物目录。叫 docs 是因为 GitHub Pages 只认仓库根下的 /docs 作为发布目录，
# REST API 的 path 只接受 / 与 /docs 两个值。
OUT = HERE / "docs"

STRINGTABLE = RES / "stringtable.sta"
ITEMS_XML = RES / "items.xml"
META_XML = RES / "items_metadata.xml"
POCKET_XML = RES / "pocketitems.xml"
GFX = RES / "gfx"

# stringtable.sta 的 <string> 顺序 = English, Japanese, Korean, Chinese (Simple), ...
# （<languages> 段里 index 0 是 Key 列，不占 <string> 位置）
LANG_ZH = 3

# 掉落物实体变体号（spawn 用）。胶囊的 spawn 子类型依赖 (颜色, 极性) 组合，
# 本地资源无法可靠反推，因此胶囊不提供「实体」指令。
SPAWN_VARIANT = {"C": 100, "T": 350, "K": 300}

# 掉落物（EntityType 5 的各变体）。
#
# 这部分无法从本机解包资源反推，已实测确认：
#   - stringtable.sta 只有关联道具名（THE_BATTERY_NAME 之类），没有按子类型分的掉落物名
#   - entities2.xml 里没有 pickup 变体表
#   - gfx/ 下只有 005.30x / 005.07x 一类的 anm2，掉落物贴图在 items/pick ups/ 下按类型合并
# 因此按灰机wiki Project:译名表/实体 的「5 掉落物」段固化。该页本身即控制台 ID 的
# 权威来源（站���「引用声明」页已标注出处）。
#
# 掉落物只能用 spawn 在地上生成，不存在 giveitem / remove 对应指令。
# 5.100 / 5.300 / 5.350 三个泛用条目分别已由道具 C / 卡牌 K / 饰品 T 的
# 「实体」按钮覆盖（spawn 5.100.N / 5.300.N / 5.350.N），不重复列出。
#
# 5.70.x 是「按纹理」编号，不是按效果编号：wiki《实体/5/70》原文写明「每当游戏
# 开始时，为每种纹理的胶囊分配一种随机胶囊效果」。也就是说 spawn 5.70.1 只会得到
# 一颗蓝底蓝点的胶囊，具体效果本局随机，无法对应到固定的 P{n}。因此胶囊条目在
# 「掉落物」里只能按纹理列，不能与「胶囊 P」按效果列的条目合并。
PICKUPS: list[tuple[str, str, str, str]] = [
    # (spawn 编码, 官方中文名, 英文名, 分组)
    ("5.10.1", "红心", "Heart", "心 / 回血"),
    ("5.10.2", "半红心", "Heart (half)", "心 / 回血"),
    ("5.10.3", "魂心", "Heart (soul)", "心 / 回血"),
    ("5.10.4", "永恒之心", "Heart (eternal)", "心 / 回血"),
    ("5.10.5", "双红心", "Heart (double)", "心 / 回血"),
    ("5.10.6", "黑心", "Black Heart", "心 / 回血"),
    ("5.10.7", "金心", "Gold Heart", "心 / 回血"),
    ("5.10.8", "半魂心", "Heart (half soul)", "心 / 回血"),
    ("5.10.9", "胆小的红心", "Scared Heart", "心 / 回血"),
    ("5.10.10", "混合心", "Blended Heart", "心 / 回血"),
    ("5.10.11", "骨心", "Bone Heart", "心 / 回血"),
    ("5.10.12", "腐心", "Rotten Heart", "心 / 回血"),
    ("5.20.1", "硬币", "Penny", "硬币"),
    ("5.20.2", "镍币", "Nickel", "硬币"),
    ("5.20.3", "铸币", "Dime", "硬币"),
    ("5.20.4", "双硬币", "Double Penny", "硬币"),
    ("5.20.5", "幸运硬币", "Lucky Penny", "硬币"),
    ("5.20.6", "黏性镍币", "Sticky Nickel", "硬币"),
    ("5.20.7", "金硬币", "Golden Penny", "硬币"),
    ("5.30.1", "钥匙", "Key", "钥匙"),
    ("5.30.2", "金钥匙", "Golden Key", "钥匙"),
    ("5.30.3", "双钥匙", "Key Ring", "钥匙"),
    ("5.30.4", "充能钥匙", "Charged Key", "钥匙"),
    ("5.40.1", "炸弹", "Bomb", "炸弹 / 屎块"),
    ("5.40.2", "双炸弹", "Double Bomb", "炸弹 / 屎块"),
    ("5.40.3", "即爆炸弹", "Troll Bomb", "炸弹 / 屎块"),
    ("5.40.4", "金炸弹", "Golden Bomb", "炸弹 / 屎块"),
    ("5.40.5", "超级即爆炸弹", "Megatroll Bomb", "炸弹 / 屎块"),
    ("5.40.6", "金即爆炸弹", "Golden Troll Bomb", "炸弹 / 屎块"),
    ("5.40.7", "巨型炸弹", "Giga Bomb", "炸弹 / 屎块"),
    ("5.41", "可投掷炸弹", "Throwable Bomb (pickup)", "炸弹 / 屎块"),
    ("5.42", "屎块", "Poop Nugget", "炸弹 / 屎块"),
    ("5.42.1", "大屎块", "Big Poop Nugget", "炸弹 / 屎块"),
    ("5.50", "箱子", "Chest", "宝箱"),
    ("5.51", "石头箱子", "Bomb Chest", "宝箱"),
    ("5.52", "刺箱子", "Spiked Chest", "宝箱"),
    ("5.53", "永恒箱子", "Eternal Chest", "宝箱"),
    ("5.54", "拟态箱子", "Mimic Chest", "宝箱"),
    ("5.55", "旧箱子", "Old Chest", "宝箱"),
    ("5.56", "木箱子", "Wooden Chest", "宝箱"),
    ("5.57", "大箱子", "Mega Chest", "宝箱"),
    ("5.58", "闹鬼箱子", "Haunted Chest", "宝箱"),
    ("5.60", "金箱子", "Locked Chest", "宝箱"),
    ("5.69.1", "福袋", "Grab Bag", "福袋"),
    ("5.69.2", "黑福袋", "Black Sack", "福袋"),
    ("5.70.1", "胶囊（蓝色-蓝色）", "Pill Blue-Blue", "胶囊（按纹理）"),
    ("5.70.2", "胶囊（白色-蓝色）", "Pill White-Blue", "胶囊（按纹理）"),
    ("5.70.3", "胶囊（橙色-橙色）", "Pill Orange-Orange", "胶囊（按纹理）"),
    ("5.70.4", "胶囊（白色-白色）", "Pill White-White", "胶囊（按纹理）"),
    ("5.70.5", "胶囊（斑点-红色）", "Pill Dots-Red", "胶囊（按纹理）"),
    ("5.70.6", "胶囊（粉色-红色）", "Pill Pink-Red", "胶囊（按纹理）"),
    ("5.70.7", "胶囊（蓝色-靛青）", "Pill Blue-Cadetblue", "胶囊（按纹理）"),
    ("5.70.8", "胶囊（黄色-橙色）", "Pill Yellow-Orange", "胶囊（按纹理）"),
    ("5.70.9", "胶囊（斑点-白色）", "Pill Dots-White", "胶囊（按纹理）"),
    ("5.70.10", "胶囊（白色-碧蓝）", "Pill White-Azure", "胶囊（按纹理）"),
    ("5.70.11", "胶囊（黑色-黄色）", "Pill Black-Yellow", "胶囊（按纹理）"),
    ("5.70.12", "胶囊（白色-黑色）", "Pill White-Black", "胶囊（按纹理）"),
    ("5.70.13", "胶囊（白色-黄色）", "Pill White-Yellow", "胶囊（按纹理）"),
    ("5.70.14", "胶囊（金色-金色）", "Pill Gold-Gold", "胶囊（按纹理）"),
    ("5.70.2049", "大胶囊（蓝色-蓝色）", "Horse Pill Blue-Blue", "胶囊（按纹理）"),
    ("5.70.2050", "大胶囊（白色-蓝色）", "Horse Pill White-Blue", "胶囊（按纹理）"),
    ("5.70.2051", "大胶囊（橙色-橙色）", "Horse Pill Orange-Orange", "胶囊（按纹理）"),
    ("5.70.2052", "大胶囊（白色-白色）", "Horse Pill White-White", "胶囊（按纹理）"),
    ("5.70.2053", "大胶囊（斑点-红色）", "Horse Pill Dots-Red", "胶囊（按纹理）"),
    ("5.70.2054", "大胶囊（粉色-红色）", "Horse Pill Pink-Red", "胶囊（按纹理）"),
    ("5.70.2055", "大胶囊（蓝色-靛青）", "Horse Pill Blue-Cadetblue", "胶囊（按纹理）"),
    ("5.70.2056", "大胶囊（黄色-橙色）", "Horse Pill Yellow-Orange", "胶囊（按纹理）"),
    ("5.70.2057", "大胶囊（斑点-白色）", "Horse Pill Dots-White", "胶囊（按纹理）"),
    ("5.70.2058", "大胶囊（白色-碧蓝）", "Horse Pill White-Azure", "胶囊（按纹理）"),
    ("5.70.2059", "大胶囊（黑色-黄色）", "Horse Pill Black-Yellow", "胶囊（按纹理）"),
    ("5.70.2060", "大胶囊（白色-黑色）", "Horse Pill White-Black", "胶囊（按纹理）"),
    ("5.70.2061", "大胶囊（白色-黄色）", "Horse Pill White-Yellow", "胶囊（按纹理）"),
    ("5.70.2062", "大胶囊（金色-金色）", "Horse Pill Gold-Gold", "胶囊（按纹理）"),
    ("5.90.1", "小电池", "Lil' Battery", "电池"),
    ("5.90.2", "微型电池", "Micro Battery", "电池"),
    ("5.90.3", "超级电池", "Mega Battery", "电池"),
    ("5.90.4", "金电池", "Golden Battery", "电池"),
    ("5.110", "铲子碎片", "Broken Shovel", "杂项"),
    ("5.150", "商店交易物品", "Shop Item", "杂项"),
    ("5.340", "通关宝箱", "Big Chest", "杂项"),
    ("5.360", "红箱子", "Red Chest", "杂项"),
    ("5.370", "挑战奖杯", "Challenge Trophy", "杂项"),
    ("5.380", "以撒的床", "Isaac's Bed", "杂项"),
    ("5.380.10", "妈妈的床", "Mom's Bed", "杂项"),
    ("5.390", "妈妈的箱子", "Mom's Chest", "杂项"),
]

CATS = ("C", "T", "K", "P", "D")
CAT_LABEL = {"C": "道具", "T": "饰品", "K": "卡牌", "P": "胶囊", "D": "掉落物"}
CAT_GIVE = {"C": "c", "T": "t", "K": "k", "P": "p"}
WIKI_URL = "https://isaac.huijiwiki.com/wiki/{}"


# --------------------------------------------------------------------------
# 语言表
# --------------------------------------------------------------------------


def load_stringtable() -> dict[str, tuple[str, str]]:
    """key -> (英文名, 简体中文名)"""
    root = ET.parse(STRINGTABLE).getroot()
    table: dict[str, tuple[str, str]] = {}
    for key in root.iter("key"):
        name = key.get("name")
        if not name:
            continue
        s = [(x.text or "").strip() for x in key.findall("string")]
        if s:
            table[name] = (s[0], s[LANG_ZH] if len(s) > LANG_ZH else "")
    return table


# --------------------------------------------------------------------------
# 物品表
# --------------------------------------------------------------------------


def load_items(strings) -> tuple[list[dict], list[dict]]:
    """items.xml -> (道具, 饰品)

    子元素按标签分道具类别（passive/active/familiar）。没有 gfx、name 也不带
    #KEY 引用的条目是内部缓存定义，不是可拾取道具，排除。
    """
    root = ET.parse(ITEMS_XML).getroot()
    coll, trink = [], []
    for el in root:
        gid, gfx, nk = el.get("id"), el.get("gfx"), (el.get("name") or "")
        if not gid or not gfx or not nk.startswith("#"):
            continue
        k = nk.lstrip("#")
        en, zh = strings.get(k, ("", ""))
        row = {"id": int(gid), "tag": el.tag, "en": en, "zh": zh}
        (trink if el.tag == "trinket" else coll).append(row)
    coll.sort(key=lambda x: x["id"])
    trink.sort(key=lambda x: x["id"])
    return coll, trink


def load_quality() -> dict[int, int]:
    root = ET.parse(META_XML).getroot()
    out: dict[int, int] = {}
    for el in root:
        if el.get("id"):
            out[int(el.get("id"))] = int(el.get("quality", 0))
    return out


def load_pocket(strings) -> tuple[list[dict], list[dict], list[dict]]:
    """pocketitems.xml -> (卡牌, 符文, 胶囊)

    卡牌 ID 与符文 ID 共用同一套 CardType 编号，合起来正好是 K1..K97。
    """
    root = ET.parse(POCKET_XML).getroot()
    cards, runes, pills = [], [], []
    for el in root:
        gid, nk = el.get("id"), (el.get("name") or "").lstrip("#")
        if not gid or nk.upper() == "NULL":
            continue
        en, zh = strings.get(nk, ("", ""))
        row = {
            "id": int(gid),
            "tag": el.tag,
            "type": el.get("type", ""),
            "pillClass": el.get("class", ""),
            "en": en,
            "zh": zh,
        }
        if el.tag == "card":
            cards.append(row)
        elif el.tag == "rune":
            runes.append(row)
        elif el.tag == "pilleffect":
            pills.append(row)
    for lst in (cards, runes, pills):
        lst.sort(key=lambda x: x["id"])
    return cards, runes, pills


# --------------------------------------------------------------------------
# 图标
# --------------------------------------------------------------------------


def index_numbered(directory: Path, prefix: str) -> dict[int, Path]:
    """collectibles_001_x.png -> {1: Path}"""
    rx = re.compile(rf"^{re.escape(prefix)}_(\d+)_", re.IGNORECASE)
    out: dict[int, Path] = {}
    if not directory.is_dir():
        return out
    for f in directory.iterdir():
        m = rx.match(f.name)
        if f.is_file() and m:
            out.setdefault(int(m.group(1)), f)
    return out


def build_icons() -> dict[str, dict[int, Path]]:
    # 卡牌与胶囊的贴图只以 .anm2 + 雪碧图形式存在，图标需按裁剪坐标逐帧切图，
    # 本次不做；这两类在页面上用类别占位符渲染。
    return {
        "C": index_numbered(GFX / "items" / "collectibles", "collectibles"),
        "T": index_numbered(GFX / "items" / "trinkets", "trinket"),
        "K": {},
        "P": {},
        "D": {},
    }


# --------------------------------------------------------------------------
# 拼音
# --------------------------------------------------------------------------


_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def initials(text: str) -> str:
    """中文取拼音首字母，英文取各单词首字母。悲伤洋葱->bsyc，The Sad Onion->tso"""
    if not text:
        return ""
    # errors="default" 会为非中文字符原样返回，从而让结果与输入逐字对齐
    py = lazy_pinyin(text, style=Style.FIRST_LETTER, errors="default")
    if len(py) != len(text):  # 对不齐就退化成逐字处理
        py = [lazy_pinyin(c, style=Style.FIRST_LETTER, errors="default")[0] or c
              for c in text]
    out: list[str] = []
    in_word = False
    for ch, p in zip(text, py):
        if _CJK.match(ch):
            if p.isascii() and p.isalpha():
                out.append(p.lower())
            in_word = False
        elif ch.isascii() and ch.isalpha():
            if not in_word:
                out.append(ch.lower())
            in_word = True
        else:
            in_word = False
    return "".join(out)


# --------------------------------------------------------------------------
# 组装
# --------------------------------------------------------------------------


def spawn_parts(code: str) -> tuple[int, int]:
    """'5.10.1' -> (10, 1)；'5.41' -> (41, 0)"""
    parts = code.split(".")
    return int(parts[1]), int(parts[2]) if len(parts) > 2 else 0


def spawn_sort_key(code: str) -> int:
    """'5.10.1' -> 1000001，'5.70.2062' -> 7002062

    掉落物的变体号不是连续的整数排序（5.40 < 5.41 < 5.42 < 5.42.1 < 5.50 < 5.90 < 5.110
    < 5.340 < 5.380 < 5.380.10 < 5.390），直接按 id 排会把 5.110 排到 5.90 前面。
    主段 * 1e5 + 次段：次段最大 2062，不会挤占主段，顺序与字典序一致。
    """
    major, minor = spawn_parts(code)
    return major * 100_000 + minor


def make_pickup_entry(code: str, zh: str, en: str, group: str) -> dict:
    major, _ = spawn_parts(code)
    return {
        "cat": "D",
        "catLabel": CAT_LABEL["D"],
        "code": code,
        "id": spawn_sort_key(code),
        "zh": zh,
        "en": en,
        "py": initials(zh),
        "enpy": initials(en),
        "sub": group,
        "pillClass": "",
        "quality": None,
        # 掉落物是地上的实体，没有 giveitem / remove 对应指令
        "give": None,
        "remove": None,
        "spawn": f"spawn {code}",
        "wiki": WIKI_URL.format(f"实体/5/{major}"),
    }


def make_entry(cat: str, row: dict, quality: dict[int, int]) -> dict:
    n = row["id"]
    g = CAT_GIVE[cat]
    variant = SPAWN_VARIANT.get(cat)
    entry = {
        "cat": cat,
        "catLabel": CAT_LABEL[cat],
        "code": f"{cat}{n}".lower(),
        "id": n,
        "zh": row["zh"],
        "en": row["en"],
        "py": initials(row["zh"]),
        "enpy": initials(row["en"]),
        "sub": row.get("type") or row.get("tag") or "",
        "pillClass": row.get("pillClass", ""),
        "quality": quality.get(n) if cat == "C" else None,
        "give": f"giveitem {g}{n}",
        "remove": f"remove {g}{n}",
        "spawn": f"spawn 5.{variant}.{n}" if variant else None,
        "wiki": WIKI_URL.format(f"{cat}{n}".upper()),
    }
    # 胶囊：大胶囊用大写 P，且 P 不能以小写形式输入
    if cat == "P":
        entry["giveBig"] = f"giveitem P{n}"
    return entry


def build() -> tuple[dict, dict]:
    strings = load_stringtable()
    coll, trink = load_items(strings)
    quality = load_quality()
    cards, runes, pills = load_pocket(strings)
    icons = build_icons()

    raw: dict[str, list[dict]] = {
        "C": coll,
        "T": trink,
        "K": cards + runes,
        "P": pills,
    }

    items: list[dict] = []
    missing_zh: list[str] = []
    missing_icon: dict[str, list[int]] = defaultdict(list)

    for cat in CATS:
        for row in raw.get(cat, []):  # D 不来自 xml，由下面的 PICKUPS 单独生成
            if not row["zh"]:
                missing_zh.append(f"{cat}{row['id']}")
            if row["id"] not in icons[cat]:
                missing_icon[cat].append(row["id"])
            e = make_entry(cat, row, quality)
            if icons[cat].get(row["id"]):
                e["icon"] = f"icons/{e['code']}.png"
            items.append(e)

    # 掉落物不在 items.xml / pocketitems.xml 里，直接用固化表
    for code, zh, en, group in PICKUPS:
        if not zh:
            missing_zh.append(code)
        items.append(make_pickup_entry(code, zh, en, group))

    # D 的 id 是 spawn 数值化后的排序键（见 spawn_sort_key），因此这一行对五类都成立
    items.sort(key=lambda x: (CATS.index(x["cat"]), x["id"]))

    data = {
        "meta": {
            "generated": datetime.now(timezone.utc).astimezone().isoformat(
                timespec="seconds"
            ),
            "game": "The Binding of Isaac: Repentance / Repentance+",
            "source": "本机已安装游戏的解包资源",
            "counts": {
                "total": len(items),
                **{CAT_LABEL[c]: sum(1 for i in items if i["cat"] == c) for c in CATS},
            },
        },
        "items": items,
    }

    report = {
        "strings": len(strings),
        "icons": {c: len(icons[c]) for c in CATS},
        "missing_zh": missing_zh,
        "missing_icon": {c: v for c, v in missing_icon.items() if c in ("C", "T")},
        "iconless_cats": [c for c in CATS if not icons[c]],
        "k_range": [min(r["id"] for r in raw["K"]), max(r["id"] for r in raw["K"])],
        "p_range": [min(r["id"] for r in raw["P"]), max(r["id"] for r in raw["P"])],
        "no_spawn": [
            CAT_LABEL[c] for c in CATS
            if not any(i["spawn"] for i in items if i["cat"] == c)
        ],
        "no_give": [CAT_LABEL[c] for c in CATS
                    if not any(i["give"] for i in items if i["cat"] == c)],
        "pickup_groups": {
            g: sum(1 for r in PICKUPS if r[3] == g) for g in dict.fromkeys(r[3] for r in PICKUPS)
        },
    }
    return data, report, icons


# --------------------------------------------------------------------------
# 产出
# --------------------------------------------------------------------------

SITE_FILES = ("index.html", "style.css", "app.js")


def asset_ver(generated: str) -> str:
    """把构建时间压成一个短版本号，例如 20261027T211144。

    托管方（mcode 的 CDN、GitHub Pages）给静态资源的是长缓存，
    浏览器会一直拿旧副本，代码改了线上却没变化。
    把版本号写进资源 URL，构建一变 URL 就变，浏览器必然重新取。
    """
    return generated.replace("-", "").replace(":", "")[:15]


def write_site(data: dict, icons: dict[str, dict[int, Path]]) -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "icons").mkdir(parents=True)

    copied = 0
    for e in data["items"]:
        if "icon" not in e:
            continue
        src = icons[e["cat"]].get(e["id"])
        if src:
            shutil.copyfile(src, OUT / e["icon"])
            copied += 1

    (OUT / "data.json").write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

    ver = asset_ver(data["meta"]["generated"])
    for name in SITE_FILES:
        p = HERE / "site" / name
        if not p.is_file():
            continue
        if name == "index.html":
            html = p.read_text(encoding="utf-8")
            html = html.replace('href="style.css"', f'href="style.css?v={ver}"')
            html = html.replace('src="app.js"', f'src="app.js?v={ver}"')
            (OUT / name).write_text(html, encoding="utf-8")
        elif name == "app.js":
            js = p.read_text(encoding="utf-8")
            js = js.replace("__BUILD_VER__", ver)
            (OUT / name).write_text(js, encoding="utf-8")
        else:
            shutil.copyfile(p, OUT / name)

    print(f"[ok] 站点 -> {OUT}")
    print(f"     data.json  {len(data['items'])} 条")
    print(f"     icons/     {copied} 个")
    print(f"     资源版本   {ver}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    for p in (STRINGTABLE, ITEMS_XML, META_XML, POCKET_XML):
        if not p.is_file():
            print(f"[x] 缺少数据文件：{p}", file=sys.stderr)
            return 1

    data, report, icons = build()
    c = data["meta"]["counts"]

    print("=" * 58)
    print("数据体检")
    print("=" * 58)
    print(f"语言表条目   {report['strings']}")
    print(f"条目合计     {c}")
    print(f"ID 区间      卡牌 K{report['k_range'][0]}-K{report['k_range'][1]}  "
          f"胶囊 P{report['p_range'][0]}-P{report['p_range'][1]}")
    print(f"掉落物分组   {report['pickup_groups']}")
    print(f"缺中文名     {len(report['missing_zh'])}")
    print(f"缺图标       {report['missing_icon'] or '无'}")
    print(f"无图标类别   {report['iconless_cats']}（改用类别占位符）")
    print(f"无实体指令   {report['no_spawn'] or '无'}")
    print(f"无道具指令   {report['no_give'] or '无'}")
    print("=" * 58)

    if args.report:
        return 0
    write_site(data, icons)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
