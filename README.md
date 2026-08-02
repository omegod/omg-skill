# OMG Skills

一套为 AI 智能体（Agent / Claude Code / Cursor 等）设计的 **UI 美学技能库**，旨在消除 AI 生成界面"程序员审美"的通病，让智能体产出具备高级感、克制感与一致性的现代 Web/App 界面。

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

将对应技能目录放入你的 Agent 技能目录：

| 工具 | 技能目录 |
|------|----------|
| Claude Code | `~/.claude/skills/<skill-name>/` |
| Cursor | `.cursor/skills/<skill-name>/` |
| opencode | `.opencode/skills/<skill-name>/` |

以 `opus5-ui-aesthetics` 为例：

```bash
cp -r ui-desgin/opus5-ui-aesthetics ~/.claude/skills/opus5-ui-aesthetics
```

### 3. 使用

技能通过 `SKILL.md` 中的 `description` 触发。当你让 Agent 生成或美化界面时，它会自动加载对应技能并遵循其中的设计规范。

---

## 技能清单

| 技能 | 风格取向 | 特点 |
|------|----------|------|
| [opus5-ui-aesthetics](ui-desgin/opus5-ui-aesthetics/SKILL.md) | 克制、极简、系统化 | 九条铁律 + 四轴人格决策流程 + 可量化的硬数值（对比度/间距/圆角）+ `palette.py` 配色脚本，强调"做减法后仍然清晰" |
| [gemini-ui-design-aesthetic](ui-desgin/gemini-ui-design-aesthetic/SKILL.md) | 惊艳、质感、暗色科技感 | 核心设计哲学 + 5 步工作流 + Design Tokens 体系 + 组件模板库，覆盖 SaaS / AI Copilot / Dashboard / Landing Page 等场景 |

### 对比与选择

- 想要 **系统化、可量化、克制高级** 的界面 → 选 `opus5-ui-aesthetics`
- 想要 **视觉惊艳、质感丰富、暗色科技风** 的界面 → 选 `gemini-ui-design-aesthetic`
- 不确定时，两者可同时安装，由场景自动触发

---

## 目录结构

```
omg-skill/
├── README.md
└── ui-desgin/
    ├── gemini-ui-design-aesthetic/      # Gemini 风格：惊艳质感派
    │   ├── SKILL.md                     # 技能主文件（含 description 触发词）
    │   └── references/                  # 深度参考文档
    │       ├── 01-design-system-tokens.md    # 设计 Token 字典
    │       ├── 02-visual-aesthetics-rules.md # 10 大美学法则
    │       ├── 03-business-scenarios.md      # 6 大业务场景指南
    │       └── 04-component-design-guide.md  # 组件设计标准
    └── opus5-ui-aesthetics/             # Opus 风格：系统克制派
        ├── SKILL.md                     # 技能主文件（含 description 触发词）
        ├── references/                  # 深度参考文档
        │   ├── personality.md           # 8 类场景人格预设与 token 表
        │   ├── color.md                 # 配色与色阶
        │   ├── tokens.md                # 间距/字阶/圆角/阴影/动效
        │   ├── layout.md                # 栅格与页面构成
        │   ├── components.md            # 组件尺寸与状态
        │   └── antipatterns.md          # AI 味清单与替代方案
        └── scripts/
            └── palette.py               # 配色生成与对比度校验脚本
```

---

## 自定义技能

新建技能时遵循标准结构：

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
