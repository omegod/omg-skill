# cu 2.1 规格：后台派发与自绘应用支持

状态：草案 v1（2026-09-05）+ 增补 2.2/2.3/2.4（2026-09-06）。取代 cu 2.0 规格（其 M1–M4 已全部实现并通过 33/33 AX e2e + 20/20 视觉 e2e，规格作废）。
对标基线：ZCode CUA 插件 0.5.14（30 工具 + 独立签名 helper `dev.zcode.cua-helper` 3.11.2）。
约束不变：bash CLI + 纯 JSON；公开 API 优先；仅 macOS；macOS 26 的 TCC 授权只能由用户本人完成，不绕过。

## 0. 背景：一次真实任务暴露的差距

同一组任务（Chrome 播 B 站《蜡笔小新》；QQ音乐 播张杰《天下》→确认→暂停）分别用 cu 2.0 与原生 CUA 执行：

| 环节 | cu 2.0 | 原生 CUA |
|---|---|---|
| Chrome AX 观察/点击 | ✅ 等效（ax find/press、stale 保护、标题 oracle） | ✅（AXPress 元素动作） |
| Chrome 播放验证 | ✅ 窗口标题「正在播放音频」后缀 | ✅ 同 |
| QQ音乐 AX 观察 | ❌ 69 节点几乎全是无标签 `AXUnknown` | ✅ 88 元素，播放控制栏全带中文标签 |
| QQ音乐 搜索 | ⚠️ 实际成功但**无法验证**（结果页不在 AX 树） | ✅ 截图直接看到结果列表 |
| QQ音乐 点歌曲 | ❌ 无可见目标，键盘盲试 3 次放弃 | ✅ 截图定位 → 双击首行 → `[53] 歌曲名：天下 - 歌手名：张杰` |
| QQ音乐 暂停 | — | ⚠️ AX 元素点击、坐标点击均被吞 → **app-scoped 空格成功** |
| 视觉兜底 | ❌ 宿主无 Screen Recording，整条路死 | ✅ helper 自带授权 |

结论：语义通道设计（句柄/stale/fail-closed）不落后；差距集中在**权限锚点、AX 字段覆盖、后台事件派发**三处。

## 1. 根因分析：ZCode 为什么能非前台操作

### 1.1 权限锚点：独立签名 helper（TCC responsible process 模型）

- TCC 判定授权归属时看的是 **responsible process**（发起方链顶端 app），子进程继承父 app 的归属。cu.py 是宿主 app 经 Bash 拉起的子进程 → 录屏授权查宿主（本机 ZCode 宿主 = denied）。
- ZCode 方案：独立 app bundle `ZCode Computer Use.app`（bundle id `dev.zcode.cua-helper`，Developer ID 签名，team `8A5X4JJ39T`，`stable_identity: true`），Accessibility + Screen Recording **授权一次挂在 helper 身上**，与宿主升级解耦；宿主经 IPC broker（`ZCodeComputerUseIPC-1`，ndjson）代理全部操作。
- 参考文献：Qt《The Curious Case of the Responsible Process》、HackTricks macOS TCC、Eclectic Light《Permissions, privacy and TCC》、Ghostty #9263（反向案例：换 helper 剥离 responsible process）。
- **对 cu 的含义**：CLI 形态没有常驻签名身份，授权永远落在宿主上。这是形态约束：doctor 的分项报告 + 「视觉任务换 Terminal 宿主」runbook 保持，并在 SKILL.md 明示宿主要求。不做（也不能）自建授权锚点。

### 1.2 事件派发：HID 全局流 vs 定向通道（SkyLight 私有 API）

后台键鼠派发的技术阶梯（由公开到私有）：

