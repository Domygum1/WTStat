# WTStat

本地 War Thunder Replay 战绩查询。双击 `start.bat`，浏览器访问 <http://127.0.0.1:8766>。

启动窗口标题显示 `WTStat QUERY - Port 8766`；WTStat all 的采集窗口标题显示 `WTStat ALL - Replay Sampler - Port 8767`。关闭任一窗口只会停止对应程序。

## 登录配置

直接输入 Replay Session ID 可匿名下载，无需 Cookie。官网按昵称搜索时，把 `config.local.example.json` 复制为 `config.local.json`，将本人已登录 `warthunder.com` 的 `identity_sid` 值填入文件。不要分享该文件。程序不打印 Cookie；`config.local.json` 已被 `.gitignore` 排除。Cookie 失效时手动更新。不支持自动登录或验证码绕过。

官网搜索同时支持昵称和 UID，直接使用官网当前的 Replay 接口。官网可查询范围和 Replay 保留时长由 Gaijin 决定。

## 使用

- 搜索昵称或 UID：首屏只请求官网一页，显示最近 15 场；“加载更多”按需读取后续页。
- 打开 <http://127.0.0.1:8766/stats> 使用“统计”：输入玩家昵称或 UID、UTC 日期范围，分别选定空战／陆战／海战和街机／历史／全真；可点关注玩家一键填入 UID。官网列表每次最多增量读取 5 页。勾选对局后最多同时处理 2 场，显示进度、全体玩家的最高阵容权重（对局权重）、查询玩家权重、组队权重和科技树国籍。组队权重取该玩家非自动小队成员的最高权重；没有这类队友时等于自己的权重，旧缓存缺少小队信息且本地无 Replay 时显示 N/A。完成一位玩家后，可在上方输入另一位玩家并继续加入；同一份统计只合并相同的对局类型与模式。同一玩家的同一 Session 不重复加入；平均对局权重按独立 Session 计算，避免多位玩家参加同一局时重复计数。点击“新建统计”可清空本次合并结果。结果可按查询玩家的权重范围（1.0–14.7，数值小数部分为 .0／.3／.7）和科技树国籍筛选，国籍可选“全部”；筛选只影响已计算结果及其汇总，不触发额外下载。任一玩家的权重无法确定时，对局权重显示 N/A。新对局只探测分段并下载含结算信息的末段，不下载完整战斗日志；统计结果保存在 SQLite。统计页可批量删除所选对局的本地 Replay 文件，保留统计数据和官网列表。列表右侧分别显示“统计已缓存”“详情已缓存”“本地有 Replay 文件”或“需获取结算”，表示本地实际保存的内容；本地有 Replay 文件不保证已有结算数据。
- 统计页的已加入样本现在显示队伍、队友科技树国家、配置载具、对空击杀、地面击杀、死亡、助攻、得分和其他结算字段，并显示最早至最晚样本时间（UTC）。下方可按玩家及组队权重汇总 K/D、K/R、平均得分；空战可按单一配置载具拆分。K 取对空击杀＋地面击杀，海战不套用此口径；缺失字段显示 N/A。时间跨度和玩家表现随结果筛选更新，已加入样本的完整时间跨度始终显示。点击“导出已统计 CSV”可导出本页已加入的全部玩家对局（不受当前筛选影响），包含时间、地图、模式、队伍、权重、组队信息、配置载具 JSON 和全部已解析的结算战绩；不包含 Replay 文件或战斗日志。关闭或刷新统计页会清空浏览器中的合并清单，但解析缓存仍在 SQLite。
- 统计页点击一条已统计对局的时间或整行，可展开该局全部玩家，分蓝队／红队展示；这份数据直接复用已读取的结算缓存，不额外下载 Replay。统计主表、玩家表现表及两队玩家表的表头均可点击排序，再点切换方向；蓝队和红队排序互不影响。
- 对局列表可按空战／陆战／海战和街机／历史／全真组合筛选。筛选即时作用于已加载的对局，不额外请求官网；点击“加载更多”后会继续筛选新读取的页面。
- 成功查询玩家昵称或 UID 后，“最近查询”会在本地 SQLite 保留最近 5 位玩家；Session ID 不计入。点击记录可再次查询，点旁边的“关注”可长期保留在“已关注”列表中，也可取消关注。打开这些本地列表不会请求官网。
- 日期范围筛选当前增量读取的官网页面。列表和详情页都将官网或 Replay 的 Unix 时间戳显示为 UTC。
- 点击对局：仅此时下载缺失的 `.wrpl` 分段；已有分段复用，结算结果写入 SQLite。
- 列表中已有本地 Replay 或解析结果的对局会标记“本地缓存”，右侧显示红色垃圾桶。确认后仅删除该局的 Replay 文件与解析结果；官网对局记录仍留在列表中，再次查看详情会重新获取。
- 查询页的“显示已缓存战局”会列出全部本地缓存，包括仅有详情、仅有统计结果或仅有 Replay 文件的对局，无需先搜索到它们。可按“完全缓存／部分缓存”筛选：已保存详情解析结果，且该局原有的所有 Replay 分段都还在本地，才算完全缓存；其余为部分缓存。点击战局可打开详情；每场右侧的红色垃圾桶可单独删除。左侧复选框可勾选多场，顶部“全选”仅作用于当前筛选结果，“删除选择战局”会在确认后删除已选战局的 Replay 文件和解析结果。官网分页缓存、最近查询、关注玩家及 Wiki 载具表保留。已过期的 Replay 可能无法重新下载。
- 直接输入十进制 Session ID 或 16 位十六进制 Session ID，可跳过列表进入该局。
- 对局详情显示 Replay 返回的载具列表。“空中击杀”和“地面击杀”分别对应 Replay 的 `kills`、`groundKills`。点击这两列或死亡、助攻、得分表头即可排序；再次点击切换高到低或低到高，两队互不影响。
- 详情底部可展开“逐条死亡记录”，查看 Replay 战斗事件中的时间、击杀者、被击杀者和武器代码。只显示能可靠对应到玩家名单的 UID；无法对应的玩家显示 N/A。已有缓存且本地 Replay 文件仍在时，会在打开详情时从本地补齐这项数据。
- 通过昵称或 UID 查询并打开对局时，详情表格会以柔和底色标出所查询的玩家；排序后仍会保持高亮。直接输入 Session ID 不指定玩家，因此不高亮。
- 玩家表格的“队列国籍”由配置载具的科技树归属推导；无法确定唯一国家时显示 N/A。点击列名可按国家排序。国籍以本地图标显示，悬停可看名称；鼠标悬停玩家昵称可查看 UID。点击载具名称可跳转到本地 Wiki 载具资料表中对应的内部代码。
- 详情中的“权重”位于队列国籍与载具之间，取玩家所列载具在该局模式下的最高值，显示一位小数并可点击表头排序。空战／海战取对应 AB、RB、SB 列；陆战 RB／SB 中的飞机取 Wiki 的陆战专用权重列。若任一载具的对应权重缺失，显示 N/A。模式可由 Replay 文件头或已缓存的官网列表提供；旧缓存缺少模式时会用现有 Replay 文件补齐，本地仍无法确定时才按需查询官网单场元数据。
- 详情里的载具按陆战、空战、直升机、海战排列；同类按该局对应权重从高到低排列，缺少权重的载具排在同类末尾。
- 查询详情会剔除队伍无效、没有配置载具且没有任何战绩的挂名玩家，已缓存的旧详情在下次打开时也会清理。仍有有效队伍但未出击的玩家保留在详情中；他们不参与对局 BR 和组队 BR 的计算。系统 Bot 也不参与 BR 计算。有配置载具或非零战绩的真人玩家计为参战证据；Replay 的配置载具不能严格证明实际出击，若有战绩但缺少可识别的载具权重，对局 BR 仍显示 N/A。
- “其他”中的 AI 为 `aiKills + aiGroundKills + aiNavalKills`，并在非零时显示空中、地面、海上分类。旧缓存首次打开时只读取本地已下载的 Replay 补齐这两项；缺少原始文件时显示 N/A，不把未知值当作 0。原始 `humanKills` 在已测试 Replay 中始终为 0，页面不再展示这个容易误导的字段。
- 浏览器打开 <http://127.0.0.1:8766/vehicles> 可筛选载具资料表并下载完整 CSV。

