---
name: computer-use
description: macOS 桌面自动化技能（Codex Computer Use 方向 + ZCode 式 AX 语义层）。当需要操作 Mac 上的图形界面——查看/操作 GUI 应用、点击按钮、填写表单、操作菜单、截图确认界面状态——而 CLI/文件工具覆盖不了时使用。两段式：优先无障碍（AX）语义动作（后台安全，不动鼠标不抢焦点），AX 够不到的自绘界面再走「截屏 → 坐标 → 执行 → 再截屏验证」视觉循环。仅限 macOS。
---

# macOS Computer Use

面向 agent 的 macOS 桌面操作技能。所有命令经 `bash scripts/cu.sh <命令>` 调用，
输出统一 JSON（`{"ok": true/false, ...}`）。

## 0. 前置：权限检查（每个会话第一次操作前执行一次）

```bash
bash <skill目录>/scripts/cu.sh doctor
```

> 首次运行若无 `.venv`，脚本会自动创建并安装 pyobjc，然后以 `bootstrapped, rerun`
> 提示退出——**重跑同一命令**即可（已实测）。

- `ok: true` → 两个权限齐备，继续。分项状态见 `checks.status`：
  `accessibility`（AX 读写 + 键鼠注入）与 `screen-recording`（截屏）。
  `stale` = 已授权但宿主未重启，AX/截屏仍会失败 → 让用户完全重启宿主 App。
  accessibility 的 stale 由 doctor 实测探出；**screen-recording 的 stale 检不出**
  （preflight 照样 ok），指纹是截图回 ok 但内容只有壁纸。
- `ok: false` → 按 `notes` 提示用户在 System Settings → Privacy & Security 中给
  **宿主 App**（终端/编辑器）开权限。macOS 26 每次切换开关都要求触控 ID/密码认证，
  只能由用户本人完成（不要绕过）。授权完成前不要继续尝试操作。
- 只有辅助功能权限也能用 **AX 语义通道 + 键鼠注入**（无需截屏的纯语义任务可继续）；
  截屏/OCR 必须等录屏授权。

## 1. 核心循环（两段式）

### 语义路径（首选）：AX 树定位 → 语义动作 → 属性验证

```
apps → ax state <app>（大页面/找可交互元素首选）或 ax tree <app>（完整层次）
     → 看编号句柄 [i]（state）或路径句柄（w0.1.3 = 窗口0.子节点链；m0.* = 菜单栏）
     → ax press / ax set / ax select / ax focus（编号和路径都收）
     → ax attr 读回验证（只读、不覆盖快照）→ 下一步
```

全程**后台安全**：不动真实鼠标、不抢用户焦点，用户可并行工作。能用语义路径绝不走坐标。

规则：

1. **一步一验证**：每个 `ax set/press` 后用 `ax attr`（值/状态）或 `screenshot` 确认生效。
2. **句柄新鲜度**：路径句柄与编号句柄都只对「最近一次 `ax tree`/`ax find`/`ax state`」有效
   （快照是单份的，任一 dump 命令整份覆盖）。UI 变化后旧句柄 fail-closed 返回
   `{"ok":false,"code":"stale"}`——**重新 dump 拿新句柄**，不要对 stale 重试同一动作。
   编号句柄另带 pos/size 复核：动态网页 DOM 重排会显式 stale，防止静默按错同名元素。
   验证读值用 `ax attr`（只读，不覆盖快照，不失效句柄）。
3. **菜单项 AXPress 必须先激活应用**（实测约束）：`ax press` 对菜单项在应用后台时
   回执 ok 但**不执行**。先 `open "App名"` 激活，再按菜单；普通窗口内按钮不受此限。
4. `ax press` 前看清节点的 `title`/`role` 再按，防止误按（安全边界见 §4）。
5. 键盘输入四选一：`ax set`（语义直写，最稳）> `ax focus` + `type --paste`（长文本/中文首选）
   > `key/type --app`（后台直投进程队列，不抢焦点——**自绘 app 忽略合成鼠标时的兜底**，
   实测 QQ音乐 后台空格暂停有效）> `type` 逐字符（短文本）。`type/key`（不带 `--app`）落在
   **前台应用**的焦点元素上，输入前确认前台正确（`frontmost`）。输出里的 `channel` 字段
   标明派发通道（pid=后台 / foreground=前台）。注意 `--app` 的边界：菜单快捷键
   （cmd+s 类 key equivalent）后台**不触发**（需激活），后台有效的是文本输入与
   app 自己处理的 keyDown（空格/方向键等）。
6. NSDocument 应用（TextEdit/Preview 等）关闭**有名字的**修改文档会**自动保存静默关窗**；
   但关闭**未命名**文档会弹「你要保留此新文稿吗？」panel（删除/取消/保存，实测 macOS 26），
   且 panel 挂着时「文件>关闭」菜单是 disabled（press 回执 ok 但 no-op）——先处理 panel
   再走菜单。需要明确「不保存」时先验证文件内容再决定。
