# 业务场景 UI 设计指南 (Business Scenarios UI Design Guide)

不同业务场景对视觉风格、色彩偏好和布局密度的要求截然不同。智能体需根据实际需求切换最佳设计方案。

---

## 场景 1：AI Native / Copilot 对话与智能化应用

### 特征与诉求
强调未来感、智能化、人机对话流畅度、极简浮动与微渐变。

### 设计关键点
1. **输入框（Prompt Input Area）**：
   - 悬浮毛玻璃胶囊形态或底栏固定。
   - 带有 Glowing Border（渐变聚焦边框）和发光发送图标。
   - 提供 Prompt Suggestions（快捷 Prompt 气泡）。
2. **对话流（Message Bubbles）**：
   - User 消息：浅透明紫/蓝底或右对齐渐变框 (`background: rgba(99, 102, 241, 0.15)`)。
   - AI / Assistant 消息：无背景框或极其微弱的暗色框，重点突出内容、代码块与 Markdown 格式。
   - AI 正在思考：打字机闪烁光标与流式打字动画、Thinking 折叠展开盒。
3. **色彩推荐**：深空蓝/黑 (`#080c14`) + 炫彩霓虹 accent (`#818cf8`, `#c084fc`, `#38bdf8`)。

---

## 场景 2：Modern SaaS 仪表盘与管理后台 (Dashboard & Admin Portal)

### 特征与诉求
信息密度适中、数据清晰可读、操作效率优先、长久看眼睛不易疲劳。

### 设计关键点
1. **三栏式标准布局**：
   - 左侧：Collapsible Sidebar（折叠式导航栏，带 Icon + Label + Badge）。
   - 顶栏：Breadcrumb + Global Search (Cmd+K 搜索框) + Notification + Profile 头像。
   - 内容区：KPI Cards (4列) + Main Chart (2/3 宽度) + Recent Activity Table (1/3 宽度)。
2. **卡片设计**：
   - 统一 Padding（20px ~ 24px）。
   - 卡片页眉：标题 + 筛选器/操作按钮下拉菜单。
3. **色彩推荐**：
   - 暗黑版：`#0f172a` 主背景 + `#1e293b` 卡片背景 + `#3b82f6` 品牌蓝。
   - 亮色版：`#f8fafc` 主背景 + `#ffffff` 卡片背景 + `#e2e8f0` 边框 + `#0f172a` 文字。

---

## 场景 3：数据可视化与实时监控看板 (Data Analytics & Command Center)

### 特征与诉求
高密度数据展示、实时图表、高对比度、大屏视觉震撼力。

### 设计关键点
1. **图表（Charts）配色**：
   - 统一调色盘，避免杂乱七彩色。推荐：翡翠绿 (`#10b981`)、电磁蓝 (`#3b82f6`)、紫罗兰 (`#8b5cf6`)、琥珀黄 (`#f59e0b`)。
   - 区域面积图（Area Chart）增加顶部到底部的渐变透明度（Gradient Fill）。
2. **数据指标 (Stat Widgets)**：
   - 特大号数字（32px - 40px `font-weight: 700`）。
   - 带有同差/环比指示器（上升绿箭头，下降红箭头 + 迷你 Sparkline 折线图）。
3. **色彩推荐**：极暗背景 (`#030712`) + 发光科技线图。

---

## 场景 4：高端 C端 Landing Page / 官网展示

### 特征与诉求
极具视觉冲击力、高留白、巨幅 Hero 区域、流畅滚动动效。

### 设计关键点
1. **Hero 区域**：
   - 巨幅标题（48px ~ 72px），关键字渐变高亮。
   - 双 CTA 按钮（主按钮：发光渐变胶囊；次按钮：毛玻璃边框按钮）。
   - 3D / 高精度的产品截帧模拟图（带浏览器外壳框或立体倾斜效果）。
2. **Feature Grid (特性网格)**：
   - 经典 Bento Box Grid（便当盒风格网格布局，交错大小卡片）。
   - 每个 Bento 卡片内置小动画或精美微缩图形。
3. **Social Proof (信任背书)**：
   - 品牌 Logo 墙（半透明灰度 Logo，Hover 恢复色彩）。
   - 用户评价卡片阵列。

---

## 场景 5：B端复杂表格与流程控制台 (Complex Enterprise Console)

### 特征与诉求
高密度、支持筛选排序、多状态批量操作、精准对齐。

### Design Checklist
1. 表格 Header：使用稍深的背景色或透明度，文字小写加粗，紧凑行高。
2. 单元格内边距：上下 12px~14px，左右 16px。
3. 状态 Badge：圆角 Status Pills（如 `Active`, `Pending`, `Failed`），搭配对应透明背景。
4. 行 Hover：加亮背景 `background: rgba(255, 255, 255, 0.03)`，末端显示快捷 Hover 工具栏。

---

## 场景 6：电商 / 消费级界面 (E-Commerce & Consumer Apps)

### 特征与诉求
图片为核心、唤起购买欲、高对比度价格显示、流畅加购体验。

### Design Checklist
1. 商品卡片：大比例精美图 + 悬浮快速收藏（Heart Icon）+ Hover 缩放动画 (`transform: scale(1.03)`).
2. 价格标签：现价大粗字（如 `#ef4444` 或 `#000`）+ 原价中划线灰字 (`#9ca3af`).
3. 评价星级：黄金色 SVG 星星 (`#fbbf24`).