所有文件都在本目录：`data/wtstat.sqlite3`、`data/wiki_vehicles.csv`、`cache/`、`.venv/`、`vendor/` 和 `bin/`。程序只绑定 `127.0.0.1`。

关闭程序：直接关闭运行 `start.bat` 的命令窗口（右上角 X），或双击 `stop.bat`，无需输入确认。若用 `Ctrl+C`，Windows 命令提示符可能询问“Terminate batch job (Y/N)?”；这是批处理自身的提示。关闭浏览器标签不会停止服务。旧版服务可能仍占用 8765 端口；请使用上面的 8766 地址。

## Wiki 载具资料表

`wiki_vehicles` SQLite 表和 `data/wiki_vehicles.csv` 收录官方 Wiki 当前 sitemap 的全部 3,252 个载具。字段包括名称、内部代码、分类、`vehicle_role`（Wiki 的游戏角色）、所属科技树、Wiki 的 Operator（游戏显示的现实所属国）以及 BR。Wiki 的游戏角色包括 Fighter、Strike aircraft、SPAA、Medium tank 等；它把 M1A2 一类现实中的主战坦克归为 Medium tank，因此本表沿用 Wiki 原词，不推断“主战坦克”。`br_ab`、`br_rb`、`br_sb` 是该分类的街机、历史、全真权重；飞机的这三列是空战，另有 `br_ground_rb`、`br_ground_sb` 表示飞机用于陆战时的权重。其他分类没有额外陆战列；Wiki 不提供的值为空。注意 Operator 与科技树可能不同，例如荷兰 F-16AM 属于法国科技树。

更新资料：运行 `.venv\Scripts\python.exe scripts\update_wiki_vehicles.py`。程序只读取 Wiki 的五个公开分类页及一个 sitemap；24 小时内复用保存在 `cache/wiki/` 的页面。`--refresh` 强制获取新页面，`--offline` 仅凭缓存重建表格。更新后重启 WTStat，让对局详情采用最新名称和国家映射。