1. `CGEventPost`（HID 系统流）→ 只达前台应用，且移动真实鼠标。**cu 现状**。
2. `CGEventPostToPid`（公开）→ 直投目标进程事件队列。键盘基本可行（macOS 无全局键盘过滤器）；鼠标面广但 Chromium/Blink 有信任过滤（缺 HID telemetry 的事件被静默丢弃），单独使用在部分场景失效，社区经验需配合 `CGEventTapCreateForPid`。
3. SkyLight 私有 API（Cua 开源 driver 与 ZCode 同款路线）：
   - `SLPSPostEventRecordTo`：翻转目标进程的 AppKit-active 态（**合成焦点**）——yabai 两步法：对前一前台进程与目标进程各调一次，只完成「事件路由焦点翻转」，不升窗、不切 Space；
   - `SLEventPostToPid`：经签名的 SkyLight 通道投递合成事件，绕开 IOHIDPostEvent，能通过 Chrome 渲染器的信任检查；
   - `_SLPSSetFrontProcessWithOptions`：真升窗（会触发 Space 重挂载）——应**规避**；
   - `_AXObserverAddNotificationAndCheckRemote`：私有 AX SPI，保持 Electron/Chromium AX 树在窗口被遮挡/异 Space 时存活。
   - AltTab / winby / cmd-tab 等开源项目佐证：窗口无激活聚焦**无公开 API 等价物**。

原生 CUA 工具面的对应证据：`type/key` 文档自述「经 synthetic-focus SkyLight session 投递（后台安全，含 Chromium）」；`left_click` 的 `window_event` 是窗口级定向投递（会自查遮挡并拒发被覆盖点位）。

**QQ音乐 case 的关键教训**：合成鼠标事件被自绘应用整体忽略是**平台级现象，原生也中招**（AXPress no-op、AX bounds 错位的窗口点击、坐标窗口点击三连败）；app-scoped 键盘一发入魂。→ 自绘 app 的兜底优先级必须是**键盘 > 鼠标**。

### 1.3 AX 字段覆盖：AXDescription 缺失

QQ音乐所有「看不见」的 UI 标签都在 **`AXDescription`**（实测：标题栏/关闭/推荐/乐馆/个人中心/播放控制栏/上一首/播放/歌曲名：…）。cu 的 walk 只读 `AXRole/AXTitle/AXValue` → 69 节点信息量 ≈ 原生 88 元素的盲化版。`AXDescription` 是 VoiceOver 语义体系的标准字段，公开 API，零风险。

### 1.4 视觉通道

窗口级截屏（`screencapture -l <window_id>`）本可截后台/被遮挡窗口，但宿主无录屏授权 → 死于 1.1 的权限锚点，非实现问题。cu 的截图坐标元数据 sidecar 与原生 frame_id 帧绑定坐标在设计上等价。

## 2. 改动规格

### M-A 语义层补全（公开 API，低风险）

1. **walk_tree 读 `AXDescription`/`AXHelp`**：节点输出增加 `desc`（截断 80 字符）；`ax find --text/--title` 同时匹配 description。验收：QQ音乐 `ax tree` 出现 `播放控制栏`、`播放`、`歌曲名：…` 节点。
2. 快照 sig 扩展：`sig[path] = [role, title]` → 保持不变（desc 参与显示不参与新鲜度校验，避免无关重绘导致 stale）。

### M-B 后台键盘通道（私有 API，探测式，可降级）

3. **`cu key` / `cu type` 新增 `--app <pid|bundle-id|名>`**（app-scoped 派发）：
   - 键盘首选 `CGEventPostToPid` 直投（公开 API，无全局键盘过滤，覆盖多数场景；QQ音乐 后台空格实测通过）；
   - SkyLight `SLPSPostEventRecordTo` 合成焦点档：**实现时暂缓**——其事件记录 ABI 未公开，盲调有客户端崩溃风险。落地形式为符号探测（dlopen/dlsym）+ 输出报告可用性；`channel` 取值 `pid | foreground`；`isActive` 检查类 app 的替代路径 = `open` 激活后前台派发（SKILL.md/troubleshooting 已注明）；
   - 不实现 `SLEventPostToPid` 的 HID telemetry 伪造与 primer-click 灰区（Chrome 鼠标信任过滤不碰——Chrome 场景 AXPress 已覆盖）；
   - 输出统一加 `channel` 字段；前台派发维持现有行为。
