# Movie 项目协作约束（Claude Code 强制工作流）

> 本文件由 Claude Code 启动时自动加载。**所有约束都是硬性的**，不准跳过。
> 产品需求事实层 → [`docs/产品文档.md`](docs/产品文档.md)
> 技术决策与红线 → [`docs/架构与红线.md`](docs/架构与红线.md)
> 任务跟踪 → [`docs/任务/`](docs/任务/) 下 4 个角色文件
> 流水线状态 → [`.claude/runs/`](.claude/runs/README.md)
> 不可自动化边界 → [`docs/不可自动化清单.md`](docs/不可自动化清单.md)

---

## 0. 会话启动检查（先于一切其它逻辑）

每次新会话开始，**响应用户第一条消息前**先检查未完成 run：

```bash
test -f .claude/runs/active.json && cat .claude/runs/active.json
```

| active.json 状态 | 处理 |
|---|---|
| 不存在 | 正常处理用户消息 |
| `status: running` | 提示用户：「检测到上次未完成的 run `<run-id>` (进度 N/M，最近事件 <T>)，要 `/继续` 还是 `/状态` 看详情？」**等用户决定**再处理本条消息 |
| `status: stopped` | 提示用户：「上次主动停在 `<run-id>` (进度 N/M)，要 `/继续` 还是开新需求？」**等用户决定** |
| `status: completed` | 不提示，正常处理 |
| `status: aborted` | 提示用户：「上次异常中止 `<run-id>`，要 `/状态` 看进度还是 `/丢弃 <run-id>` 清理？」**等用户决定** |

**仅例外**：用户消息是 `/状态` / `/继续` / `/停止` / `/丢弃` 时，直接执行对应 slash command 不需要先提示。

---

## 1. 三种用户消息 → 三条路径

收到用户消息后，**先分类再行动**：

### 1.1 新产品需求 / 改动（全自动流水线）
**触发条件（任一即触发）**：
- 用户敲 `/新需求 <描述>` slash command
- 消息含关键词：「新需求 / 加功能 / 改 PRD / 产品改动 / 想做 / 新功能 / 改产品文档 / 加一个 / 我要做」
- 用户描述的事情**没有在 4 个任务文件**里出现

**核心原则**：用户在 `/新需求` 这一刻**只需说一次需求**，之后**全自动跑到底**，只在最终汇报。

**响应**：
1. **不要直接动代码**。哪怕需求看起来 1 行能写完。
2. 先读 [`docs/产品文档.md`](docs/产品文档.md) 现状
3. 直接走 [`/新需求` slash command](.claude/commands/新需求.md) 完整流水线（**不要先问"要继续吗"**，直接开干）
4. 流水线自动跑：改产品文档 → planner 拆任务 → 自动循环 (developer → tester) 到全部完成 → 终报告

### 1.2 已存在任务（快速路径，同样全自动）
**触发条件**：用户说「做 P3.7」「实施后端任务里的 X 项」「继续上次没做完的 Y」「把后端剩下的任务都做了」，且任务在 4 个任务文件里能查到。

**响应**：
1. 不强制改产品文档（任务已规划过）
2. 解析用户指定的任务范围（一条 / 多条 / 整组）
3. **自动 for-loop** 对每一条任务：调 `developer` → 调 `tester` → PASS commit / FAIL 重试 / 3 轮 FAIL 标 `[~]` 跳过
4. **全部完成才汇报**（终报告含 PASS 列表 + FAIL 列表 + commit 记录）

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

## 3. 多 Agent 编排（Ralph 方案 — 里程碑分层 + 全自动循环 + 跨会话恢复）

