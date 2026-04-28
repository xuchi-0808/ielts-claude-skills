---
name: ielts-dashboard
description: |
  IELTS 学习数据可视化 Dashboard。生成本地 HTML 网页，展示写作趋势图、四科雷达图、错题热力图、同义替换统计、考试倒计时。
  触发方式：/ielts-dashboard、「Dashboard」「看数据」「打开数据面板」
metadata:
  version: Pro
---

# IELTS Dashboard — 学习数据可视化

你负责生成并打开本地的 IELTS 学习数据可视化面板。

**你的工作很简单：调用 CLI 生成 Dashboard HTML，然后打开它。**

---

## 执行流程

### Step 1：确保数据初始化

```bash
python3 ~/.claude/skills/shared/ielts_cli.py init
```

### Step 2：生成 Dashboard

```bash
python3 ~/.claude/skills/shared/ielts_cli.py dashboard
```

### Step 3：打开浏览器

```bash
open ~/.ielts/dashboard.html
```

### Step 4：告诉用户

```markdown
✅ Dashboard 已生成并打开！

📊 你在浏览器中可以看到：
- 写作分数走势图（最近 10 篇）
- 四科雷达图（当前 vs 目标）
- 高频错误 Top 10
- 同义替换库统计
- 词汇复习概览
- 距离考试天数 + 每日建议

路径：`~/.ielts/dashboard.html`
刷新：在浏览器中刷新即可看到最新数据。

💾 提示：运行 `python3 ~/.claude/skills/shared/ielts_cli.py backup` 备份全部数据。
```

---

## 故障处理

### 如果浏览器没自动打开

告诉用户手动打开：
```bash
open ~/.ielts/dashboard.html
```

### 如果没有数据

提醒用户：
```
Dashboard 里还没数据。先去做一次练习：

- 批改一篇作文 → /ielts-writing
- 分析一篇阅读 → /ielts-reading
- 分析一套听力 → /ielts-listening

有了数据后，再回来 `/ielts-dashboard`。
```

---

## 边界

- 你只生成 Dashboard——不分析数据（那是 `/ielts-diagnosis` 的事）
- 数据来源是 `~/.ielts/` 下的 JSON 文件
- Dashboard 是纯静态 HTML，不需要服务器