## Replay 导弹名称表

`data/missile_names.csv` 和 SQLite `missile_names` 表按 Replay 内部武器代码保存导弹名称。对局详情的战斗日志显示名称，鼠标悬停可看原始代码；下载的 JSON 同时保留 `weapon` 和 `weapon_name`。没有精确映射的武器仍显示原始代码。

Wiki 的[武器目录](https://wiki.warthunder.com/collections/weapon)提供展示名称和部分武器页，但并未列出每种 Replay 内部代码。代码与名称的精确对应取自游戏的 `units_weaponry.csv`（[Wiki 本地化指南](https://wiki.warthunder.com/cdk/1819-a-better-guide-to-localization-mods)说明该文件，[公开游戏数据镜像](https://github.com/gszabi99/War-Thunder-Datamine/blob/master/lang.vromfs.bin_u/lang/units_weaponry.csv)提供文件）；CSV 的 `wiki_url` 仅在 Wiki 武器目录或载具武器栏能够核实时填写。更新命令：`.venv\Scripts\python.exe scripts\update_missile_names.py --verify-observed`；`--offline` 用本地源文件重建，`--refresh` 重新获取。更新后重启程序。

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

## 离线 Replay JSON 与战斗日志

在项目根目录运行：

```powershell
.\bin\wtstat_results.exe --json .\cache\replays\127b0049001c6bd4
.\bin\wtstat_results.exe --battle-log .\cache\replays\127b0049001eedc1
.\.venv\Scripts\python.exe scripts\test_replay_parser.py
```

`--json` 只读取本地分段，不访问网络。可附加第三个参数指定载具 CSV；默认使用 `data/wiki_vehicles.csv`。输出包含十六进制 `session_id`、UTC 时间、地图名称及原始标识、秒数时长、队伍、玩家 UID/昵称、载具和战绩。地图名称复用 WT-Plotter 的确切标识映射，缺少映射时为 null。载具国家只按 CSV 内部代码精确匹配，`nation` 是科技树，`operator_nations` 是 Wiki Operator。

`vehicles` 来自结算的配置阵容；`actual_vehicles`、`spawned` 无法确认时为 null。`statistics.kills` 保留结算原始字段（空中击杀），地面/海上击杀另列，不能当作合计。缺失统计是 null，真实 0 保留为 0。没有最终结算标记的中间 BLK 不作为最终战绩。`errors` 和 `unsupported_fields` 明确记录不支持的内容。

原来的 `FILE...` 和 `--carve DIR HASHES` 调用保持兼容，并新增同格式的 `match` 字段。`--json` 还输出按时间排序的 `battle_log`；`--battle-log` 只导出日志。日志覆盖当前解析器能识别的摧毁、暴击/严重伤害、奖励和聊天消息；每条摧毁消息含玩家 UID（若可确定）、实体编号、载具/武器代码、目标类型及原始死亡类型值。`weapon_owner_uid` 只表示武器持有者，不算作死亡玩家。页面中的“战斗日志”只显示玩家击杀与玩家坠毁，仍可下载完整解析日志 JSON；已缓存详情会优先用本地 Replay 刷新一次，无需重新下载。玩家目标缺少来源或武器时，页面显示“坠毁”；有击杀归属的玩家姓名会保留，没有来源则显示横线。下载的原始日志字段不改。

实测 5 场 `0x18C1C`、共 80 段，160 名玩家的 UID/队伍/核心战绩及 323 条配置载具与结算 BLK 一致；报告保存在 `cache/parser-tests/`。

## 已知限制

新版 Replay 上结算数据可读，但当前实体解析尚不能可靠还原每位玩家实际出击的所有载具，因而相应格子通常为 N/A。载具名称和国家优先取本地 Wiki 表，缺失时退回 WT-Plotter 翻译目录；未知条目保留内部代码及 N/A。3 个无人机在 Wiki 列表中没有 Operator，26 个载具没有 BR，表内保持空值。若官网 Replay 接口改版，需要调整 `app.py` 的 `site_page`。下载遇到 404、403、429 和超时会明确报错。

新版 ECS 的构造消息多一个前导字节，已针对本地 `0x18C1C` 样本修正，并在实体销毁时清理 UID 映射。4 场空战样本的全部玩家死亡均可对应 UID。20 段样本的 135 条摧毁消息中，132 条可对应来源玩家、120 条可对应目标玩家、12 条只给出武器持有者槽位、3 条只给出侦察无人机实体；不能把后 15 条伪装成玩家死亡。部分其他 ECS 组件仍因新版格式/哈希缺失而报解析警告，实际出击载具可能不完整。逐条助攻及未实现的 Replay 消息类型尚不能导出；已解析的战斗日志不等于游戏全部网络数据。

## AI 生成声明

WTStat 自有的程序代码、界面和文档 100% 由 GPT 生成。`vendor/` 中的第三方开源项目及引用的字体、图标归各自原作者所有，并遵循其原有许可证。
