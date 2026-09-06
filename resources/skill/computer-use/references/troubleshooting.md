# 排错对照表（macOS Computer Use）

## 截屏

| 现象 | 原因 | 处理 |
|---|---|---|
| `screencapture failed: could not create image from display` | 宿主 App 无"屏幕录制"权限（macOS 26 硬报错） | System Settings → 隐私与安全性 → 屏幕录制，勾选宿主 App，**完全重启宿主 App** |
| 截图只有壁纸、没有窗口内容 | 同上，但为旧版 macOS 的表现（不报错） | 同上；运行 `cu doctor` 预检 |
| 截图内容与实际屏幕不符 | 屏幕变化后未重新截图 / 授权后未重启宿主 | 重新 `screenshot`；重启宿主 |
| 分辨率与预期不符 | Retina/缩放显示：像素尺寸 = 点尺寸 × scale（本机 scale≈1.4971，非整数） | 正常现象；cu 的坐标契约已自动处理 |

## AX 语义通道（cu 2.0）

| 现象 | 原因 | 处理 |
|---|---|---|
| `ax tree` 返回空 nodes / note「未暴露可读的 AX 树」 | 应用无窗口，或未生成 AX 树 | 先确认 `windows --pid` 有窗口；Chromium/Electron 会自动设 `AXManualAccessibility` 后重试（约 0.5s）；个别 Electron 仍需在应用设置里开辅助功能 |
| `ax tree/find/press` 返回 `code:"unsupported"`（AXError -25211 APIDisabled） | 目标 App 拒绝 AX 客户端（自保护类应用） | 换视觉路径（screenshot + click）操作该应用 |
| `ax press/set` 返回 `code:"stale"` | UI 已变化或窗口数变化导致句柄失效（fail-closed，符合预期） | 重新 `ax tree` 取新句柄；**不要对 stale 重试同一动作** |
| `ax press` 返回 `code:"not-found"`：路径不在最近一次 tree 输出里 | 快照被另一次 tree/find 覆盖（快照是单份的） | 对目标应用重新 `ax tree` 再取句柄 |
| `ax press` 返回 `code:"no-action"` | 元素未声明 AXPress（窗口类只声明 AXRaise） | 用 `ax attr <path>` 查看声明的动作，改用 `ax action --name` 或换目标 |
| **菜单项 `ax press` 回执 ok 但没有任何效果** | 菜单项 AXPress 只对**激活态**应用生效（macOS 26 实测） | 先 `open "App名"` 激活，再按菜单；窗口内按钮不受此限 |
| `ax set` 返回 `unsupported`「AXValue 不可直接写」 | 目标元素值不可写（按钮/静态文本） | 改用 `ax focus` + `type --paste`，或对按钮 `ax press` |
| `ax focus` 后 `type` 无反应 | 应用未激活，前台是别的应用 | `type/key` 落在**前台应用**焦点上；先 `open` 激活目标应用，`ax focus` 再输入；或改用 `type/key --app`（后台直投，见下节） |
| **`ax tree` 满是无标签 `AXUnknown`**（如 QQ音乐） | 自绘 app 把可读标签放在 **AXDescription**，早期版本只读 title/value | 升级到 cu 2.1+：节点带 `desc` 字段，`ax find --text` 同时匹配 desc（播放控制栏/歌曲名：… 都能搜到） |
| **元素点击回执 ok 但没有任何效果**（如 QQ音乐 播放按钮） | 自绘视图的 AX bounds 与视觉位置错位，或 app 过滤合成鼠标事件（原生工具同样中招） | 改用**键盘**：`key --app <pid> space`（播放/暂停类快捷键）；或截屏后 `click` 视觉坐标；不要对同一坐标重复点击 |
| `type/key --app` 对某 app 无效 | 个别 app 做 isActive 检查（pid 直投被忽略；SkyLight 合成焦点档暂缓实现） | `open "App名"` 激活后用前台 `key/type`；输出 `channel` 字段确认实际通道 |
| `key --app cmd+s` 等菜单快捷键后台不生效（TextEdit 实测：选区纹丝不动） | 菜单快捷键由**菜单系统**派发（key equivalent），需要激活态；app 自己处理的 keyDown（空格/方向键/home/文本输入）后台才有效 | 快捷键类操作先 `open` 激活；后台通道用于文本输入与 app 内建按键（如 QQ音乐 空格播放/暂停） |
| `ax tree` 输出带 `retried: N` | WebArea 空壳自动重试：Chromium 惰性建树，页面刚加载时 WebArea 先出现、内容后填充 | 正常现象；若重试 2 次后仍为空壳，等页面加载完重新 dump |
| **大页面 `ax find` 找不到深层元素**（B 站级 DOM 1000+ 节点，默认 300 节点/深度 10 走不到）；`--all` 又慢到超时 | find 是串行全树 DFS，每节点 8+ 次 XPC | 改用 **`ax state`**（cu 2.2）：交互优先 + 时间预算（默认 10s，实测 B 站 0.6s 走完 1900 节点），编号句柄直接 `ax press 42` |
| **编号句柄 `ax press 42` 返回 not-found**「编号不在编号表里」 | 快照是单份的：之后跑过 tree/find/state 都会整份覆盖编号表 | 对目标应用重新 `ax state`；验证态用 `ax attr`（只读、不写快照） |
| **编号动作返回 stale「编号指向的元素已移动/隐藏」** | 快照里存了 pos/size，动作解析时复核——动态网页 DOM 几秒内重排，路径会漂到别的同名节点，复核把"静默按错"拦成显式 stale（实测 B 站两连按第二次即触发） | 重新 `ax state` 取新编号；**state → 动作要一气呵成** |
| **Chromium 页面内容读不到**（WebArea 空壳、`retried` 耗尽仍 0 元素；激活/刷新/切标签都无效） | 页面是在后台/被遮挡时加载的，渲染进程没建 web AX 树 | 激活后**重新导航**（`open --url` 直达最有效）；或让任一 AT 客户端查询一次（原生 helper/VoiceOver），Chromium 会全局点亮 AX |
| **视频网站控制栏「播放/暂停」AXPress 回执 ok 但不切换**（B 站实测） | 播放中控制栏自动隐藏（opacity/pointer-events），AXPress 被 DOM 接受但播放器不理 | **暂停态**（栏可见）AXPress 有效；播放中切换用空格 `key space`（焦点需在页面上）；AXPress 顺带能把焦点带回播放器，之后再空格就有效 |
| **同名按钮一大堆**（B 站暂停态展开合辑列表：100+ 个「播放/暂停」分集按钮） | 列表项播放按钮与控制栏按钮同名 | `ax state` 输出带 pos/size：按位置过滤（控制栏在播放器左下）；`--text` 缩小范围；按错分集按钮会**在新窗口打开那一集** |
| `ax attr w0`（窗口标题）在媒体页频繁 stale | 窗口标题含「正在播放音频」后缀，随播放态变化，签名校验必失效 | 这类"验证用读"直接重新 `ax tree`/`ax state`（重写快照无 stale）；编号句柄要在验证后重新获取 |
| TextEdit/Preview 等关闭修改过的文档没有保存对话框 | NSDocument 自动保存模型：关闭=静默存盘+关窗 | 属正常行为；需要「不保存」时先 `ax attr` 读值确认内容再操作 |
| `doctor` 显示 accessibility `stale` | 已授权但宿主 App 未重启，AX 读写被拒 | 完全退出并重启宿主 App |

