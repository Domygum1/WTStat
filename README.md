# WTStat

本地 War Thunder Replay 战绩查询。双击 `start.bat`，浏览器访问 <http://127.0.0.1:8766>。

## 登录配置

直接输入 Replay Session ID 可匿名下载，无需 Cookie。官网按昵称搜索时，把 `config.local.example.json` 复制为 `config.local.json`，将本人已登录 `warthunder.com` 的 `identity_sid` 值填入文件。不要分享该文件。程序不打印 Cookie；`config.local.json` 已被 `.gitignore` 排除。Cookie 失效时手动更新。不支持自动登录或验证码绕过。

官网搜索同时支持昵称和 UID，直接使用官网当前的 Replay 接口。官网可查询范围和 Replay 保留时长由 Gaijin 决定。

## 使用

- 搜索昵称或 UID：首屏只请求官网一页，显示最近 15 场；“加载更多”按需读取后续页。
- 对局列表可按空战／陆战／海战和街机／历史／全真组合筛选。筛选即时作用于已加载的对局，不额外请求官网；点击“加载更多”后会继续筛选新读取的页面。
- 成功查询玩家昵称或 UID 后，“最近查询”会在本地 SQLite 保留最近 5 位玩家；Session ID 不计入。点击记录可再次查询，点旁边的“关注”可长期保留在“已关注”列表中，也可取消关注。打开这些本地列表不会请求官网。
- 日期范围筛选当前增量读取的官网页面。列表和详情页都将官网或 Replay 的 Unix 时间戳显示为 UTC。
- 点击对局：仅此时下载缺失的 `.wrpl` 分段；已有分段复用，结算结果写入 SQLite。
- 列表中已有本地 Replay 或解析结果的对局会标记“本地缓存”，右侧显示红色垃圾桶。确认后仅删除该局的 Replay 文件与解析结果；官网对局记录仍留在列表中，再次查看详情会重新获取。
- 对局列表右上角的“清除所有对局缓存”可在确认后删除全部已下载 Replay 和解析结果；当前对局列表、官网分页缓存、筛选状态、最近查询、关注玩家及 Wiki 载具表保留。已过期的 Replay 可能无法重新下载。
- 直接输入十进制 Session ID 或 16 位十六进制 Session ID，可跳过列表进入该局。
- 对局详情显示 Replay 返回的载具列表。“空中击杀”和“地面击杀”分别对应 Replay 的 `kills`、`groundKills`。点击这两列或死亡、助攻、得分表头即可排序；再次点击切换高到低或低到高，两队互不影响。
- 详情底部可展开“逐条死亡记录”，查看 Replay 战斗事件中的时间、击杀者、被击杀者和武器代码。只显示能可靠对应到玩家名单的 UID；无法对应的玩家显示 N/A。已有缓存且本地 Replay 文件仍在时，会在打开详情时从本地补齐这项数据。
- 通过昵称或 UID 查询并打开对局时，详情表格会以柔和底色标出所查询的玩家；排序后仍会保持高亮。直接输入 Session ID 不指定玩家，因此不高亮。
- 玩家表格的“队列国籍”由配置载具的科技树归属推导；无法确定唯一国家时显示 N/A。点击列名可按国家排序。国籍以本地图标显示，悬停可看名称；鼠标悬停玩家昵称可查看 UID。点击载具名称可跳转到本地 Wiki 载具资料表中对应的内部代码。
- 详情中的“权重”位于队列国籍与载具之间，取玩家所列载具在该局模式下的最高值，显示一位小数并可点击表头排序。空战／海战取对应 AB、RB、SB 列；陆战 RB／SB 中的飞机取 Wiki 的陆战专用权重列。若对局模式或任一载具的对应权重缺失，显示 N/A。模式优先使用已缓存的官网列表数据；直接输入 Session ID 且本地缺少模式时，若配置了 Cookie，会按需查询一次官网单场元数据。
- 详情里的载具按陆战、空战、直升机、海战排列；同类按该局对应权重从高到低排列，缺少权重的载具排在同类末尾。
- “其他”中的 AI 为 `aiKills + aiGroundKills + aiNavalKills`，并在非零时显示空中、地面、海上分类。旧缓存首次打开时只读取本地已下载的 Replay 补齐这两项；缺少原始文件时显示 N/A，不把未知值当作 0。原始 `humanKills` 在已测试 Replay 中始终为 0，页面不再展示这个容易误导的字段。
- 浏览器打开 <http://127.0.0.1:8766/vehicles> 可筛选载具资料表并下载完整 CSV。

所有文件都在本目录：`data/wtstat.sqlite3`、`data/wiki_vehicles.csv`、`cache/`、`.venv/`、`vendor/` 和 `bin/`。程序只绑定 `127.0.0.1`。