7. **媒体/播放状态验证 oracle（纯文本，无需截屏）**：Chrome 窗口标题「正在播放音频」后缀；
   播放菜单项标题翻转（播放↔暂停）；播放控制栏元素 `desc`（如 `歌曲名：X - 歌手名：Y`、
   播放/暂停播放）；进度时间文本。
8. **后台唤起用 `open --background`，成败判定读 `frontmost_after`**（不许只看 `mode`/
   退出码）：`--background` 是结束状态保证，结束后前台必须仍是 `frontmost_before`。
   已运行 app 加 `--background` 会按已运行跳过（`mode:"already_running"`，不发 open
   事件、不造窗）；要重开其窗口加 `--force`（`mode:"forced_reopen"`）。app 自激活抢
   前台时（QQ音乐 类实测 0.5~4s 落地）契约如实报 `foreground_stolen_by`，恢复已自动
   执行（inline + 12s 单发看门狗兜迟到的重放）；恢复都失败才 `ok:false
   code:"foreground_stolen"`。

### 无视觉模型的边界（纯文本模型必读）

语义通道全程是文本（`apps` → `ax tree`/`ax find` → `ax press`/`ax set` → `ax attr` 验证），
不读图即可完成大部分任务。额外两条规则：

1. **禁止盲猜坐标**：AX 树里找不到、`ocr` 也不出文字的目标，按 §5 失败规则停止并报告。
   没有视觉就无法确认点击结果，对猜测坐标点击/输入的误伤风险不可接受。
2. **验证只用文本证据**：`ax attr` 读值、窗口标题、文件内容、剪贴板、`ocr` 文本。
   `screenshot` + `ocr` 可以当"义眼"用（OCR 返回的像素坐标可直接 `click`），
   但仅限带文字的目标；图标按钮、自绘画布、纯视觉状态（弹窗/加载/勾选态）
   无法确认时，如实报告而不是猜。

### 视觉兜底：AX 够不到才用（自绘界面、图片按钮、AX 树缺失）

```
screenshot → 看图定位（不确定就 region 放大或 ocr）→ 执行一个动作
→ wait 300~800ms → screenshot 验证 → 下一步
```

规则与旧版一致：一步一验证；看不见的不存在（先滚动/ocr/放大再下结论）；先
`windows` + `screenshot` 摸清环境；<20px 小目标先 region 放大再取坐标；
点击没反应先查弹窗，不要重复点击同一坐标。

## 2. 工具面

### 环境 / 观察

| 命令 | 作用 | 关键参数 |
|---|---|---|
| `doctor` | 分项权限自检（accessibility: ok/stale/denied；screen-recording: ok/denied/unknown——stale 检不出，见 §0） | — |
| `apps` | 运行中 GUI 应用（pid/bundle_id/name/frontmost/hidden） | — |
| `frontmost` | 当前前台应用 | — |
| `windows` | 可见窗口（window_id/owner/边界） | `--pid N` 按进程过滤 |
| `displays` | 显示器列表 | — |
| `screenshot` | 截屏（PNG + 坐标元数据） | `--display N` `--out P` `--region-px X Y W H`（加 `--pts` 按屏幕点） `--window <id>` |
| `ocr` | 本地 Vision OCR | `--lang zh-Hans,en-US` |
| `open "App名"` | 启动/激活应用 | `--bundle-id com.apple.X`、`--url "scheme://…"`、`--settle 2000`；`--background`：后台唤起，结束后前台必须仍是 `frontmost_before`；`--force`：重开已运行实例的窗口（对已运行 app 加 `--background` 时必须一起用，否则按已运行跳过） |
| `clipboard get/set` | 剪贴板 | — |
| `position` / `wait MS` | 指针位置 / 等待 | — |

### AX 语义族（后台安全）

| 命令 | 作用 | 备注 |
|---|---|---|
| `ax tree <pid\|bundle-id\|应用名>` | dump AX 树（写句柄快照） | `--depth 10 --max 300 --role button,textfield --all` |
| `ax state <app>` | **原生式优先级元素表**（编号句柄、大页面友好） | 交互控件排前+`flags`（pressable/editable/disabled/focused）；`--text/--role` 过滤、`--top N`、`--timeout 秒`；编号直接喂 press/set/attr |
| `ax find <app> --text "提交"` | 按文本/标题/角色深度搜索 | 同时匹配 `title`/`desc`(AXDescription)/`help`/值；`--title`、`--role button`、`--first` |
| `ax press <path>` | AXPress（语义点击） | 菜单项需先激活应用 |
| `ax action <path> --name AXOpen` | 执行元素声明的动作 | 用节点 `acts` 里列出的名字 |
| `ax set <path> --value "…"` | 语义直写 AXValue | 文本域/组合框；滑块填数字 |
| `ax attr <path> [--name AXValue]` | 读属性（状态验证） | 无 `--name` 列出全部属性 |
| `ax select <path> --range 0 5` | 设置选区 | kAXSelectedTextRange |
| `ax focus <path>` | 聚焦元素（type 前置） | 应用未激活时先 `open` |