4. 安全边界不变：app-scoped 派发同样遵守「破坏性动作先确认」「不碰安全/隐私弹窗」；SKILL.md 补充「后台键入不经用户视线，务必先确认目标 app」。

### M-C 健壮性

5. **WebArea 空壳检测**：walk 结束若 WebArea 存在但子节点 < 5，等待 1.5s 重试（上限 2 次），输出标 `retried: true`。（Chrome 惰性建树实测坑：首 dump 0 链接 → 数秒后 161 链接。）
6. **`screenshot --window` 改用 `screencapture -l <window_id>`**：可截被遮挡/后台窗口，坐标元数据契约（origin/scale/region 标志）保持。
7. **`ax press` 落空引导**：目标 acts 为空但有 pos 时，错误输出 hint 建议 `click --mode pts` 或键盘路径；文案注明自绘 app 可能忽略合成鼠标事件。

### M-D 文档与测试

8. SKILL.md：核心循环补**第三输入通道**（app-scoped 键盘：AX 够不到 + 鼠标被吞时的兜底，QQ音乐实测唯一有效路径）；新增「媒体状态验证 oracle 清单」——Chrome 窗口标题「正在播放音频」后缀 / 播放菜单标题翻转（播放↔暂停）/ 播放控制栏 desc 歌名 / 进度时间文本；三者都是本次实战验证过的纯文本证据。
9. troubleshooting.md：新增「AX 半封闭自绘 app（QQ音乐型）」操作序：菜单/深链 → AXDescription 定位 → 键盘兜底；「AX bounds 与视觉错位」：元素点击落空（回执 ok 但无效果）先换键盘再换坐标。
10. e2e_ax.py 扩展：
    - QQ音乐 段（skip-if-absent，不依赖登录态写入）：tree 出现 desc 节点 → `key --app space` 切换播放态 → 菜单标题 oracle 翻转 → 再切回；
    - TextEdit 后台键入段：`type --app` 写入 → `ax attr` 读回一致（不激活窗口）；
    - 回归：原 33 步全绿；视觉 e2e 20 步全绿（Terminal 宿主）。

## 3. 明确不做（Non-goals）

- 不自建常驻 broker/daemon/helper app（CLI 形态与零依赖不变；授权锚点问题以文档诚实降级解决）；
- 不绕过、不模拟、不代按任何 TCC 授权（macOS 26 必须用户本人认证）；
- 不做 Chromium 鼠标信任伪造（HID telemetry / primer click 灰区）；Chrome 场景走 AXPress；
- 不对 canvas/游戏类 app（GHOST/Unity 型，只吃 `cghidEventTap`+mouseMoved）承诺后台能力——如实报告限制。

## 4. 里程碑

| M | 内容 | 规模 |
|---|---|---|
| A | AXDescription/AXHelp 读取 + find 匹配 | cu.py ~40 行 |
| B | `--app` 后台键盘（PostToPid + SkyLight 探测降级 + channel 字段） | ~120 行 |
| C | WebArea 空壳重试 + `screenshot -l` + press 落空 hint | ~50 行 |
| D | SKILL.md / troubleshooting / e2e 扩展 | 文档+测试 |

## 5. 参考资料

- Qt Blog — The Curious Case of the Responsible Process：https://www.qt.io/blog/the-curious-case-of-the-responsible-process
- HackTricks — macOS TCC：https://hacktricks.wiki/en/macos-hardening/macos-security-and-privilege-escalation/macos-security-protections/macos-tcc/
- Eclectic Light — Permissions, privacy and TCC（attribution chain）：https://eclecticlight.co/2025/11/08/explainer-permissions-privacy-and-tcc/
- Cua — Inside macOS window internals（SkyLight 后台驱动全解，SLEventPostToPid / SLPSPostEventRecordTo / 合成焦点 / Chrome 信任过滤）：https://cua.ai/blog/inside-macos-window-internals
- Stack Overflow — SLPSPostEventRecordTo 用法：https://stackoverflow.com/questions/63869388/how-to-use-private-api-slpsposteventrecordto-on-macos-app
- Stack Overflow — 后台应用发送快捷键（CGEventPostToPid 局限）：https://stackoverflow.com/questions/79530459/how-to-send-a-shortcut-key-to-a-background-application-in-macos-development
- alt-tab-macos（`_SLPSSetFrontProcessWithOptions` 实战与怪癖）：https://github.com/lwouis/alt-tab-macos
- Screenify — macOS Screen Recording Permissions Guide：https://www.screenify.studio/blog/2026-04-23-macos-screen-recording-permissions

