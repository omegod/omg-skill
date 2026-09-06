# Token 取值表

## 间距

基准 4px。**只允许这些值**：

```
0  2  4  8  12  16  24  32  48  64  96  128
```

出现 5/6/7/10/13/15/18/20/25/30 = 未经设计。20 和 40 是唯一可选的例外（部分体系用 4/8/12/16/20/24/32/40/48）——选定一套后不得混用。

密度倍率（来自人格分）：

| 密度 | 倍率 | 组件内 padding | 组间距 | 区块间距 |
|---|---|---|---|---|
| 1 疏朗 | 1.5× | 24–32 | 48 | 96–128 |
| 2 | 1.25× | 20–24 | 32 | 64–96 |
| 3 通用 | 1.0× | 16 | 24 | 48–64 |
| 4 | 0.85× | 12 | 16 | 32–48 |
| 5 紧凑 | 0.75× | 8–12 | 12 | 24–32 |

**分组规则**：外边距 > 组间距 > 组内距，每级 ≥1.5×。典型：`32 / 16 / 8`。
标签与其输入框的距离，必须明显小于该字段与下一字段的距离——这是表单看起来专业与否的分水岭。

## 字号

比例（ratio）由人格决定：

| 场景 | body | ratio | 说明 |
|---|---|---|---|
| 工具/后台/数据 | 13–14 | 1.125–1.2 | 小步进，塞得下 |
| 通用产品 | 15–16 | 1.2–1.25 | 默认 |
| 阅读/内容 | 17–18 | 1.25–1.333 | 舒适 |
| 营销/落地页 | 16–17 | 1.25 + display 跳档 | 标题可直接跳到 48–72 |

典型 1.25 阶梯（body 16）：
```
xs 12 · sm 14 · base 16 · lg 20 · xl 24 · 2xl 30 · 3xl 38 · 4xl 48 · 5xl 60
```
单页取用 ≤5 档。

**行高**：
```
正文 1.5–1.65 · 小字 1.45 · 标题(20–30) 1.25 · 大标题(30–48) 1.15 · 超大(>48) 1.05
```
经验式：`lh ≈ 1.75 − 0.012 × 字号px`，夹在 [1.05, 1.75]。

**字距 letter-spacing**：
```
≥48px:  −0.03em
30–48:  −0.025em
20–30:  −0.015em
16–20:  −0.005em
14–16:   0
≤12:    +0.01em
全大写:  +0.06em ~ +0.1em（必须加，否则挤成一团）
```

**字重**：常规 400 / 中 500 / 半粗 600。**慎用 700+**——粗体是廉价感来源之一，除非人格重量 ≥4。正文与标题的区分优先靠字号和颜色，其次才是字重。

字体栈（无品牌字体时）：
```css
font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto,
             "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif;
/* 数字对齐 */ font-variant-numeric: tabular-nums;
```
中文场景务必带 `PingFang SC` / `Microsoft YaHei`，否则中文回退到宋体，观感直接崩。

## 圆角

| 档 | 值 | 适用 |
|---|---|---|
| sharp | 0 / 2 / 4 | 奢侈品、专业工具、数据密集 |
| default | 4 / 8 / 12 | 通用 |
| soft | 8 / 12 / 16 | 消费类 |
| round | 12 / 16 / 24 | 儿童、生活服务 |

- **嵌套公式**：`内圆角 = 外圆角 − 间距`。外 12 内边距 4 → 内 8。直接内外同值会看出"套壳"。
- 胶囊圆角（999px）只给 tag / avatar / 开关，不给按钮和卡片——全胶囊化是 AI 味。
- 单页 ≤3 种圆角。

## 阴影

| 级 | 用途 | 值 |
|---|---|---|
| 0 | 平面元素 | `none`（用边框或背景色差区分） |
| 1 | 卡片、输入框 | `0 1px 2px hsl(var(--sc)/.06), 0 1px 3px hsl(var(--sc)/.05)` |
| 2 | 下拉、popover | `0 2px 4px hsl(var(--sc)/.06), 0 8px 16px hsl(var(--sc)/.07)` |
| 3 | 弹窗、抽屉 | `0 4px 8px hsl(var(--sc)/.07), 0 20px 40px hsl(var(--sc)/.10)` |

`--sc` = shadow color = 主色相深色版（见 color.md）。永远双层。透明度别超 0.12，超过就是"塑料感"。

**深色模式阴影几乎无效**，改用表面亮度分层：每抬升一级 L +0.035，并加 1px 描边。

## 动效

| 类型 | 时长 | 缓动 |
|---|---|---|
| 颜色/透明度（hover、focus） | 120–150ms | `ease-out` |
| 小位移、开关 | 150–180ms | `cubic-bezier(.4,0,.2,1)` |
| 下拉、tooltip、气泡 | 200–260ms | 入 `cubic-bezier(0,0,.2,1)` / 出 `cubic-bezier(.4,0,1,1)` |
| 抽屉、弹窗、页面转场 | 280–400ms | `cubic-bezier(.32,.72,0,1)` |

- 入场 ease-**out**（快起慢收），出场 ease-**in**，出场比入场快 20–30%。
- 位移距离 ≤ 元素自身尺寸的 30%，超过就晃眼。
- 弹性/回弹只给"确认成功"这类正反馈，不给常规过渡。
- 列表逐项入场：stagger 20–40ms，超过 6 项就别做了。
- **必须**尊重 `prefers-reduced-motion: reduce` → 关掉位移/缩放，保留透明度。

## CSS 变量骨架

```css
:root {
  /* 间距 */
  --sp-1:4px;  --sp-2:8px;  --sp-3:12px; --sp-4:16px;
  --sp-6:24px; --sp-8:32px; --sp-12:48px; --sp-16:64px;

  /* 圆角 */
  --r-sm:4px; --r-md:8px; --r-lg:12px; --r-full:999px;

  /* 表面（浅色） */
  --page:#f9fafd; --surface:#fff; --sunken:#f3f4f6;
  --border:#dcdee2; --border-strong:#c8cace;
  --text:#1e1f22; --text-2:#515256; --text-muted:#707275;

  /* 强调 */
  /* accent 白字实测 4.78:1 ✓AA。勿提亮：L>0.57 即失败 */
  --accent:#436ed1; --accent-hover:#3964c5; --accent-active:#3059ba;
  --accent-fg:#fff; --accent-subtle:#e1eafc;

  /* 阴影 */
  --sc:264 8% 22%;
  --sh-1:0 1px 2px hsl(var(--sc)/.06), 0 1px 3px hsl(var(--sc)/.05);
  --sh-2:0 2px 4px hsl(var(--sc)/.06), 0 8px 16px hsl(var(--sc)/.07);

  /* 动效 */
  --dur-fast:140ms; --dur:200ms; --dur-slow:320ms;
  --ease-out:cubic-bezier(0,0,.2,1);
}

[data-theme="dark"] {
  --page:#0f1013; --surface:#17191d; --sunken:#0b0c0e;
  --border:#2c2e32; --border-strong:#404247;
  --text:#eceef4; --text-2:#aeb1b6; --text-muted:#7b7d82;
  --accent:#759cef; --accent-fg:#0f1013; --accent-subtle:#1c2842;
}

@media (prefers-reduced-motion: reduce) {
  *,*::before,*::after { animation-duration:.01ms!important;
    transition-duration:.01ms!important; scroll-behavior:auto!important; }
}
```
