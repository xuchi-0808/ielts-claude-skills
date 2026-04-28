# IELTS Claude Skills · vPro

> 一套跑在 Claude Code 上的雅思备考 AI 教练 skill。
> **数据持久化、跨会话记忆、可视化 Dashboard、8 个 Skill 协同工作。**

---

## 这是什么

8 个 [Claude Code Skill](https://docs.claude.com/en/docs/claude-code/skills)，构成一个完整的雅思备考助手：

| Skill | 干啥 | 触发词 |
|-------|------|--------|
| `/ielts` | 路由入口 + 摸底 + 进度追踪 | 「我要备考雅思」「IELTS」 |
| `/ielts-writing` | 写作四维批改 + 改写对比 + 审题 + 历史追踪 | 「批改作文」「帮我看看这篇」 |
| `/ielts-reading` | 同义替换提取 + T/F/NG 拆解 + 错题诊断 + 同义替换库 | 「分析阅读」「这道为什么错」 |
| `/ielts-speaking` | 5 个万能故事覆盖 80% Part 2 话题 + 练习追踪 | 「口语素材」「Part 2 准备」 |
| `/ielts-listening` | 听力错题分析 + 精听训练 + 题型追踪 | 「听力」「错题」「精听」 |
| `/ielts-vocab` | 间隔重复复习 + 同义替换专项 + 场景词汇包 | 「背单词」「词汇」「复习」 |
| `/ielts-diagnosis` | 数据诊断 + 个人化备考计划 | 「诊断」「备考计划」 |
| `/ielts-dashboard` | 可视化 Dashboard（趋势图/雷达图/错题热力图） | 「Dashboard」「看数据」 |

**vPro 新特性：**
- 数据持久化到 `~/.ielts/`——跨会话记忆
- **教练记忆系统：** 自动记录你的学习偏好、弱项模式、策略反馈，下次对话无缝衔接
- 每篇作文自动归档，带评分历史
- 错题本自动聚合高频错误标签
- 同义替换库跨篇累计，可搜索
- 间隔重复词汇训练（SM-2 算法）
- 本地 HTML Dashboard：趋势图 / 雷达图 / 错题分布
- 数据驱动诊断 + 个人化训练计划
- 一键备份 / 恢复

---

## 适合谁

- 备考雅思、想用 AI 当陪练的考生
- 已经在用 Claude Code 的开发者
- 想要进度追踪、错题本、可视化 Dashboard 的考生

---

## 安装

### 前提
你要先装好 [Claude Code](https://docs.claude.com/en/docs/claude-code)。

### 安装步骤

```bash
# 1. 进入项目目录
cd ielts-claude-skills

# 2. 复制所有 skill 到 Claude Code skills 目录
cp -r ielts ielts-writing ielts-reading ielts-speaking \
      ielts-listening ielts-vocab ielts-diagnosis ielts-dashboard \
      shared dashboard \
      ~/.claude/skills/

# 3. 初始化数据目录
python3 ~/.claude/skills/shared/ielts_cli.py init

# 4. 重启 Claude Code
```

装完之后重启 Claude Code，输入 `/ielts` 就能用。

---

## 怎么用

### 场景 1：什么都不知道，想被引导

```
你：/ielts
AI：（问你 3 个问题：目标分、考试日期、今天想练啥）
   → 路由到对应的子 skill
   → 自动保存你的配置
```

### 场景 2：直接批改作文

```
你：/ielts-writing
   [粘贴题目 + 你的作文]
AI：
- 四维评分（TR / CC / LR / GRA）
- 句子级标注每个问题
- 改写成目标分数版本
- 给提分优先级
- 自动保存到 ~/.ielts/writing/
```

### 场景 3：分析阅读错题

```
你：/ielts-reading
   [粘贴文章 + 题目 + 你的答案 + 标准答案]
AI：
- 逐题拆解错因
- 提取同义替换词表 → 自动入库
- T/F/NG 逻辑分析
```

### 场景 4：听力错题分析

```
你：/ielts-listening
   [粘贴题目 + 你的答案 + 正确答案]
AI：
- Section 得分分析
- 错因分类（拼写/数字/没听到/干扰项）
- 精听任务生成
```

### 场景 5：词汇复习

```
你：/ielts-vocab
AI：
- 推送今日到期词汇（间隔重复）
- 同义替换专项训练
- 按话题推送词汇包
```

### 场景 6：查看学习数据

```
你：/ielts-dashboard
AI：
- 生成本地 HTML Dashboard
- 自动在浏览器打开
- 写作趋势图 / 四科雷达图 / 错题分布
```

### 场景 7：诊断 + 备考计划

```
你：/ielts-diagnosis
AI：
- 读取所有历史数据
- 生成诊断报告
- 制定每日/每周训练计划
```

---

## 文件结构

```
ielts-claude-skills/
├── ielts/SKILL.md              # 路由教练
├── ielts-writing/SKILL.md      # 写作批改
├── ielts-reading/SKILL.md      # 阅读分析
├── ielts-speaking/SKILL.md     # 口语素材
├── ielts-listening/SKILL.md    # 听力分析
├── ielts-vocab/SKILL.md        # 词汇训练
├── ielts-diagnosis/SKILL.md    # 诊断 + 备考计划
├── ielts-dashboard/SKILL.md    # Dashboard 生成
├── shared/
│   └── ielts_cli.py            # 数据层 CLI（Python stdlib）
├── dashboard/
│   └── template.html           # Dashboard HTML 模板
├── README.md
└── LICENSE                     # MIT
```

---

## 数据存储

全部数据存储在 `~/.ielts/` 下：

```
~/.ielts/
├── config.json          # 用户配置
├── writing/             # 作文历史
├── reading/             # 阅读记录
├── listening/           # 听力记录
├── speaking/            # 口语记录
├── errors.json          # 错题本
├── synonyms.json        # 同义替换库
├── progress.json        # 分数趋势
├── vocab.json           # 词汇 + 间隔重复数据
├── memories.json        # 教练记忆（偏好/弱项/策略）
└── dashboard.html       # 生成的 Dashboard
```

**纯本地，无云端。** 用 `python3 ~/.claude/skills/shared/ielts_cli.py backup` 备份。

---

## License

[MIT](./LICENSE)

---

## 反馈

Fork from [ielts-claude-skills](https://github.com/YANZHANLIN/ielts-claude-skills). Issues and PRs welcome on your own fork.