## 6. 2.2 增补（已实现）：ax state 原生式优先级检索

B 站大页面实弹暴露的检索短板：`ax find` 全树 DFS 在 1000+ 节点 DOM 上
"默认上限够不到、`--all` 慢到超时"，而原生 `get_app_state` 按优先级秒回。
按「策略照搬、架构不搬」实现（不引入 daemon / 私有 API，沿用 §3 non-goals）：

- **`ax state <app>`**：BFS + 交互角色优先（可按压 > 输入 > 文本叶子 > 带文本
  次要；空容器只遍历不输出）+ 时间预算（默认 10s，`--timeout 0` 不限，5 万节点
  兜底上限）。每节点只读便宜属性（role/title/desc/value/children），修饰读
  （actions/settable/enabled/pos/size）只对入选元素做且受预算约束。
- **编号句柄**：元素带 `i` + `flags`（pressable/editable/disabled/focused），
  快照存 index→path 映射（附 pos/size 元数据）；`ax press/set/attr/focus/action/
  select` 接受纯数字编号，解析时做 role+title 签名 + pos/size 复核（±2pt）——
  动态网页 DOM 重排显式 stale，防静默按错同名节点。
- **隐藏实例过滤**：交互/输入角色 0×0 元素不占编号（关闭菜单项、网页同名
  隐藏副本；B 站暂停态合辑列表 100+ 个「播放/暂停」的教训）。
- 实测：B 站视频页 1865~2186 节点 0.6s 走完、播放/暂停预算内命中、编号 press
  切换播放态成功（暂停态控制栏）；e2e 55/55 覆盖编号 set/attr 回读、--text
  过滤、越界 not-found、Chrome 大页面预算断言。
- 站点行为结论（详见 troubleshooting）：播放中控制栏隐藏时 AXPress 无效，
  暂停态有效；空格依赖焦点；`ax attr w0` 对媒体页窗口标题必 stale（标题含
  播放态后缀），验证读值应重新 dump。

## 7. 2.3 增补（已实现）：--region-px 裁剪修复

opencode 宿主（macOS 26，有录屏权限）实测暴露：AttributeError 修复后裁剪本身仍不生效——
`screenshot --region-px 0 0 800 600` 返回 ok 但 PNG 仍是 3420×2224 全屏，且 meta 被污染
（origin 168,219 为上次 `--window` 残留属正常语义；**scale 8.55 = 3420÷400 是病征**），
下一次调用 `point_w 46.78 = 400÷8.55` 跨调用累积错乱。

根因两层：

1. **`screencapture -D N -R x,y,w,h` 同用时 `-R` 被忽略**（macOS 26 实测，man 页未写交互
   语义）：命令里 `-R` 拼进去了，但 `-D` 整屏生效，输出全屏 PNG。
2. **捕获后无尺寸校验**：meta 的 `scale = PNG宽 ÷ 区域点宽` 用实际 PNG 反推——裁剪没发生
   时算出 8.55 这种垃圾 scale 并落盘，把单次失败放大成链式污染。

修复（cu 2.3）：

- **区域捕获命令去掉 `-D`**：`screencapture -x -R x,y,w,h out.png`——`-R` 接受全局点坐标
  自带显示选择，与 `-D` 互斥；全屏捕获路径保留 `-D` 不变。
- **捕获后 fail-closed 校验**：PNG 实际像素必须等于期望值（±2px 容差），不符立即报错
  `region crop not applied: requested NxM px, got WxH`，**不写 meta**——裁剪静默失败
  从"污染后续所有换算"降级为"本次明确报错"。