```
主对话（coordinator，就是我）
  ↓
[Step 0] 创建 run 目录 .claude/runs/<run-id>/
         写 active.json（status=running）
  ↓
[Step 1] 红线预检 → 触线 → 调 redblue → 停下等用户拍板（必停口子①）
  ↓ 不触线
[Step 2] 改 docs/产品文档.md 对应章节
  ↓
[Step 3] meta-planner subagent → 切里程碑 ≤ 10 个
         写 manifest.json + milestones.md
  ↓
[Step 4] 里程碑层 for-loop（按拓扑序）：
  ┌──────────────────────────────────────────────────────────┐
  │ for milestone in milestones:                             │
  │   if milestone.blocks_to_user:                           │
  │     输出阻塞清单 → 暂停（status=stopped）                │
  │     等用户完成 + /继续                                   │
  │     continue（recheck）                                  │
  │                                                          │
  │   planner subagent → 拆该里程碑任务 ≤ 30 条              │
  │   写 tasks_queue.jsonl                                   │
  │                                                          │
  │   for task in 该里程碑任务（按 deps 拓扑序）:            │
  │     if task.deps 有 [~] / cascade_skip:                  │
  │       cascade_skip 该 task（Q4=A）                       │
  │       写 tasks_skipped.jsonl reason=cascade_skip_from_X  │
  │       continue                                           │
  │                                                          │
  │     attempt = 1                                          │
  │     while attempt <= 3:                                  │
  │       发 developer subagent (name=dev-<ID>)              │
  │       发 tester subagent                                 │
  │       PASS → tasks_done.jsonl + commit + break           │
  │       FAIL → SendMessage 回 dev-<ID>; attempt++          │
  │     if attempt > 3:                                      │
  │       tasks_skipped.jsonl reason=failed_3_attempts       │
  │       预跳过该 task 的所有下游（cascade）                │
  │   ↓                                                      │
  │   milestones.md 标 [✓]                                   │
  │   git push origin main（Q5=A 不开 PR）                   │
  │   timeline.log: MILESTONE_DONE + MILESTONE_PUSH          │
  └──────────────────────────────────────────────────────────┘
  ↓
[Step 5] active.json status=completed
         终报告（PASS / FAIL / cascade / commits / 改动文件 / 下一步）
```

**核心约定**：
- ✅ 状态全部写盘（`.claude/runs/<run-id>/`），关窗口能恢复
- ✅ 里程碑分层（meta-planner → planner）解决大需求 context 爆炸
- ✅ 里程碑边界自动 push（Q2=A 修正：上次说"每条 PASS 都 push"是错的，实际是每个里程碑结束 push 一次）
- ✅ FAIL 3 轮 + 上游 [~] 时**自动 cascade skip 下游**（Q4=A），跑到底再让用户处理
- ✅ 不可自动化里程碑（blocks_to_user=true）→ 暂停 + 阻塞清单 + 等用户 /继续
- ✅ 全部里程碑跑完才回主对话汇报终报告
- ❌ 不再"单任务即停"
- ❌ 不再"等用户拍板下一条"

### 3.1 状态写盘时机表

| 事件 | 写哪个文件 |
|---|---|
| run 启动 | active.json + manifest.json + milestones.md |
| meta-planner 完成 | manifest.json.milestones |
| 里程碑开始 | active.json.milestone_idx + timeline.log |
| planner 完成单里程碑拆解 | tasks_queue.jsonl 追加 |
| task 开始 | tasks_running.json + timeline.log |
| task PASS | tasks_done.jsonl 追加 + tasks_running.json 清空 + git commit + active.json 更新 |
| task FAIL N 轮 | tasks_running.json.attempt 自增 + timeline.log |
| task FAIL 3 轮 | tasks_skipped.jsonl 追加 + timeline.log |
| cascade skip | tasks_skipped.jsonl 追加 reason=cascade_skip_from_X |
| 里程碑结束 | milestones.md + manifest.json.milestones[i].status + git push + timeline.log |
| 用户 /停止 | active.json.status=stopped + stopped.flag + timeline.log |
| run 完成 | active.json.status=completed + 终报告 + timeline.log |

### 3.2 cascade skip 算法（Q4=A）

```python
def cascade_skip(failed_task_id):
    # BFS 找所有下游
    queue = [failed_task_id]
    while queue:
        upstream = queue.pop(0)
        downstream = [t for t in tasks_queue if upstream in t.deps and t.status == "pending"]
        for t in downstream:
            t.status = "predicted_skip"
            tasks_skipped.append({
                "id": t.id,
                "reason": f"cascade_skip_from_{failed_task_id}",
                "blocked_downstream": [...]  # 该 task 的下游也会被这个流程标记
            })
            queue.append(t.id)
```