`ax tree/find/state` 的节点含 `pos`/`size`（**屏幕点坐标**）→ `click --mode pts` 可直接消费；
错误码统一 fail-closed：`stale / no-action / not-found / permission / unsupported`，
`hint` 字段说明恢复动作。

### 键盘 / 指针（视觉兜底与通用输入）

| 命令 | 作用 | 关键参数 |
|---|---|---|
| `click X Y` | 单/双/三击 | `--count 2`、`--button right`、`--down`/`--up`（按住/释放拆分） |
| `move X Y` / `drag X1 Y1 X2 Y2` | 悬停 / 拖拽 | `--duration 600` |
| `scroll X Y` | 滚动 | `--down 5` / `--up` / `--left` / `--right` |
| `type "文本"` | 输入 Unicode（支持中文） | `--paste`（剪贴板中转，长文本首选，粘贴后自动恢复原剪贴板）、`--press-enter`、`--app <pid\|bundle-id\|名>`（后台直投） |
| `key cmd+c` | 组合键 | `--hold 800`（按住）、`--app`（后台直投）；`holdkey w --duration 2000` 按住单键 |

## 3. 坐标契约（视觉路径）

- **`click/move/drag/scroll` 的 X Y 默认指「最后一张截图里的像素坐标」**——cu 依据
  screenshot 写入的元数据（scale/显示器原点）自动换算成屏幕点坐标。**不要自己除以 2。**
- `--region-px` 裁剪与 `--window` 窗口截图**也会更新坐标元数据**（原点平移到裁剪区）：
  在裁剪图/窗口图上看到的像素坐标可以直接 `click`，无需换算。
- 备用模式：`--mode norm`（0–1000）、`--mode pts`（屏幕点，`ax tree` 的 pos/size 用这个）。
- 截图后屏幕变了就重新截图；跨屏操作先对目标屏 `screenshot --display N`。

## 4. 安全边界（照抄 Codex Computer Use 的克制原则）

- **破坏性动作先确认**：删除文件、发送消息、提交表单、支付、退出登录等，先向用户复述
  将要发生的事并等确认。**AX 动作同样适用**：`ax press` 前确认元素 title/role 语义，
  防止误按「删除」「发送」类按钮。
- **不碰**：终端类应用（Terminal/iTerm）、本技能自身运行环境、系统安全/隐私弹窗
  （不要替用户点 Allow）。
- 不在截图/AX 树里读取并回传密码/密钥等敏感内容；涉及凭据的输入让用户自己完成。
- **后台键入先确认**：`key/type --app` 直接向目标进程注入键盘事件，用户视线之外也会生效。
  发送前用 `apps` 确认目标 app 与其状态；**绝不向终端类应用派发**；内容有发送/删除等
  外向语义时先向用户复述并确认。
- 任务范围限定在用户指定的应用/流程内；用户随时可接管鼠标键盘，每次动作前意识到屏幕已变。
- `wait` 是合法动作：不要用连续点击/重试代替等待。

## 5. 完成与失败状态

- 任务完成：最后一屏截图 + ocr/窗口列表或 `ax attr` 读值作为证据，向用户报告结果。
- 无法完成（目标不存在、权限缺失、反复失败 3 次、持续 stale）：停止动作，报告已尝试
  的步骤、当前屏幕/AX 状态、失败原因。

## 6. 排错

详见 `references/troubleshooting.md`。高频项：截屏报错=无录屏权限；AX 树空/缺节点=
应用未暴露 AX（Chromium/Electron 会自动设 `AXManualAccessibility`，个别 app 拒绝 AX
返回 `unsupported`）；菜单 `ax press` 无效=应用未激活；`code:"stale"`=重新 `ax tree`；
坐标偏移=截图后屏幕已变化。

## 7. 自测

```bash
.venv/bin/python tests/test_coords.py     # 坐标/键码单测（无权限要求）
.venv/bin/python scripts/e2e_ax.py        # AX 闭环 e2e（仅需辅助功能权限）
open -a Terminal scripts/run-e2e.sh       # 视觉闭环 e2e（需录屏+辅助功能，Terminal 宿主；
                                          # 含 screenshot --region-px 断言：PNG 实际像素 == 请求尺寸、scale 复位）
```
