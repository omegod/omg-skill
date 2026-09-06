# macOS Computer Use 实现方案调研（面向纯视觉模型）

> 调研时间：2026-09-05。目标：为「仅支持视觉的模型」（只能看截图、输出文本/坐标，无法读取 Accessibility 树）设计一个 macOS 上的 computer use 技能。主要参照 **Codex Computer Use**（OpenAI Codex 的 `@Computer` 功能）的实现方向。

---

## 1. Codex Computer Use 是怎么做的（本次的主要参照方向）

来源：[ChatGPT Learn — Computer Use](https://learn.chatgpt.com/docs/computer-use)、[Codex for almost everything](https://openai.com/index/codex-for-almost-everything/)。

- **形态**：Codex Desktop 内置的 Computer Use 插件（提示词里 `@Computer` 或 `@应用名` 唤起），让模型"看到并操作 macOS/Windows 的图形界面"，用于 CLI/结构化工具覆盖不了的场景（GUI 应用设置、无插件的软件、复现 UI bug）。
- **感知**：模型可以看到屏幕内容、截屏、读取窗口/菜单/键盘输入/剪贴板状态；可见内容（网页、截图、打开的文件）成为模型上下文。
- **执行**：在 **macOS 上通过 Accessibility（AX）执行点击/输入/导航**，配合截屏验证；Windows 上则是移动真实指针并抢占前台。
- **权限模型**：需要 **屏幕录制**（看屏幕）+ **辅助功能**（点击/输入）两个 TCC 权限；**按 App 审批**——首次操作某 App 时弹出"Allow Codex to use Calculator?"，可"Always allow"，记录在 `config.toml` 的 `[computer_use.windows] always_allowed_app_ids`（macOS 同类机制在设置里）。
- **边界（设计得很克制，值得照抄）**：
  - 不允许自动化**终端类 App 和 ChatGPT 自己**（防止绕过安全策略）；
  - 不能以管理员身份认证、不能替用户批准系统安全/隐私弹窗；
  - 对涉及账号、支付、凭据的操作要求用户在场逐步确认；
  - 任务建议限定在单个 App/流程内，用户随时可接管/取消。
- **模型选择**：官方建议视觉密集任务用 GPT-6 Astra；底层是 OpenAI Responses API 的 `computer_use` 工具（前身 `computer-use-preview` 已弃用）。

**OpenAI `computer_use` 工具的动作契约**（[API 文档](https://developers.openai.com/api/docs/guides/tools-computer-use)）：模型返回 `computer_call`（动作数组），harness 执行后回传 `computer_call_output`（新截图 + `acknowledged_safety_checks`）。动作集：`click / double_click / triple_click / drag / scroll / type / keypress / wait / screenshot`；坐标基于**声明的逻辑显示尺寸**（如 1024×768），harness 负责缩放到真实屏幕。

---

## 2. 主流框架对比

详细调研结论（2026-09 现状）：

| 方案 | Grounding 来源 | 坐标格式 | 执行机制 | macOS 支持 | 现状 |
|---|---|---|---|---|---|
| **UI-TARS 1.5/2（字节）** | 模型原生 | `click(point=[x,y])` 动作串；7B 用 1920×1080 空间、72B 用 1000×1000 归一化 | 宿主解析动作串 → pyautogui 类操作 | 桌面 App 支持 | 1.5-7B：OSWorld 42.5、ScreenSpot-v2 94.2；2.0 仅 API |
| **UI-TARS-desktop** | UI-TARS 原生 | 点坐标 | 本地/远程 computer operator + MCP | 原生 App | ~38.8k stars，活跃 |
| **OmniParser v2（微软）** | 外挂解析器 | YOLO 图标检测 + Florence 图标描述 + OCR → 元素 bbox + SoM 序号，VLM 选序号 | OmniTool（Windows VM），执行 BYO | 解析器跨平台，执行需自建 | 0.6s/帧(A100)；v3 权重 MIT；维护模式 |
| **Anthropic Computer Use** | 模型原生 | 固定 1024×768（或同比例）模型空间，harness 换算 | 参考实现跑在 Docker/X11 + xdotool；macOS 需自移植（CGEvent + screencapture） | 参考实现仅 Linux | Sonnet 4.5 OSWorld 61.4%；`computer_toolset_20260801` 已去 beta |
| **OpenAI CUA** | 模型原生 | 声明的逻辑显示尺寸 | `computer_call`/BYO 环境 | BYO | preview 弃用，并入 GPT-5.4+ `computer_use` 工具 |
| **Agent-S3（Simular）** | 混合：规划 VLM + 专用 grounding 模型 | grounding 模型像素空间 | pyautogui `exec` | 支持 | OSWorld 72.6%（bBoN），达人类水平 |
| **trycua/cua** | BYO 模型（可选 OmniParser） | 取决于模型 | 宿主后台驱动（不抢焦点）+ 沙盒 API + Virtualization.framework macOS VM | **macOS 最完善** | ~22.2k stars，MIT，活跃 |
| **Self-Operating Computer** | GPT-4V 裸像素 / SoM / OCR 元素表 | 混合 | pyautogui | 支持 | 已停更（2025-09），仅作模式参考 |
| **Qwen2.5/3-VL** | 模型原生（**绝对像素**坐标，动态分辨率） | bbox/点，JSON | BYO + 官方 cookbook | BYO | Qwen3-VL-32B ScreenSpot 95.8，开源最强 grounding |
| **GLM-4.5V/4.6V（智谱）** | 模型原生 | bbox **0–1000 归一化** + `<|begin_of_box|>` token | BYO | BYO | 106B MoE 活跃；GLM-PC 已商用 |
| **Gemini Computer Use** | 模型原生 | **0–1000 归一化** | 客户端 handler（参考实现 Playwright） | 浏览器优先，桌面 BYO | preview；Gemini 3 ScreenSpot-Pro 72.7 |

**关键结论：**

1. **Grounding 两条路线**：(a) 用 GUI 特训过的 VLM 原生出坐标（UI-TARS、Qwen3-VL、GLM-V，ScreenSpot 94+）；(b) 通用 VLM + 外挂解析器（OmniParser v2，任意 VLM 可用，延迟 ~0.6s/帧）。本技能面向的模型若是通用 VLM，坐标精度是短板 → 需要**缩小目标的技巧**（zoom 再点）+ **动作后截图验证**兜底。
2. **坐标归一化没有行业标准**：绝对像素（Qwen）、固定模型空间（Anthropic 1024×768 / OpenAI 声明尺寸）、0–1000 归一化（Gemini/GLM）。**技能必须显式声明一个规范坐标空间并负责换算**——这是 harness 的职责，不能指望模型算对。
3. **macOS 没有现成官方执行器**：Anthropic 参考实现是 X11/xdotool，OpenAI/Gemini 全 BYO。开源里 trycua/cua 是 macOS 最完整的骨架（宿主驱动 + VM 沙盒）；Codex 官方做法是 AX 执行 + 截屏观察。
4. **沙盒化是共识**（Anthropic Docker、Google VM、cua VM），但个人技能场景下"宿主直跑 + 权限门控 + 克制的动作边界"（Codex 模式）更实用。

---

## 3. macOS 平台技术栈（本机已验证）

本机环境：macOS 26.6.2（Tahoe）/ Apple M2 / 内置屏 2560×1664 物理像素 = **1280×832 逻辑点**（Retina 2x）。

### 3.1 截屏

- **`screencapture`（系统自带，首选）**：`screencapture -x out.png`（`-x` 静音；`-C` 含鼠标指针；`-D <N>` 指定显示器；`-l <windowid>` 截指定窗口；`-R x,y,w,h` 截区域）。速度快、零依赖。
- **TCC 屏幕录制权限**：无权限时 **macOS 26 硬报错**（"could not create image from display"，本机实测）；旧版 macOS 的表现是**不报错但只有壁纸、没有窗口内容**（尺寸正常、2x 像素）——两种行为都必须在运行前用 `CGPreflightScreenCaptureAccess()` 预检拦截。授权后需**完全重启宿主 App** 才生效；`tccutil reset ScreenCapture` 可重置。
- **TCC 权限归属宿主 App**（本机实测）：从终端/编辑器里跑脚本时，权限挂在宿主 App 上而非脚本自己；ZCode 的 Bash 子进程树默认无授权，`AXIsProcessTrusted()`/`CGPreflightScreenCaptureAccess()` 均返回 false，CGEvent 被静默丢弃（`position` 不变化可实证）。端到端测试需要在一个已授权的宿主里跑（如授权后的 Terminal：`open -a Terminal scripts/run-e2e.sh`）。
- ScreenCaptureKit / CGWindowListCreateImage（pyobjc）：适合高频截屏或按窗口截，v1 用不上。

### 3.2 坐标系（核心坑位）

- macOS 窗口坐标与 CGEvent 用**逻辑点**（point），Retina 屏上 `screencapture` 输出 **2x 物理像素**。模型看的是像素图、算出的是像素坐标 → **必须除以 scale（像素宽/点宽）再送给 CGEvent**，多显示器还要加显示器原点（副屏原点可为负）。
- pyautogui / cliclick / CGEvent 全部期望**逻辑点**。
- 技能设计：`screenshot` 时把 `{像素尺寸, 点尺寸, scale, 显示器原点}` 写入 sidecar 元数据；`click` 等命令**默认接受截图像素坐标**，自动换算 —— 模型永远只工作在"我最后看到的那张图"的坐标系里，不用自己算。

### 3.3 输入注入

- **CGEventPost（pyobjc Quartz，kCGHIDEventTap）**：mouse move/click/double/drag/scroll、键盘事件全覆盖；经验要点：move 与 click 之间加小延迟、事件发布到正确位置、Unicode 输入用 `CGEventKeyboardSetUnicodeString`（绕过 key code 映射表，中文可输）。pyobjc 无需编译，`pip install pyobjc-framework-Quartz` 即可。
- **cliclick**（brew）：等价的零 Python 依赖方案，`c:100,200` / `t:"text"` / `kp:cmd+c`，内部也是 CGEvent，坐标用逻辑点。备选。
- **osascript + System Events**：`keystroke` / `key code` / AX 元素 `click`（可点菜单栏项等 AX 元素，CGEvent 做不到）；同样需要辅助功能权限；`tell app X to activate` 做 App 激活。作为补充手段保留。
- **Secure Input**：某些密码框开启后会吞键盘事件，`ioreg -l -w 0 | grep SecureInput` 可检测，SKILL 里要写进排错。
- 权限归属：从终端跑脚本时，TCC 权限挂在**宿主 App**（终端/ZCode）上，不是脚本自己。

### 3.4 观察与增强原语

- **窗口列表**：`CGWindowListCopyWindowInfo` 拿窗口标题/边界/pid（其他 App 的窗口名需要屏幕录制权限）。
- **前台 App**：`NSWorkspace.frontmostApplication`。
- **OCR**：Vision `VNRecognizeTextRequest`（pyobjc-framework-Vision），本地、快、准，可给纯视觉模型做"动作后文本验证"（本机实测：中英混排可识别，**语言列表顺序影响结果，中文场景需 `zh-Hans` 在前**；pyobjc 的 `confidence`/`string` 可能暴露为方法需兼容）。
- **AX 作为增强（非模型输入）**：AXUIElement 可枚举元素角色/位置，用于点击校验或精确点击；Electron/Web 部分支持、游戏不支持。v1 不依赖，作为后续增强。

---

## 4. 纯视觉 Agent 的循环设计

来自 Anthropic / OpenAI / UI-TARS 的公开实践：

1. **观察 → 思考 → 一个动作 → 再观察**：每步动作后必须截图验证，不要盲发多步。
2. **动作空间要克制且自包含**：screenshot、click（左/右/双/三击）、type、key（组合键）、scroll、drag、move、wait，外加 `wait`（等动画/加载）与明确的**完成/失败状态**（防止死循环）。Anthropic 的 `hold_key`/`zoom`、OpenAI 的 `keypress` 都是同构的。
3. **坐标精度**：通用 VLM 对小目标（菜单项、关闭按钮）容易偏 10-20px。缓解：① 点之前可用局部放大（zoom crop）；② 动作后验证、失败就修正；③ 有外挂解析器（OmniParser/OCR）时用元素表代替裸坐标。
4. **历史管理**：旧截图及时丢弃（token 大户），只保留文字轨迹 + 最近 1-2 张截图。
5. **常见失败模式**（OSWorld/ScreenSpot 结论）：小点击目标、下拉菜单、拖拽、往指定输入框打字、时序（弹窗没等出现就点）。技能里要写成显式检查项。
6. **安全门控**（照抄 Codex 的边界）：不碰终端/自身、破坏性动作先确认、任务限定单 App、随时可停。

---

## 5. 选型与实现方案（结论）

**技术路线：Codex Computer Use 式的"宿主直跑 harness"** —— 一个本机 `cu` CLI（screencapture 截屏 + pyobjc Quartz 注入事件）+ SKILL.md 定义的截图-动作-验证循环，模型侧零坐标换算。

```
resources/skill/computer-use/
├── SKILL.md            # 技能主文件：触发条件、核心循环、坐标契约、安全边界、排错
├── RESEARCH.md         # 本调研报告
├── references/
│   └── troubleshooting.md  # 权限/Secure Input/常见失败对照表
└── scripts/
    ├── cu.sh           # 入口（自动创建 .venv 并装 pyobjc）
    └── cu.py           # 执行器：doctor/displays/screenshot/click/move/drag/scroll/type/key/wait/position/clipboard/ocr
```

- **感知**：`screencapture -x`，输出 PNG + JSON 元数据（像素尺寸/scale/原点），sidecar 供后续 click 自动换算。
- **执行**：pyobjc Quartz CGEvent（move/click/drag/scroll/type/key），Unicode 打字、组合键映射表；激活 App 用 `osascript`。
- **坐标契约**：默认收"最后一张截图的像素坐标"；`--pts`（逻辑点）、`--norm`（0–1000）备选。
- **权限**：`cu doctor` 预检屏幕录制（`CGPreflightScreenCaptureAccess`）+ 辅助功能（`AXIsProcessTrusted`），缺失时给出系统设置路径，不产出"壁纸图"假成功。
- **安全**：SKILL.md 层面落实 Codex 的边界（不碰终端与自身、破坏性操作先确认、每步验证）。
- **验证**：OCR（Vision）+ 截图回看；测试以"截图可见内容 → 点坐标 → 打字 → 再截图确认"的端到端闭环为准。

## 参考资料

- Codex Computer Use: https://learn.chatgpt.com/docs/computer-use · https://openai.com/index/codex-for-almost-everything/
- OpenAI computer_use 工具: https://developers.openai.com/api/docs/guides/tools-computer-use
- Anthropic computer-use-demo: https://github.com/anthropics/anthropic-quickstarts
- UI-TARS: https://github.com/bytedance/UI-TARS · https://github.com/bytedance/UI-TARS-desktop
- OmniParser: https://github.com/microsoft/OmniParser
- trycua/cua: https://github.com/trycua/cua
- Agent-S: https://github.com/simular-ai/Agent-S · GUI-Actor: https://github.com/microsoft/GUI-Actor
- Self-Operating Computer: https://github.com/OthersideAI/self-operating-computer
- Qwen2.5-VL: https://qwenlm.github.io/blog/qwen2.5-vl/ · GLM-4.5V: https://huggingface.co/zai-org/GLM-4.5V
- Gemini computer use: https://ai.google.dev/gemini-api/docs/computer-use
- ScreenSpot 排行: https://gui-agent.github.io/grounding-leaderboard/
- cliclick: https://github.com/BlueM/cliclick · peekaboo: https://github.com/steipete/peekaboo
- 屏幕录制权限行为（无权限=纯壁纸）: https://apple.stackexchange.com/questions/384230 · https://community.adobe.com/questions/652
