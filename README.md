# OMG Skills

一套为 AI 智能体（Agent / Claude Code / Cursor / opencode 等）设计的 **技能库**，全部技能位于 `resources/skill/`（一个技能一个目录），目前包含：

- **UI 美学技能** —— 消除 AI 生成界面"程序员审美"的通病，让智能体产出具备高级感、克制感与一致性的现代 Web/App 界面（`claude-opus-5-ui-aesthetics`、`gemini-3.6-flash-ui-aesthetics`）。
- **工具类技能** —— 让不支持多模态的模型也能读取图片等非文本输入（`computer-use`、`image-describe`）。

---

## 目录

- [快速开始](#快速开始)
- [技能清单](#技能清单)
- [目录结构](#目录结构)
- [自定义技能](#自定义技能)

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/omegod/omg-skill.git
```

### 2. 安装技能

推荐用仓库自带的安装 CLI（Node.js ≥ 18，零依赖，无需 `npm install`）：

```bash
cd omg-skill
node src/index.mjs                 # 交互式：选 skill → 选 agent → 选安装范围
```

交互流程：`空格` 勾选 / `a` 全选，方向键移动，`回车` 确认。安装范围二选一：

- **用户级**：装到 `~/.claude/skills/` 等全局目录，所有项目可用
- **项目级**：装到当前项目 `.claude/skills/` 等，仅该项目可用

也可以用参数一步到位（`--help` 查看全部选项）：

```bash
node src/index.mjs list                                                       # 查看仓库内技能与支持的 agent
node src/index.mjs install -a claude-code,codex -s computer-use,image-describe -g -y
node src/index.mjs install -a cursor -s image-describe -l --dir ~/my-project  # 项目级安装
node src/index.mjs install --dry-run -a claude-code -s computer-use -g        # 只看计划不写入
node src/index.mjs uninstall -a claude-code -s computer-use -g -y             # 卸载
```

支持的目标 agent：`claude-code`、`codex`、`zcode`、`opencode`、`cursor`、`agents`（`~/.agents/skills/` 跨工具共享目录）。

也可以手动 `cp -r`，各 Agent 的技能目录：

| 工具 | 技能目录 |
|------|----------|
| Claude Code | `~/.claude/skills/<skill-name>/` |
| Codex CLI | `~/.codex/skills/<skill-name>/` |
| ZCode | `~/.zcode/skills/<skill-name>/` |
| opencode | `~/.config/opencode/skills/<skill-name>/` |
| Cursor | `.cursor/skills/<skill-name>/` |

以 `claude-opus-5-ui-aesthetics` 为例：

```bash
cp -r resources/skill/claude-opus-5-ui-aesthetics ~/.claude/skills/claude-opus-5-ui-aesthetics
```

### 3. 使用

技能通过 `SKILL.md` 中的 `description` 触发。当你让 Agent 生成或美化界面时，它会自动加载对应技能并遵循其中的设计规范；当需要读取图片而当前模型不支持多模态时，`image-describe` 会自动触发，并在图片到达时运行本机 `omg img-describe` 把图片转成文本描述。该技能依赖已安装的 [omg CLI](https://github.com/omegod/omg-cli) 与已配置的视觉模型（`omg config set model <视觉模型ID>`）。

---

## 技能清单

### UI 美学

| 技能 | 风格取向 | 特点 |
|------|----------|------|
| [claude-opus-5-ui-aesthetics](resources/skill/claude-opus-5-ui-aesthetics/SKILL.md) | 克制、极简、系统化 | 九条铁律 + 四轴人格决策流程 + 可量化的硬数值（对比度/间距/圆角）+ `palette.py` 配色脚本，强调"做减法后仍然清晰" |
| [gemini-3.6-flash-ui-aesthetics](resources/skill/gemini-3.6-flash-ui-aesthetics/SKILL.md) | 惊艳、质感、暗色科技感 | 核心设计哲学 + 5 步工作流 + Design Tokens 体系 + 组件模板库，覆盖 SaaS / AI Copilot / Dashboard / Landing Page 等场景 |

### 工具类

| 技能 | 用途 |
|------|------|
| [image-describe](resources/skill/image-describe/SKILL.md) | 图片 → 详尽文本描述。当模型不支持多模态时，调用本机 `omg img-describe` 将图片路径或 URL 转为 Markdown 描述，作为图片内容供模型继续处理 |
| [computer-use](resources/skill/computer-use/SKILL.md) | macOS 桌面自动化（Codex Computer Use 方向）。纯视觉模型通过「截屏 → 坐标 → 执行 → 再截屏验证」循环操作 GUI 应用：点击、输入、滚动、拖拽、OCR 验证。依赖 `scripts/cu.sh`（首次运行自动创建 venv 安装 pyobjc）与"屏幕录制 + 辅助功能"两项系统权限，详见 [调研报告](resources/skill/computer-use/RESEARCH.md) |

### 对比与选择

- 想做 **系统化、可量化、克制高级** 的界面 → 选 `claude-opus-5-ui-aesthetics`（风格来源：Claude Opus 5）
- 想做 **视觉惊艳、质感丰富、暗色科技风** 的界面 → 选 `gemini-3.6-flash-ui-aesthetics`（风格来源：Gemini 3.6 Flash）
- **UI 类** 不确定时，两者可同时安装，由场景自动触发
- **图片理解**：模型不支持多模态、需要读取图片/截图/图表时 → 使用 `image-describe`（依赖已配置视觉模型的本机 [omg](https://github.com/omegod/omg-cli) 命令）

---

## 目录结构

```
omg-skill/
├── README.md
├── package.json                     # 安装 CLI 的包信息（零依赖，bin: omg-skill）
├── docs/                            # 版本文档（spec 及其历史版本，见 docs/README.md）
│   ├── README.md                    # 索引与版本管理约定
│   ├── browser-use-spec.md          # bu 0.1 规格（浏览器自动化，对标 ZCode browser-use，草案）
│   └── computer-use-spec.md         # cu 2.1 规格 + 2.2 增补（已实现，归档）
├── resources/
│   └── skill/                       # 全部技能（一个技能一个目录，安装 CLI 自动发现）
│       ├── gemini-3.6-flash-ui-aesthetics/      # UI 美学：Gemini 3.6 Flash 惊艳质感派
│       │   ├── SKILL.md                         # 技能主文件（含 description 触发词）
│       │   └── references/                      # 深度参考文档
│       │           ├── 01-design-system-tokens.md    # 设计 Token 字典
│       │           ├── 02-visual-aesthetics-rules.md # 10 大美学法则
│       │           ├── 03-business-scenarios.md      # 6 大业务场景指南
│       │           └── 04-component-design-guide.md  # 组件设计标准
│       ├── claude-opus-5-ui-aesthetics/         # UI 美学：Claude Opus 5 系统克制派
│       │   ├── SKILL.md                         # 技能主文件（含 description 触发词）
│       │   ├── references/                      # 深度参考文档
│       │   │       ├── personality.md           # 8 类场景人格预设与 token 表
│       │   │       ├── color.md                 # 配色与色阶
│       │   │       ├── tokens.md                # 间距/字阶/圆角/阴影/动效
│       │   │       ├── layout.md                # 栅格与页面构成
│       │   │       ├── components.md            # 组件尺寸与状态
│       │   │       └── antipatterns.md          # AI 味清单与替代方案
│       │   └── scripts/
│       │           └── palette.py               # 配色生成与对比度校验脚本
│       ├── image-describe/                      # 工具类：图片 → 文本描述（非多模态模型读取图片）
│       │   └── SKILL.md                         # 技能主文件（含调用步骤与排错指引）
│       └── computer-use/                        # 工具类：macOS 桌面自动化（纯视觉模型）
│           ├── SKILL.md                         # 技能主文件（核心循环/坐标契约/安全边界）
│           ├── RESEARCH.md                      # 实现方案调研报告
│           ├── references/
│           │       └── troubleshooting.md       # 权限/坐标/OCR 排错对照表
│           └── scripts/
│               ├── cu.sh                        # 入口（自动引导 venv + pyobjc）
│               ├── cu.py                        # 执行器：截屏/点击/键盘/滚动/OCR/窗口
│               ├── e2e_test.py                  # 自驱动端到端测试（OCR 闭环断言）
│               └── run-e2e.sh                   # 在已授权宿主（如 Terminal）中跑 e2e
└── src/                             # 安装 CLI（Node.js ≥18，零依赖）
    ├── index.mjs                    # 入口：命令路由 + 参数解析 + 交互流
    ├── agents.mjs                   # 各 agent 的 skills 目录注册表
    ├── skills.mjs                   # 仓库技能扫描（resources/skill/）+ frontmatter 解析
    ├── prompts.mjs                  # 零依赖交互原语（多选/单选/确认/输入）
    └── install.mjs                  # 安装/卸载执行引擎
```

---

## 自定义技能

在 `resources/skill/<name>/` 下新建技能目录（安装 CLI 会自动发现），遵循标准结构：

```
my-skill/
├── SKILL.md        # YAML frontmatter：name + description（触发词），正文为工作流
└── references/     # 按需加载的深度文档，避免主文件过大
```

`SKILL.md` frontmatter 示例：

```yaml
---
name: my-skill
description: 触发词与适用场景说明，Agent 依据此 description 自动加载
---
```

---

## License

MIT
