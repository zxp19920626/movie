# Movie 项目协作约束（Claude Code 强制工作流）

> 本文件由 Claude Code 启动时自动加载。**所有约束都是硬性的**，不准跳过。
> 产品需求事实层 → [`docs/产品文档.md`](docs/产品文档.md)
> 技术决策与红线 → [`docs/架构与红线.md`](docs/架构与红线.md)
> 任务跟踪 → [`docs/任务/`](docs/任务/) 下 4 个角色文件

---

## 1. 三种用户消息 → 三条路径

收到用户消息后，**先分类再行动**：

### 1.1 新产品需求 / 改动（强约束流程）
**触发条件（任一即触发）**：
- 用户敲 `/新需求 <描述>` slash command
- 消息含关键词：「新需求 / 加功能 / 改 PRD / 产品改动 / 想做 / 新功能 / 改产品文档 / 加一个 / 我要做」
- 用户描述的事情**没有在 4 个任务文件**里出现

**响应**：
1. **不要直接动代码**。哪怕需求看起来 1 行能写完。
2. 先读 [`docs/产品文档.md`](docs/产品文档.md) 现状
3. 引导用户走完整流水线：「这看起来是新需求，建议走 `/新需求` 流程，先把变更落进产品文档再拆任务实施。要继续吗？」
4. 用户确认后调 [`/新需求` slash command](.claude/commands/新需求.md) 流水线

### 1.2 已存在任务（快速路径）
**触发条件**：用户说「做 P3.7」「实施后端任务里的 X 项」「继续上次没做完的 Y」，且任务在 4 个任务文件里能查到。

**响应**：
1. 不强制改产品文档（任务已规划过）
2. 直接调 `developer` subagent 实施该任务
3. 完成后调 `tester` subagent 校验
4. PASS → 把任务文件里 `[ ]` 改成 `[✓]`，commit message 用 `done: P3.7 ...` 格式
5. FAIL → 把 tester 报告 + developer 上下文一起 SendMessage 回 developer 修，循环直到 PASS

### 1.3 问题 / 探索 / 调试（不走流程）
**触发条件**：用户问「X 是怎么实现的 / 为什么报错 / 这段代码什么意思」。

**响应**：直接答，不走流水线。但**不准修改文件**除非用户明确要求。

---

## 2. 红线检查门禁

任何代码 / 任务 / 部署改动**动手前**对照 [`docs/架构与红线.md`](docs/架构与红线.md) 第 5 章「红线」+ 第 6 章「不做清单」+ 第 9 章「红蓝对抗触发条件」。

**触线 → 必须开红蓝对抗**（Q4 选 A 自动）：
1. 调 `redblue` subagent
2. agent 内部并行调 architect（主张方案） + premortem（找死法）
3. 合稿输出「方案 / 风险 / 缓解 / 是否破例 / 推荐意见」
4. **停下来等用户拍板**，不准擅自破例

---

## 3. 多 Agent 编排（Ralph 方案）

```
主对话（coordinator，就是我）
  ↓
planner subagent → 拆任务到 4 角色文件 + 验收标准 + 专属测试规格
  ↓ （我核对 + 红线检查）
列任务清单 → 等用户确认本次做哪条 / 哪几条
  ↓ （Q6: 默认只做第一条，剩下挂任务文件）
单任务循环:
  developer subagent → 实施 + 必须新增专属测试用例 (Q3 强约束)
  ↓ （SendMessage 把任务上下文传过去）
  tester subagent → 跑 pytest + import-linter + admin-web build + 专属新测试 → PASS/FAIL
  ↓
  ├ FAIL → SendMessage 回 developer 保留上下文修 → 重测（最多 3 轮）
  ├ 3 轮还 FAIL → 停下汇报用户：错误摘要 + 我的判断
  └ PASS → 任务文件 [ ] → [✓] + commit
```

**单任务做完即停**（Q6）。汇报「这条做完了，下一条是 X，要继续吗？」等用户回复。**不准一锅端**做完整个任务列表。

---

## 4. 文档维护铁律

| 改动类型 | 必改文件 |
|---|---|
| 新功能 / 新模块 / 新表 | `docs/产品文档.md` 对应章节 + `docs/任务/<角色>任务.md` 加任务 |
| 改技术栈 / 引新依赖 / 改红线 | `docs/架构与红线.md` + 必须开红蓝对抗 |
| 任务完成 | 对应任务文件 `[ ]` → `[✓]` + 进度总览数字更新 |
| 任务跳过 | `[ ]` → `[-]` + 写明 `← 原因：...`，**不静默删除** |
| API 改动 | 跑 `cd backend && uv run python scripts/export_api_docs.py` 刷新 `docs/api.md` |

**禁止**：写代码不改文档；改文档不动代码；commit 跨多个不相关任务。

---

## 5. 关键文件 / 命令速查

```bash
# 后端单测
cd backend && uv run pytest -v

# 模块边界（红线 #14）
cd backend && uv run lint-imports

# admin-web build
cd admin-web && pnpm build

# Locust 压测
cd backend && uv run locust -f scripts/locustfile.py --host http://localhost:8000

# Gitleaks（红线 #10）
gitleaks detect --config .gitleaks.toml

# API 文档刷新
cd backend && uv run python scripts/export_api_docs.py

# Seed admin
cd backend && uv run python seed.py
```

| 找东西去哪 |
|---|
| **PRD** = `docs/产品文档.md` |
| **技术 / 红线** = `docs/架构与红线.md` |
| **后端任务** = `docs/任务/后端任务.md` |
| **前端任务** = `docs/任务/管理后台任务.md` |
| **App 任务** = `docs/任务/安卓任务.md` |
| **测试任务** = `docs/任务/测试任务.md` |
| **API 列表** = `docs/api.md`（自动生成） |
| **cp 模块深设计** = `docs/channel-module-design.md` |
| **故障应急** = `docs/incident-playbook.md` |

---

## 6. 沟通风格

- 文档语言：中文，部署 / 运维大白话（用户是 Android 出身、零运维基础）
- 代码 / commit / 标识符：英文
- 注释：默认不写，"为什么"非显然时一行
- 响应：简短直接；关键决策给「推荐 + 一句理由」
- commit message：`done: P3.7 jwt refresh rotation` / `chore: 拆分文档` / `fix: ...` / `feat: ...`

---

## 7. 不准做清单（流程层面）

- ❌ 用户提新需求时**直接写代码**不先改产品文档
- ❌ planner 输出后**不让用户确认**就开始实施
- ❌ developer 写代码**不写专属测试用例**（Q3 强约束，tester 检查没测试直接 FAIL）
- ❌ tester FAIL 时**自作主张破例放行**
- ❌ 触红线时**不开红蓝对抗**直接破例
- ❌ 一次会话**做完整个任务列表**（Q6：单任务做完即停 + 汇报）
- ❌ 任务跳过时**静默删除**（必须 `[-]` + `← 原因：...`）
- ❌ 改 docs/api.md（自动生成的，改路由后跑脚本刷新）
