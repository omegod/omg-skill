# Design System Tokens 规范

设计系统 Token 是保证界面高端、协调、一致的核心基石。智能体在输出任何 CSS 代码时，应优先定义并使用以下变量体系。

---

## 1. 色彩体系 (Color Palettes)

### A. 赛博暗黑 / AI 科技风 (Cyber Dark / AI Tech) - 推荐首选
适合：AI 工具、Copilot、数据分析平台、现代开发者工具。

```css
:root {
  /* 背景层次 (Background Hierarchy) */
  --bg-app: #090d16;          /* 全局主背景 */
  --bg-surface: #111827;      /* 基础卡片背景 */
  --bg-surface-glass: rgba(17, 24, 39, 0.7); /* 毛玻璃卡片背景 */
  --bg-element: #1f2937;      /* 输入框/次级容器背景 */
  --bg-element-hover: #374151;/* 悬浮背景 */

  /* 品牌色与主题渐变 (Brand & Accent Gradients) */
  --brand-primary: #6366f1;   /* Indigo 600 */
  --brand-secondary: #a855f7; /* Purple 500 */
  --brand-cyan: #06b6d4;      /* Cyan 500 */
  
  --gradient-brand: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
  --gradient-glow: radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.15), transparent 70%);

  /* 边框与微光 (Border & Subtle Strokes) */
  --border-subtle: rgba(255, 255, 255, 0.08);
  --border-medium: rgba(255, 255, 255, 0.16);
  --border-glow: rgba(99, 102, 241, 0.4);

  /* 文本对比度 (Typography Contrast) */
  --text-title: #f9fafb;      /* 标题/高亮 (98% 亮度) */
  --text-body: #d1d5db;       /* 正文/内容 (85% 亮度) */
  --text-muted: #9ca3af;      /* 次要文本 (65% 亮度) */
  --text-disabled: #4b5563;   /* 禁用文本 (40% 亮度) */
}
```

### B. 极致简洁 SaaS / B端中性风 (Clean & Professional Light/Dark)
适合：企业级 SaaS 平台、CRM、管理后台、文档中心。

```css
:root {
  /* Light Mode */
  --bg-app-light: #f8fafc;
  --bg-surface-light: #ffffff;
  --border-light: #e2e8f0;
  --text-title-light: #0f172a;
  --text-body-light: #334155;
  --brand-light: #2563eb;     /* Blue 600 */

  /* Dark Mode */
  --bg-app-dark: #0f172a;
  --bg-surface-dark: #1e293b;
  --border-dark: #334155;
  --text-title-dark: #f8fafc;
  --text-body-dark: #cbd5e1;
  --brand-dark: #3b82f6;      /* Blue 500 */
}
```

---

## 2. 排版阶梯与字体 (Typography Scale)

推荐字体导入（Google Fonts）：
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

CSS 排版变量定义：
```css
:root {
  /* 字体族 */
  --font-heading: 'Plus Jakarta Sans', -apple-system, sans-serif;
  --font-body: 'Inter', -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  /* 字号与行高 (Size & Line Height) */
  --font-xs: 0.75rem;    /* 12px / line-height: 1.5 */
  --font-sm: 0.875rem;   /* 14px / line-height: 1.5 */
  --font-base: 1rem;     /* 16px / line-height: 1.6 */
  --font-lg: 1.125rem;   /* 18px / line-height: 1.5 */
  --font-xl: 1.25rem;    /* 20px / line-height: 1.4 */
  --font-2xl: 1.5rem;    /* 24px / line-height: 1.3 */
  --font-3xl: 1.875rem;  /* 30px / line-height: 1.2 */
  --font-4xl: 2.25rem;   /* 36px / line-height: 1.1 */
  --font-5xl: 3rem;      /* 48px / line-height: 1.1 */

  /* 字重 (Font Weight) */
  --weight-regular: 400;
  --weight-medium: 500;
  --weight-semibold: 600;
  --weight-bold: 700;
}
```

---

## 3. 空间与网格间距 (Spacing & Layout Grid)

严格遵循 **8px / 4px 网格基准**，避免随意给定未对齐的数值（如 `17px`, `23px`）：

```css
:root {
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;
}
```

---

## 4. 光影、深度与圆角 (Shadows, Depth & Radius)

### 圆角系统 (Border Radius)
```css
:root {
  --radius-sm: 6px;    /* 标签、微型按钮 */
  --radius-md: 10px;   /* 标准按钮、输入框 */
  --radius-lg: 16px;   /* 卡片、对话框 */
  --radius-xl: 24px;   /* 大模块、模态框主框架 */
  --radius-full: 9999px; /* 丸状标签/头像 */
}
```

### 多层立体阴影 (Layered Elevation Shadows)
避免使用粗暴的单层黑色阴影，采用分层自然弥散阴影：

```css
:root {
  /* 低浮层 (Cards, Dropdowns) */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05),
              0 2px 4px 0 rgba(0, 0, 0, 0.05);

  /* 中浮层 (Hovered Cards, Popovers) */
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1),
              0 10px 15px -3px rgba(0, 0, 0, 0.1);

  /* 高浮层 (Modals, Floating Panels) */
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.3),
              0 8px 10px -6px rgba(0, 0, 0, 0.2);

  /* 霓虹辉光 (Glows for Interactive Actions) */
  --shadow-glow-brand: 0 0 20px -3px rgba(99, 102, 241, 0.5);
  --shadow-glow-cyan: 0 0 20px -3px rgba(6, 182, 212, 0.5);
}
```