- **期望值 = resolve_rect 的逆运算，scale 只能用换算时的同一个实测值**（image 模式期望
  == 输入像素；pts 模式 = 点 × prev scale），纯函数 `region_expected_px` 可独立验证。
  第一版曾用 CGDisplayPixelsWide ÷ point_w 估算显示 scale，被验证宿主打脸：macOS 26 上
  CGDisplayPixelsWide 返回**点数**（1710）而非物理像素（3420），期望被算成 400×300，
  把已正确裁出的 800×600 误报为失败。教训：断言基准不能依赖显示 API 口径，只能用
  同一管线自己量出来的数。

验证义务（交付门槛，实测教训）：在**有录屏权限的宿主**上跑
`scripts/e2e_test.py`（`open -a Terminal scripts/run-e2e.sh`），其中 4c 步
`screenshot-region-px` 断言 **PNG 实际像素 == 请求尺寸** 且 scale 复位；仅跑 e2e_ax 的
no-crash 步不构成裁剪功能的验收。

## 8. 2.4 增补（已实现）：open --background 与 doctor stale 口径纠偏

opencode 全链路审查报出两项（核实均属实）：

1. **`open` 无后台选项**：三条路径（`-b`/url/`-a`）都裸拼 `open`，"主窗口已关 + 不许切
   前台"即死局（QQ音乐 实历）。修复：`open --background` 透传 `open -g`（man 页实证
   "Does not bring the application to the foreground"）；输出增加 `backgrounded` 字段，
   frontmost 保持实测原值——后台唤起时模型不得误读为"已在前台"。e2e_ax 增加
   `open-background-no-foreground` 断言步（TextEdit 已 killall 不可能在前台）。
2. **doctor 的 screen-recording 报不出 stale**：`"ok" if sr else "denied"` 结构上只有
   两个出口，SKILL.md doctor 行却承诺 ok/stale/denied。且 preflight 在"已授权但宿主
   未重启"时照样 True，doctor 无法检出该态（曾有方案"拍测试图做纯色断言"被否——
   stale 截图是壁纸图像而非纯色，断言漏报）。修复（文档+文案路线）：
   - status 改三态 `ok/denied/unknown`（原实现把 macOS <10.15 的 None 吞成 denied）；
   - denied note 症状纠偏：denied 是硬失败（"could not create image"），不是静默坏图；
     原文案把 stale 的"壁纸-only"指纹安在了 denied 头上；
   - ok 分支新增常驻提示：stale 检不出，截图回 ok 但只有壁纸 = 重启宿主；
   - SKILL.md §0 stale 定义与 doctor 行同步改口径。
   - 附带（同批审查）：`clipboard set` 未检查 pbcopy 返回码，失败也回
     `ok:true`（返回码被埋进无意义的 `r` 字段），fail-closed 破洞——已改为
     非 0 即 fail（带 code），成功输出去掉 `r`。

## 9. 2.4 终稿（已实现）：open 三段式、单发看门狗与前台读数真值化

### 9.1 open 三段式（§8.1 初版被复测推翻后的最终设计）

初版 `--background` 只透传 `open -g` 并回 `backgrounded` 字段。复测发现半对：
`-g` 只约束 LaunchServices 的启动动作，**已运行 app 收到 open/reopen 事件后会
自激活抢前台**——实测矩阵：QQ音乐/QQ/微信/VSCode/Chrome 抢；TextEdit/访达不抢
（按 app 而定），且激活落地 0.5~4s+ 非确定。叠加用户诉求"已打开的应用不要重复
open"，`cmd_open` 定稿三段式：

- **已运行 + `--background`（无 `--force`）**：不发 open 事件，直接回
  `{mode:"already_running", via:"resolve", pid, windows, frontmost_after}`；
  零窗口时由调用方决定 `--force` 重开或 `key --app` 造窗。
- **冷启 / `--url`**：`open -g` 启动 + inline 轮询抓快抢，`mode:"launched_cold"`。
- **`--force` 且已运行**：用现有实例的 bundle-id 走 `open -b`（本地化名
  `open -a` 实测 `Unable to find application named 'QQ音乐'`，bundle-id 才可靠），
  `mode:"forced_reopen"`。