## 截屏（cu 2.0 变更）

| 现象 | 原因 | 处理 |
|---|---|---|
| `screenshot --window <id>` 报 window not on screen | 窗口已关闭/最小化或 window_id 过期 | 重新 `windows`（可加 `--pid`）取当前 window_id |
| region/窗口截图上的坐标点击位置不对 | 检查 meta 是否与该截图对应（region/window 截图**已更新** meta 原点） | 重新截图后再取坐标；`cu screenshot` 返回值里有当前 origin/scale |

## 点击 / 键盘

| 现象 | 原因 | 处理 |
|---|---|---|
| 点击、按键无任何效果（position 不变） | 宿主 App 无"辅助功能"权限，CGEvent 被静默丢弃 | System Settings → 隐私与安全性 → 辅助功能，勾选宿主 App，重启宿主 |
| `key`/`type` 部分应用无反应 | 目标 App 开启了 **Secure Input**（密码框） | `ioreg -l -w 0 \| grep -i secureinput` 检测；换非密码框目标或让用户手动输入 |
| 输入了但进了别的窗口 | 动作与激活之间有竞态，焦点落在别的 App | 每次输入前重新截图确认前台与焦点；用 `open "App"` 激活后 wait 800ms+ |
| 双击/三击识别成多次单击 | 系统双击间隔内事件间隔过大 | cu 内部已按 clickState 递增构造，若仍异常改用 `--count 2` 单命令 |
| 中文打不出 | unicode 事件路径异常 | `cu type` 走 CGEventKeyboardSetUnicodeString，理论支持全部 Unicode；仍有问题改用剪贴板粘贴（`clipboard set` + `key cmd+v`） |

## OCR（Vision）

| 现象 | 原因 | 处理 |
|---|---|---|
| 中文识别缺失/置信度低 | 语言列表顺序影响结果 | `--lang zh-Hans,en-US`（中文优先）；英文界面用默认 `en-US,zh-Hans` |
| 小字/模糊字识别差 | 截图整体缩放后文字太小 | `screenshot --region-px` 裁剪局部后再 OCR |
| OCR 坐标和 click 对不上 | OCR bbox 单位是"最后一张截图的像素" | 直接把 bbox 中心喂给 `click`（默认就是截图像素系），不要换算 |

## 坐标

| 现象 | 原因 | 处理 |
|---|---|---|
| 点偏了 | 截图之后屏幕发生变化（滚动/弹窗/窗口移动） | 重新 `screenshot` 再取坐标；SKILL 的"一步一验证"就是为了防这个 |
| 多显示器点错屏 | 副屏原点为负/不同 scale | 每次操作前对目标屏 `screenshot --display N`，让元数据与目标屏一致 |
| 模型看到的是被缩小过的图 | 宿主把截图下采样后再喂给模型 | 用 `--mode norm`（0–1000）按缩放后图的比例报坐标，或重新截原图 |

## 权限授予（一次性，需要用户本人在场）

1. System Settings → 隐私与安全性 → **辅助功能**：开启宿主 App。
2. System Settings → 隐私与安全性 → **录屏与系统录音**：开启宿主 App。
3. **macOS 26 实测：每次切换开关都会弹"使用触控ID或输入密码允许此操作"认证框**，无法由
   Agent 代为完成（这是设计如此的安全门，不要尝试绕过）；首次触发时列表里会预注册目标 App。
4. **完全退出并重启宿主 App**（TCC 授权在重启后生效；只关窗口无效）。
5. 重跑 `cu doctor` 应为 `ok: true`。
6. 重置授权（开发调试用）：`tccutil reset ScreenCapture` / `tccutil reset Accessibility`。

> TCC 权限归属宿主 App 而非脚本：从已授权的 Terminal 里跑 `run-e2e.sh`，其子进程（cu）继承信任。
> 未授权宿主里跑会得到：截屏硬报错（macOS 26）/ 纯壁纸（旧版），鼠标键盘事件被静默丢弃。