关闭程序：直接关闭运行 `start.bat` 的命令窗口（右上角 X），或双击 `stop.bat`，无需输入确认。若用 `Ctrl+C`，Windows 命令提示符可能询问“Terminate batch job (Y/N)?”；这是批处理自身的提示。关闭浏览器标签不会停止服务。旧版服务可能仍占用 8765 端口；请使用上面的 8766 地址。

## Wiki 载具资料表

`wiki_vehicles` SQLite 表和 `data/wiki_vehicles.csv` 收录官方 Wiki 当前 sitemap 的全部 3,252 个载具。字段包括名称、内部代码、分类、`vehicle_role`（Wiki 的游戏角色）、所属科技树、Wiki 的 Operator（游戏显示的现实所属国）以及 BR。Wiki 的游戏角色包括 Fighter、Strike aircraft、SPAA、Medium tank 等；它把 M1A2 一类现实中的主战坦克归为 Medium tank，因此本表沿用 Wiki 原词，不推断“主战坦克”。`br_ab`、`br_rb`、`br_sb` 是该分类的街机、历史、全真权重；飞机的这三列是空战，另有 `br_ground_rb`、`br_ground_sb` 表示飞机用于陆战时的权重。其他分类没有额外陆战列；Wiki 不提供的值为空。注意 Operator 与科技树可能不同，例如荷兰 F-16AM 属于法国科技树。

更新资料：运行 `.venv\Scripts\python.exe scripts\update_wiki_vehicles.py`。程序只读取 Wiki 的五个公开分类页及一个 sitemap；24 小时内复用保存在 `cache/wiki/` 的页面。`--refresh` 强制获取新页面，`--offline` 仅凭缓存重建表格。更新后重启 WTStat，让对局详情采用最新名称和国家映射。

载具名称前的特殊标志（例如东德 `◊`）由 Wiki 的 `WTSymbols` 字体绘制。本地页面使用 `static/fonts/symbols_skyquake.bfc9728c6a6bc73f209a.ttf`，来源：<https://wiki.warthunder.com/fonts/symbols_skyquake.bfc9728c6a6bc73f209a.ttf>。该字体属于 Wiki 提供的资源，不属于本项目的 AGPL 源码许可。

国旗图标保存在 `static/flags/`，避免 Windows 将 Unicode 国旗显示成字母。九面现行国旗来自 [flag-icons v7.5.0](https://github.com/lipis/flag-icons/tree/v7.5.0/flags/4x3)（MIT，许可证见 `static/flags/LICENSE-flag-icons.txt`）；苏联旗来自 [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Flag_of_the_Soviet_Union.svg)（Public Domain）。

## 依赖与解析器

Python 3.12+，依赖见 `requirements.txt`。随项目提供构建好的 Windows `bin/wtstat_results.exe`。解析器源代码在 `vendor/wrpl-inspector/`，基于 [wrpl-inspector](https://github.com/maxsupermanhd/wrpl-inspector)（AGPL-3.0）；本项目保留其许可证及源码，只在其 `wrplRead.go` 加了 zstd 数据流兼容，在 `cmd/wtstat_results/` 加了本地桥接程序。其他调查用仓库也保留在 `vendor/`，请分别遵守其许可证。完整源码可用同目录的 Go 1.25.6 重建：

本项目整体按根目录 `LICENSE`（AGPL-3.0）提供；WT-Plotter 的翻译目录与其原有 GPL/LGPL 许可证一并保留。

```powershell
cd C:\Desktop\WTStat\vendor\wrpl-inspector
$env:GOMODCACHE='C:\Desktop\WTStat\cache\go-mod'
$env:GOCACHE='C:\Desktop\WTStat\cache\go-build'
$env:GOPATH='C:\Desktop\WTStat\cache\gopath'
& 'C:\Desktop\WTStat\work\go-runtime\go\bin\go.exe' build -o 'C:\Desktop\WTStat\bin\wtstat_results.exe' ./cmd/wtstat_results
```

## 已知限制

新版 Replay 上结算数据可读，但当前实体解析尚不能可靠还原每位玩家实际出击的所有载具，因而相应格子通常为 N/A。载具名称和国家优先取本地 Wiki 表，缺失时退回 WT-Plotter 翻译目录；未知条目保留内部代码及 N/A。3 个无人机在 Wiki 列表中没有 Operator，26 个载具没有 BR，表内保持空值。若官网 Replay 接口改版，需要调整 `app.py` 的 `site_page`。下载遇到 404、403、429 和超时会明确报错。

逐条死亡记录的 UID 映射仍受新版 ECS 数据解析限制。已测试的 20 段真实样本含 135 条记录，其中 132 条可对应击杀者、62 条可对应被击杀者、61 条双方都能对应；未知身份不会推测。死亡事件条数不等于结算击杀数。

## AI 生成声明

WTStat 自有的程序代码、界面和文档 100% 由 GPT 生成。`vendor/` 中的第三方开源项目及引用的字体、图标归各自原作者所有，并遵循其原有许可证。
