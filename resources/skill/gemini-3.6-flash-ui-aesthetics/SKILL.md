---
name: gemini-3.6-flash-ui-aesthetics
description: 智能体 UI 美学与高级界面设计指南。用于指导 AI 智能体生成具备极高视觉水准、优雅色调、丰富质感、和谐层次与动效的现代 Web/App 界面。覆盖 SaaS、AI Copilot、数据看板、B端控制台、高端 C端 Landing Page 等多种业务场景。风格来源：Gemini 3.6 Flash，惊艳、质感、暗色科技感。
---

# UI Design Aesthetic Skill | 智能体 UI 美学与高级界面设计指南

本 Skill 专为 AI 智能体（Agent）设计，旨在全面提升智能体生成前端 UI 界面时的**视觉审美、美学质感、交互体验与设计一致性**。避免产生同质化、土气、粗糙或未经雕琢的“程序员审美”界面。

---

## 核心设计哲学 (Core Philosophy)

1. **惊艳的第一印象 (Wow Factor at First Sight)**
   - 界面绝不仅是“功能可用”，必须在视觉上给人高端、精致、和谐的科技感与设计感。
2. **严谨的系统化 Token (Design System First)**
   - 拒绝随意硬编码颜色和间距。建立固定的 HSL/RGB 变量体系（色彩、阶梯字号、4/8px 网格间距、微阴影、圆角）。
3. **富有生命力的质感 (Tactile & Dynamic Depth)**
   - 巧用**渐变边框 (Gradient Border)**、**毛玻璃 (Glassmorphism)**、**环境次级高光 (Ambient Glow)** 与 **深度阴影 (Layered Shadows)**。
4. **流畅精致的微交互 (Micro-Interactions)**
   - 按钮 hover 升起、卡片光泽流动、点击缩放反馈（`active: scale(0.98)`）、过渡动效（`cubic-bezier`）。

---

## 快速生成 5 步工作流 (Agent Step-by-Step Workflow)

当你（智能体）受命设计或生成前端 UI 界面时，必须严格执行以下步骤：

```
[1. 确定业务场景] ──> [2. 选择美学风格与色盘] ──> [3. 建立 CSS Design Tokens] ──> [4. 组装组件与布局] ──> [5. 注入动效与细节打磨]
```

### Step 1: 确定业务场景与视觉定位
根据用户需求匹配场景类型（详见 `references/03-business-scenarios.md`）：
- **AI Native / Future Tech**: 赛博暗黑、深色毛玻璃、霓虹发光粒子、极细微光线边框。
- **Modern SaaS / Enterprise**: 简洁克制、高对比度阅读体验、深浅灰阶、莫兰迪/科技蓝点缀。
- **B端数据看板 (Dashboard)**: 多维度数据网格、富有节奏的高亮卡片、色彩语义化的图表。
- **高端 Landing Page**: 大气留白、巨型渐变字体、光效背景、流线型 C端动效。

### Step 2: 注入规范的 CSS Design Tokens
在 CSS 头部声明标准变量体系（详见 `references/01-design-system-tokens.md`）：
```css
:root {
  /* 色阶与配色 */
  --bg-primary: #090d16;
  --bg-surface: rgba(22, 29, 45, 0.7);
  --border-subtle: rgba(255, 255, 255, 0.08);
  --brand-primary: #6366f1;
  --brand-gradient: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
  
  /* 字体与排版 */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  --text-main: #f8fafc;
  --text-muted: #94a3b8;

  /* 阴影与深度 */
  --shadow-sm: 0 2px 4px rgba(0,0,0,0.1);
  --shadow-glow: 0 0 25px rgba(99, 102, 241, 0.25);
  
  /* 动效缓动 */
  --transition-smooth: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
```

### Step 3: 应用高级感核心美学法则
遵从 `references/02-visual-aesthetics-rules.md` 中的 10 大美学法则：
1. **不要使用纯黑 (#000) 或纯白 (#fff)**，使用带有冷暖色调沉淀的暗色（如 `#090d16`）与月白（如 `#f8fafc`）。
2. **多层级边框与内阴影**：结合 `border: 1px solid rgba(255,255,255,0.1)` 和 `box-shadow: inset 0 1px 0 rgba(255,255,255,0.15)` 制造立体精致切面。
3. **字号与字重阶梯对比**：标题用 `font-weight: 700` + 紧密字间距 `letter-spacing: -0.02em`，次要文字用 `font-weight: 400` + 透明度。
4. **容器卡片感**：使用 `backdrop-filter: blur(12px)` + 半透明背景，提升视效品质。

### Step 4: 组装高质感组件
从 `references/04-component-design-guide.md` 获取标准组件模板（卡片、按钮、表格、输入框、模态框等）。

### Step 5: 自检防错清单
生成代码前进行自我审查：
- [ ] 是否引入了现代美观字体（如 Google Fonts Inter / Plus Jakarta Sans / Outfit）？
- [ ] 按钮与可点击元素是否具备 Hover、Active、Focus 三态微交互？
- [ ] 行高是否充裕（正文行高建议 1.5 - 1.6，标题建议 1.2 - 1.3）？
- [ ] 容器内边距（Padding）是否足够呼吸感（卡片 Padding 至少 20px-24px）？

---

## Skill 参考文档索引 (Reference Map)

请阅读以下子文件以获取特定维度的深度指引：
- 🎨 [01-design-system-tokens.md](references/01-design-system-tokens.md) — 完整设计 Token 字典与配色方案表
- ✨ [02-visual-aesthetics-rules.md](references/02-visual-aesthetics-rules.md) — 让界面提升档次的 10 大高级感细节与光影法则
- 🏬 [03-business-scenarios.md](references/03-business-scenarios.md) — 6 大典型业务场景（SaaS, AI Copilot, Dashboard, B端, C端）设计指南
- 🧩 [04-component-design-guide.md](references/04-component-design-guide.md) — 高品质前端 UI 组件 CSS/HTML 代码标准
- 🖥️ [modern-dashboard-demo.html](examples/modern-dashboard-demo.html) — 完整的高级暗黑风 Dashboard HTML 示范代码