### 3.3 不可自动化里程碑处理

manifest.json.milestones[i].blocks_to_user=true 时，主 Agent 跑到该里程碑：

1. 在 active.json 写 status=stopped + blocked_reason="user_action_required"
2. timeline.log 写 BLOCKED_USER_INPUT M<X>
3. 输出阻塞清单（可执行的 checklist）：
   ```
   ## 流水线暂停 — 等待你完成 M0「账户与域名」

   - [ ] 0.1 在 Cloudflare Registrar 买域名
   - [ ] 0.2 注册阿里云国际版账号
   ...

   完成后任意窗口敲 `/继续` 接着跑。
   ```
4. **退出 for-loop**，等用户 /继续

用户做完后 `/继续` 时，主 Agent 会重新检查该里程碑的 blocks_to_user 任务（按 docs 里那条任务的"完成验证方法"判断；如果验证不了就**询问一次**「M0.1 域名买好了吗？(y/n)」），然后继续往下跑。

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

## 7. 必停口子（自动流水线唯一例外，不停就失控）

自动流水线**只在以下 5 种情况停下问用户**：

| ID | 情况 | 处理 |
|---|---|---|
| ① | planner / meta-planner 触红线 / 不做清单 | 调 `redblue` → 把合稿给用户拍板 |
| ② | planner / meta-planner 拆解失败（需求模糊 / 0 条 / 冲突） | 列歧义点让用户补 |
| ③ | developer 中途发现任务规格歧义 | 中断 → 改产品文档 → /继续 |
| ④ | 跑到 `blocks_to_user=true` 里程碑（账户实名 / 法务 / 应用商店审核 / 商务 / 物理） | 输出阻塞清单 + status=stopped → 等用户做完 + /继续 |
| ⑤ | （**不停**）同一任务 FAIL 3 轮 | 标 `[~]` + cascade skip 下游 + 进终报告，**继续下一里程碑** |

例外 ⑤ 是关键设计：3 轮死循环时**不停下问**，把失败累积到终报告，符合"我只看终验"诉求。

例外 ④ 是大需求关键设计：账户实名 / 应用商店审核 / 真实流量调优等是 Claude 永远做不了的事（详见 [`docs/不可自动化清单.md`](docs/不可自动化清单.md)）。

## 8. 不准做清单（流程层面）

- ❌ 用户提新需求时**直接写代码**不先改产品文档
- ❌ planner 拆完任务**列清单等用户确认**（Q2=B：直接进 for-loop）
- ❌ 任意一条 PASS 后**停下问"下一条做不做"**（Q1=A：自动循环）
- ❌ 每条 PASS 后 push 远程（Q5=A 修正：里程碑结束才 push）
- ❌ developer 写代码**不写专属测试用例**（Q3 强约束，tester 检查没测试直接 FAIL）
- ❌ tester FAIL 时**自作主张破例放行**
- ❌ 触红线时**不开红蓝对抗**直接破例
- ❌ FAIL 3 轮**停下问用户**（应该标 `[~]` + cascade skip 下游继续）
- ❌ 任务跳过时**静默删除**（必须 `[-]` + `← 原因：...` 或 `[~]` + 终报告说明）
- ❌ 跑到 `blocks_to_user=true` 里程碑时**强行尝试自动化**（直接停下 + 阻塞清单）
- ❌ 不写 `.claude/runs/<run-id>/` 状态（关窗口就丢失进度）
- ❌ 改 docs/api.md（自动生成的，改路由后跑脚本刷新）

---

## 9. 不可自动化边界（一句话）

完整清单见 [`docs/不可自动化清单.md`](docs/不可自动化清单.md)。涉及**账户实名 / 法务 / 商务 / 运营 / 物理**的任务，主 Agent 必须停下输出阻塞清单等用户操作。**永远不要假装自己能代办**这些事。
