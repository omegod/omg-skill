# cu 2.1 规格：后台派发与自绘应用支持

状态：草案 v1（2026-09-05）。取代 cu 2.0 规格（其 M1–M4 已全部实现并通过 33/33 AX e2e + 20/20 视觉 e2e，规格作废）。
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
