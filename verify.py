# -*- coding: utf-8 -*-
"""data.json 产物校验：抽样比对 + 全量一致性检查。部署前跑一次。"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(__file__).resolve().parent / "out"
DATA = OUT / "data.json"

# 人工核对的基准样本：(code, 官方中文名, 官方英文名)
# 中文名取自官方 stringtable.sta；其中 C36 / C177 / C45 / C686 / C118 同时与
# 小黑盒工具「里该隐」页显示的条目一致，可作交叉验证。
EXPECT = [
    ("c1", "悲伤洋葱", "The Sad Onion"),
    ("c36", "大便", "The Poop"),
    ("c45", "美味的心", "Yum Heart"),
    ("c118", "硫磺火", "Brimstone"),
    ("c177", "便携式老虎机", "Portable Slot"),
    ("c686", "灵魂吊坠", "Soul Locket"),
    ("t35", "弯羊角", "Curved Horn"),
    ("k1", "0-愚者", "0 - The Fool"),
    ("k31", "鬼牌", "Joker"),
    ("k97", "雅各与以扫的魂石", "Soul of Jacob and Esau"),
    ("p0", "剧毒臭屁", "Bad Gas"),
    ("p7", "体力上升", "Health Up"),
    # 掉落物基准取自 wiki Project:译名表/实体「5 掉落物」段（5.10.9 官译为「胆小的红心」，
    # 不是「胆小的小红心」；5.10.1 / 5.20.1 即用户举例的两条红心与硬币）
    ("5.10.1", "红心", "Heart"),
    ("5.10.9", "胆小的红心", "Scared Heart"),
    ("5.20.1", "硬币", "Penny"),
    ("5.42.1", "大屎块", "Big Poop Nugget"),
    ("5.60", "金箱子", "Locked Chest"),
    ("5.70.14", "胶囊（金色-金色）", "Pill Gold-Gold"),
    ("5.70.2062", "大胶囊（金色-金色）", "Horse Pill Gold-Gold"),
    ("5.390", "妈妈的箱子", "Mom's Chest"),
]

# 名称里本来就没有字母的条目（<3 / 20/20 / ???）不要求首字母
_HAS_LETTER = re.compile(r"[A-Za-z㐀-鿿]")

fail = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global fail
    if not ok:
        fail += 1
    print(f"  [{'OK ' if ok else 'FAIL'}] {label}{(' -> ' + detail) if detail else ''}")


def main() -> int:
    if not DATA.is_file():
        print("找不到 data.json，请先运行 build.py")
        return 1

    data = json.loads(DATA.read_text(encoding="utf-8"))
    items = data["items"]
    by_code = {i["code"]: i for i in items}

    print("=" * 58)
    print("抽样比对（对照官方中文名 / 英文名）")
    print("=" * 58)
    for code, zh, en in EXPECT:
        it = by_code.get(code)
        if not it:
            check(f"{code} 存在", False, "缺失")
            continue
        check(f"{code} = {zh} / {en}", it["zh"] == zh and it["en"] == en,
              f"实际 {it['zh']} / {it['en']}")

    print()
    print("=" * 58)
    print("全量一致性")
    print("=" * 58)
    m = data["meta"]["counts"]
    check("总条目 1141", m["total"] == len(items) == 1141, str(len(items)))
    check("道具 721", m["道具"] == 721, str(m["道具"]))
    check("饰品 188", m["饰品"] == 188, str(m["饰品"]))
    check("卡牌 97", m["卡牌"] == 97, str(m["卡牌"]))
    check("胶囊 50", m["胶囊"] == 50, str(m["胶囊"]))
    check("掉落物 85", m["掉落物"] == 85, str(m["掉落物"]))

    check("code 唯一", len(by_code) == len(items), f"{len(by_code)}/{len(items)}")
    check("无缺中文名", all(i["zh"] for i in items))
    check("无缺英文名", all(i["en"] for i in items))
    check("全部有 py", all(i["py"] for i in items if _HAS_LETTER.search(i["zh"])),
          str([i["code"] for i in items if not i["py"]]))
    check("全部有 enpy", all(i["enpy"] for i in items if _HAS_LETTER.search(i["en"])),
          str([i["code"] for i in items if not i["enpy"]]))
    check("C/T/K/P 全有 give", all(i["give"] for i in items if i["cat"] != "D"))
    check("C/T/K/P 全有 remove", all(i["remove"] for i in items if i["cat"] != "D"))

    k_ids = sorted(i["id"] for i in items if i["cat"] == "K")
    check("卡牌 ID 连续 1..97", k_ids == list(range(1, 98)), f"{k_ids[:3]}..{k_ids[-3:]}")
    p_ids = sorted(i["id"] for i in items if i["cat"] == "P")
    check("胶囊 ID 连续 0..49", p_ids == list(range(0, 50)))

    spawn_cats = {i["cat"] for i in items if i.get("spawn")}
    check("有 spawn 的类别 = C/T/K/D", spawn_cats == {"C", "T", "K", "D"}, str(spawn_cats))
    check("胶囊无 spawn", all(i["spawn"] is None for i in items if i["cat"] == "P"))
    check("胶囊有大胶囊指令", all(i.get("giveBig") for i in items if i["cat"] == "P"))

    check(
        "spawn 前缀正确",
        all(
            i["spawn"] == f"spawn 5.{v}.{i['id']}"
            for i in items
            if (v := {"C": 100, "T": 350, "K": 300}.get(i["cat"]))
        ),
    )

    print()
    print("=" * 58)
    print("掉落物 D")
    print("=" * 58)
    d = [i for i in items if i["cat"] == "D"]
    check("数量 85", len(d) == 85, str(len(d)))
    check("code 形如 5.x / 5.x.y",
          all(re.fullmatch(r"5\.\d+(\.\d+)?", i["code"]) for i in d),
          str([i["code"] for i in d if not re.fullmatch(r"5\.\d+(\.\d+)?", i["code"])][:5]))
    check("spawn 即 'spawn ' + code", all(i["spawn"] == f"spawn {i['code']}" for i in d))
    check("无 give / remove", all(i["give"] is None and i["remove"] is None for i in d))
    check("无图标", not any("icon" in i for i in d))

    # 变体号排序：5.40 < 5.41 < 5.42 < 5.42.1 < 5.50 < 5.90 < 5.110 < ... < 5.380 < 5.380.10 < 5.390
    order = [i["code"] for i in d]
    expected_order = sorted(order, key=lambda c: [int(x) for x in c.split(".")[1:]])
    check("按 spawn 变体号有序", order == expected_order,
          f"实际前6 {order[:6]} / 应为 {expected_order[:6]}")
    check("5.110 在 5.90 之后",
          order.index("5.110") > order.index("5.90.4"),
          f"5.90.4@{order.index('5.90.4')} 5.110@{order.index('5.110')}")

    groups = defaultdict(int)
    for i in d:
        groups[i["sub"]] += 1
    check("分组合计 = 85", sum(groups.values()) == 85, str(dict(groups)))

    # 5.100 / 5.300 / 5.350 是泛用条目，已由 C/K/T 的实体按钮覆盖，不应重复出现
    check("不含泛用条目 5.100/5.300/5.350",
          not ({"5.100", "5.300", "5.350"} & set(order)),
          str({"5.100", "5.300", "5.350"} & set(order)))
    check("胶囊纹理 28 条", sum(1 for c in order if c.startswith("5.70.")) == 28,
          str(sum(1 for c in order if c.startswith("5.70."))))
    check("胶囊纹理与大胶囊各 14",
          sorted(int(c.split(".")[2]) for c in order if c.startswith("5.70.")
                 and int(c.split(".")[2]) < 2049) == list(range(1, 15))
          and sorted(int(c.split(".")[2]) for c in order if c.startswith("5.70.")
                     and int(c.split(".")[2]) >= 2049) == list(range(2049, 2063)))

    print()
    print("=" * 58)
    print("图标文件")
    print("=" * 58)
    icon_dir = OUT / "icons"
    files = list(icon_dir.glob("*.png"))
    check("图标文件数 = 907", len(files) == 907, str(len(files)))
    expect_files = {Path(i["icon"]).name for i in items if i.get("icon")}
    check("data.json 引用的图标都存在",
          all((OUT / i["icon"]).is_file() for i in items if i.get("icon")))
    empty = [f.name for f in files if f.stat().st_size == 0]
    check("无 0 字节图标", not empty, str(empty[:5]))
    print(f"  信息：data.json 引用 {len(expect_files)} 个图标文件")

    print()
    print("=" * 58)
    print(f"结果：{'全部通过' if fail == 0 else f'{fail} 项未通过'}")
    print("=" * 58)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
