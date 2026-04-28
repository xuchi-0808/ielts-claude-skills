# IELTS Claude Skills — Project Instructions

## 项目概要

8 个 Claude Code Skill 组成的雅思备考 AI 教练系统 vPro。

## 工作流程

### 日常开发
- 工作目录：`/Users/xc/Documents/Obsidian Vaults/Notebook/Projects/ielts-claude-learn/ielts-claude-skills/`
- 修改后推送到远端：`git push origin master`
- 远端仓库：`git@github.com:xuchi-0808/ielts-claude-skills.git`

### 遇到使用问题时
当用户在使用 skill 过程中发现问题（bug、功能缺失、体验问题），按以下流程处理：

1. 在工作目录中修复问题
2. 同步到 `~/.claude/skills/`：
   ```bash
   cp -r ielts ielts-writing ielts-reading ielts-speaking ielts-listening ielts-vocab ielts-diagnosis ielts-dashboard shared dashboard ~/.claude/skills/
   ```
3. 提交并推送到远端：
   ```bash
   git add -A && git commit -m "<描述修改内容>" && git push origin master
   ```
4. 告知用户修复内容

### 数据层
- CLI 脚本：`shared/ielts_cli.py`（Python stdlib-only）
- 用户数据存储在 `~/.ielts/`，纯本地，无云端
- CLI 路径在 skill 中引用为：`python3 ~/.claude/skills/shared/ielts_cli.py`
