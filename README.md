# Search for isaac

《以撒的结合：忏悔 / 忏悔+》控制台指令速查。搜中文名、英文名、拼音首字母或编号，点一下就复制指令。

线上版：

- <https://rip-lip.github.io/Search-for-isaac/> —— GitHub Pages，推 `main` 分支后自动重新发布
- <https://pvk7ilfp3kbd7.space.mcode.cn> —— 另一处部署，内容手动同步

游戏里按 ` 打开控制台需要先改 `options.ini`，把 `EnableDebugConsole` 设成 `1`。

## 指令格式

| 类别 | 给角色 | 在地上生成 |
| --- | --- | --- |
| 道具 C | `giveitem c1` | `spawn 5.100.1` |
| 饰品 T | `giveitem t35` | `spawn 5.350.35` |
| 卡牌 K | `giveitem k31` | `spawn 5.300.31` |
| 胶囊 P | `giveitem p0` | — |
| 掉落物 D | — | `spawn 5.10.1` |

大胶囊写成大写 P：`giveitem P0`，`P` 不能写成小写。
`remove *` 清空角色全部道具与饰品。

掉落物是地上的实体，没有对应的 `giveitem` / `remove`，页面上这类条目只有一个「实体」按钮。

## 条目

1141 条：

| 分类 | 条数 |
| --- | --- |
| 道具 C | 721 |
| 饰品 T | 188 |
| 卡牌 K | 97 |
| 胶囊 P | 50 |
| 掉落物 D | 85 |

## 数据从哪来

道具、饰品、卡牌、胶囊的编号、官方中文名、英文名、品质、图标，都是 `build.py` 从本机安装的
《以撒的结合：忏悔 / 忏悔+》解包资源里提取的：

- `stringtable.sta` —— 官方简体中文本地化
- `items.xml` —— 道具与饰品
- `items_metadata.xml` —— 道具品质
- `pocketitems.xml` —— 卡牌、符文、胶囊
- `gfx/items/` —— 图标

掉落物（红心、硬币、钥匙、宝箱、电池……）没法从本机资源反推：`stringtable.sta` 里只有
`THE_BATTERY_NAME` 一类的关联道具名，没有按子类型分的掉落物名；`entities2.xml` 里也没有 pickup 变体表。
这部分照 [Project:译名表/实体](https://isaac.huijiwiki.com/wiki/Project:%E8%AF%91%E5%90%8D%E8%A1%A8/%E5%AE%9E%E4%BD%93)
的「5 掉落物」段逐条写死在 `build.py` 的 `PICKUPS` 表里。`5.100` / `5.300` / `5.350` 三个泛用条目
就是道具、卡牌、饰品的生成指令，所以没重复列。

## 本地跑

```powershell
cd console-site
pip install pypinyin

python build.py          # 生成 docs/
python verify.py         # 53 项校验
python serve.py          # http://127.0.0.1:8765/
```

`python build.py --report` 只打印数据体检，不写文件。

## 几个坑

- `5.70.x` 是胶囊的纹理编号，不是效果编号。游戏开局时才随机决定每种纹理对应哪个效果，
  所以 `spawn 5.70.1` 拿到的效果是随机的。要指定效果请用 `giveitem p0`。
- 卡牌和胶囊只能写 `[类型][ID]`，不能输英文名。
- 剖腹产（C Section）只能写 `g c678` 或 `g C section`，写 `c section` 会被当成「道具」给出去。
- 命令对大小写敏感。

## 目录

```
build.py     抽数据、生成 docs/
verify.py    校验 docs/data.json
serve.py     本地预览服务器
site/        页面模板：index.html / style.css / app.js
docs/        构建产物，部署的就是它，也是 GitHub Pages 的发布目录
```

## 版权

《以撒的结合》及站内图标等素材的著作权归 [Nicalis](https://www.nicalis.com/) /
Edmund McMillen 所有。这是个人自用的非商业查询工具。

掉落物的中英文译名取自灰机wiki，按
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) 分享，出处已注明。