- `--background` 三段共用同一结束状态保证：**结束后前台仍是 `frontmost_before`**。
  被抢时如实报 `foreground_stolen_by`，inline 恢复（System Events 主路 +
  activateWithOptions 备，轮次重试 + 稳定持有裁决）成功则 `ok:true`；失败
  `ok:false code:"foreground_stolen"`——窗口可能已开出（功能达成），但后台保证
  破了，如实报告不粉饰。`backgrounded` 字段退役。
- SKILL.md 规则 8 写入判定规则：**成败判定读 `frontmost_after`，不许只看 mode**。

### 9.2 前台读数真值化：NSWorkspace 冻结缓存坑（本轮根因）

**受控实验实锤**：同进程内 `NSWorkspace.frontmostApplication()` 在无 runloop 的
CLI 进程里是 **AppKit 连接建立时刻的冻结缓存**——用 osascript 激活 Finder 后，
fresh osascript 与 CGWindowList 逐次读都跟踪真值，NSWorkspace 连续 6 读纹丝不动
报旧值。此前看门狗 `restored:false` 全是它的连锁误报：采样器/主进程启动于
ZCode 前台 → 对 QQ音乐 真实抢前台全盲；看门狗恰在激活落地瞬间启动 → 被钉死在
QQ音乐 → 4 轮恢复检查全盲判负（osascript 其实已生效，真值早已回到 ZCode）。

修复：`_frontmost_app()` 改为 **CGWindowList 最顶层 layer-0 常规窗口属主**
（无状态 C API，逐次读即真值；regular activationPolicy 优先，取不到退
NSWorkspace 兜底）。单点修复后所有前台读数（`frontmost_before/after`、inline
轮询、`_hold_front`、看门狗）同口径。与 §7 的 "CGDisplayPixelsWide 在 macOS 26
返回点数" 合并为同一条教训：**跨时刻的状态判定一律用无状态 API，不用 GUI 框架
的缓存态；断言基准不能建立在显示/GUI API 的口径上。**

### 9.3 单发看门狗（watchforeground，内部命令不进 SKILL 表）

- 单发有界（12s 观察期），只盯被 open 的那个 app：前台连续两读落回 opened_pid
  就把 restore_pid 拉回来，最多 2 次（实测重放激活会跟恢复拉锯）；用户主动切到
  其它 app 不干预。
- inline 恢复失败也照常 spawn（失败可能只是拉锯未平息，看门狗是最后一道兜底）。
- `restored` 语义 = **终态裁决**：观察期结束时 restore_pid 是否稳定持有前台
  （从未被抢也为 true）；`attempts` 数组保留每次恢复的 ok/via 供追查。
- 结果落盘 `~/.cache/omg-computer-use/foreground-watchdog.json`。

无干扰复跑实测（`open --bundle-id com.tencent.QQMusicMac --background --force`，
高频采样对账）：t≈1.4s QQ音乐 延迟激活真实抢前台 → inline `system-events(rc=0)`
恢复，t≈2.8s 前台回到 ZCode 并稳定保持 → 契约 `foreground_stolen_by:"QQ音乐"`,
`frontmost_restored:true`, `frontmost_after:"ZCode"`, `ok:true`；看门狗 12s 内
无再抢，终态 `restored:true`。时间线与采样器逐段一致。

### 9.4 原生行为对照（实测记录，作设计佐证）

- ZCode 原生 open_application 是 resolve-first：对已运行实例不发 open 事件、
  不激活、不造窗（窗口全部关闭的 VSCode 也不造窗）；activate=true 才激活且有
  postcondition 校验；无 `--force` 等价物（activate≠reopen，new_instance 是
  另起进程）。cu 的 already_running skip 与之同思路，`--force` 补"重开窗口"语义。
- macOS `open` 无 `--force` 类参数；`-g` 只管启动动作（见 9.1 实测矩阵）。
