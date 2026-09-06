# 前端高品质组件设计指南 (Component Design Guide)

智能体在生成界面组件代码时，可直接套用或借鉴以下精美且可用的 CSS/HTML 模式。

---

## 1. 现代化毛玻璃卡片 (Glassmorphism Card)

```html
<div class="card-glass">
  <div class="card-header">
    <div class="card-icon">
      <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
    </div>
    <span class="badge badge-indigo">Active Feature</span>
  </div>
  <h3 class="card-title">Real-time Analytics</h3>
  <p class="card-desc">Process millions of events with sub-millisecond latency and dynamic aggregation.</p>
</div>
```

```css
.card-glass {
  background: rgba(17, 24, 39, 0.65);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 24px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1),
              0 10px 25px -5px rgba(0, 0, 0, 0.3);
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.card-glass:hover {
  border-color: rgba(99, 102, 241, 0.4);
  transform: translateY(-4px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15),
              0 20px 35px -10px rgba(99, 102, 241, 0.15);
}
.card-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
  display: flex;
  align-items: center;
  justify-content: center;
}
.card-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: #f9fafb;
  margin: 16px 0 8px 0;
}
.card-desc {
  font-size: 0.875rem;
  color: #9ca3af;
  line-height: 1.5;
  margin: 0;
}
```

---

## 2. 高亮渐变与微动效按钮 (Gradient Primary & Subtle Buttons)

```html
<!-- 主品牌渐变按钮 -->
<button class="btn btn-primary">
  <span>Launch Copilot</span>
  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
</button>

<!-- 次级幽灵/透明边框按钮 -->
<button class="btn btn-secondary">
  Documentation
</button>
```

```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 20px;
  font-size: 0.875rem;
  font-weight: 600;
  border-radius: 10px;
  cursor: pointer;
  outline: none;
  border: none;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

/* Primary Gradient Button */
.btn-primary {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #ffffff;
  box-shadow: 0 4px 14px 0 rgba(99, 102, 241, 0.39);
}
.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px 0 rgba(99, 102, 241, 0.55);
  filter: brightness(1.08);
}
.btn-primary:active {
  transform: translateY(0) scale(0.98);
}

/* Secondary Glass Button */
.btn-secondary {
  background: rgba(255, 255, 255, 0.05);
  color: #d1d5db;
  border: 1px solid rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(8px);
}
.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
  border-color: rgba(255, 255, 255, 0.25);
  transform: translateY(-1px);
}
```

---

## 3. 极精致数据统计指标 (KPI Metric Component)

```html
<div class="kpi-card">
  <div class="kpi-label">Total Revenue</div>
  <div class="kpi-value-row">
    <span class="kpi-value">$124,592</span>
    <span class="kpi-trend trend-up">
      <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
      +14.2%
    </span>
  </div>
  <div class="kpi-subtext">vs. previous month</div>
</div>
```

```css
.kpi-card {
  background: rgba(17, 24, 39, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  padding: 20px;
}
.kpi-label {
  font-size: 0.875rem;
  color: #9ca3af;
  font-weight: 500;
}
.kpi-value-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-top: 10px;
}
.kpi-value {
  font-size: 1.875rem;
  font-weight: 700;
  color: #f9fafb;
  letter-spacing: -0.02em;
}
.kpi-trend {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 9999px;
}
.trend-up {
  background: rgba(34, 197, 94, 0.12);
  color: #4ade80;
  border: 1px solid rgba(34, 197, 94, 0.2);
}
.kpi-subtext {
  font-size: 0.75rem;
  color: #6b7280;
  margin-top: 8px;
}
```

---

## 4. 高保真搜索与 AI 输入框 (Search & AI Prompt Input)

```html
<div class="ai-input-wrapper">
  <input type="text" class="ai-input" placeholder="Ask AI to generate, analyze, or build..." />
  <button class="ai-send-btn">
    <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M12 5l7 7-7 7"/></svg>
  </button>
</div>
```

```css
.ai-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
}
.ai-input {
  width: 100%;
  padding: 14px 48px 14px 18px;
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  color: #f8fafc;
  font-size: 0.9375rem;
  outline: none;
  transition: all 0.25s ease;
}
.ai-input:focus {
  border-color: #818cf8;
  box-shadow: 0 0 0 3px rgba(129, 140, 248, 0.2),
              0 0 20px rgba(129, 140, 248, 0.15);
  background: rgba(15, 23, 42, 0.95);
}
.ai-send-btn {
  position: absolute;
  right: 8px;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: white;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
}
.ai-send-btn:hover {
  transform: scale(1.05);
}
```

---

## 5. 优雅现代表格 (Modern Data Table)

```html
<div class="table-container">
  <table class="table-custom">
    <thead>
      <tr>
        <th>User</th>
        <th>Role</th>
        <th>Status</th>
        <th style="text-align: right;">Actions</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="user-cell">
          <div class="avatar">CH</div>
          <div>
            <div class="name">Caicheng Hu</div>
            <div class="email">hu@example.com</div>
          </div>
        </td>
        <td><span class="role-tag">Admin</span></td>
        <td><span class="badge badge-success">Online</span></td>
        <td style="text-align: right;">
          <button class="action-btn">Edit</button>
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

```css
.table-container {
  width: 100%;
  overflow-x: auto;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(17, 24, 39, 0.5);
}
.table-custom {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.875rem;
}
.table-custom th {
  background: rgba(255, 255, 255, 0.03);
  padding: 14px 18px;
  color: #9ca3af;
  font-weight: 600;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.table-custom td {
  padding: 14px 18px;
  color: #d1d5db;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}
.table-custom tbody tr:hover {
  background: rgba(255, 255, 255, 0.03);
}
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #ec4899);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.75rem;
}
.user-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user-cell .name { font-weight: 600; color: #f9fafb; }
.user-cell .email { font-size: 0.75rem; color: #6b7280; }
```
