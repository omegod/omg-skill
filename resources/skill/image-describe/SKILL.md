---
name: image-describe
description: 当需要读取图片/图像/截图/照片/图表/扫描件内容、但当前模型不支持多模态（无法接收图像）时使用。调用本机 `omg img-describe` 命令，将本地图片路径或 HTTP(S) URL 转换为结构化 Markdown 文本描述，作为图片内容供模型继续处理。触发词：图片、图像、截图、照片、这张图、看下这个图、describe this image、screenshot、photo、diagram。
---

## 何时使用
- 仅在当前模型明确不支持图片识别时使用
- 用户给出图片、截图、照片、图表、扫描件或图片路径/URL，要求读取或解释其内容。
- 当前模型不支持图像输入（纯文本模型）。
- 用户提供图片的本地路径或 `http(s)` 链接。

## 前置条件

- 本机已安装 `omg`：执行 `omg --version` 能正常返回版本号。
- 已配置支持图像输入的模型：执行 `omg config get` 查看，必要时用
  `omg config set model <视觉模型ID>` 指定（如 `sensenova-6.7-flash-lite`）。
- 确认子命令可用：`omg img-describe --help`。

## 步骤

1. 确定图片位置：
   - 优先用绝对路径；相对路径先转为绝对路径（可用 `ls` 确认文件存在）。
   - 也支持 URL：`https://example.com/img.png`。

2. 运行命令并捕获 stdout：

   ```bash
   omg img-describe "<路径或URL>"
   ```

   常用参数：

   - `--prompt "关注点"` — 追加描述重点（如"识别界面上所有按钮和文案"）。
   - `--ascii` — 附加本地字符画轮廓（不额外消耗 API token）。
   - `--language en` — 切换描述语言（默认中文 `zh`）。
   - `--detail high|low|auto` — 视觉细节等级（默认 `high`）。

3. 命令 stdout 输出的 Markdown 即图片内容的文字版，作为该图片的上下文体。
   回答用户问题时，区分输出中标注的"事实 / 合理推断 / 不确定信息"：
   不要把推断当成事实复述。描述过长时按需读关键章节（核心概述、主体与细节、
   文字与符号、合理推断）。
