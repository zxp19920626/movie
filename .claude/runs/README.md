# `.claude/runs/` — 跨会话流水线状态

每次执行 `/新需求` 或大需求任务时，主 Agent 在此创建一个 run 目录，**所有进度写盘**。
关闭窗口 → 任意新窗口 → `/继续` → 从中断点接着跑。

---

## 目录布局

```
.claude/runs/
├── active.json                  ← 指向当前活跃 run（重开窗口先读这个）
├── README.md                    ← 本文件（规范）
└── <run-id>/                    ← 每个 run 一个目录
    ├── manifest.json            ← run 元数据 + 里程碑列表
    ├── milestones.md            ← 人类可读：里程碑进度
    ├── tasks_queue.jsonl        ← 待跑任务队列（按依赖排序）
    ├── tasks_running.json       ← 当前正在跑的任务（≤ 1 条）
    ├── tasks_done.jsonl         ← 已完成（每行一条）
    ├── tasks_skipped.jsonl      ← 跳过（3 轮 FAIL 或 cascade skip）
    ├── timeline.log             ← 时间戳事件流（append-only）
    └── stopped.flag             ← 用户敲 /停止 后写入；存在则下次启动需 /继续
```

---

## run-id 格式

`YYYY-MM-DD-HHMM-<5char-slug>`
例：`2026-05-06-1442-aiqiyi`、`2026-05-06-1500-fav-list`

slug 由主 Agent 从需求里截取（去空格 / 转拼音 / 截 5 字符），用于人眼快速辨识。

---

## active.json

```json
{
  "run_id": "2026-05-06-1442-aiqiyi",
  "title": "开发完整商用安卓影视 App",
  "started_at": "2026-05-06T14:42:11+08:00",
  "status": "running",
  "milestone_idx": 2,
  "milestone_total": 8,
  "tasks_done": 47,
  "tasks_skipped": 3,
  "tasks_total_estimated": 156,
  "last_commit": "a1b2c3d",
  "last_event_at": "2026-05-06T16:38:22+08:00"
}
```

**status 取值**：`running` / `stopped`（用户主动停） / `completed`（终报告已出） / `aborted`（异常崩溃，下次启动询问是否清理）

**写入时机**：
- run 开始 → 创建（status=running）
- 每完成一条任务 → 更新 tasks_done / last_commit / last_event_at
- 每开始新里程碑 → 更新 milestone_idx
- 用户敲 `/停止` → status=stopped
- 终报告输出 → status=completed

---

## manifest.json

```json
{
  "run_id": "2026-05-06-1442-aiqiyi",
  "title": "开发完整商用安卓影视 App",
  "args": "<用户原始 /新需求 输入>",
  "created_at": "2026-05-06T14:42:11+08:00",
  "milestones": [
    {
      "id": "M1",
      "name": "仓库骨架 + 抽象层",
      "description": "...",
      "priority": 1,
      "task_count_estimated": 30,
      "deps": [],
      "status": "done"
    },
    {
      "id": "M2",
      "name": "用户认证 (user 模块)",
      "description": "...",
      "priority": 2,
      "task_count_estimated": 20,
      "deps": ["M1"],
      "status": "running"
    }
  ]
}
```

**写入时机**：meta-planner 拆完里程碑后**一次性写入**；后续只改 milestones[i].status。

---

## milestones.md（人类可读）

```markdown
# Milestones — <title>

- [✓] M1 仓库骨架 + 抽象层 (30/30)
- [~] M2 用户认证 (8/20) — 进行中
- [ ] M3 内容模块 (0/35)
- [ ] M4 cp 平台 (0/40)
- [ ] M5 播放链路 (0/15)
- [ ] M6 admin 后台 (0/12)
- [ ] M7 部署 (0/15)
- [ ] M8 监控告警 (0/10)
```

**写入时机**：里程碑状态变化时同步。

---

## tasks_queue.jsonl

每行一个任务（JSON Lines 格式），按依赖顺序排：

```jsonl
{"id":"P3.5","milestone":"M2","role":"backend","desc":"email 注册登录","deps":[],"verify":"...","test_spec":"backend/tests/test_email_auth.py 至少 5 用例","status":"pending"}
{"id":"P3.6","milestone":"M2","role":"backend","desc":"google oauth","deps":["P3.5"],"verify":"...","test_spec":"...","status":"pending"}
```

**status 取值**：`pending` / `running` / `done` / `skipped` / `predicted_skip`（cascade）

**写入时机**：
- planner 拆任务时**追加**写入
- 任务状态改变时改对应行（用 jsonl 是为了 append 友好；改单行用 sed 或 Read+Write 整文件）

---

## tasks_running.json

```json
{
  "task_id": "P3.6",
  "started_at": "2026-05-06T15:30:11+08:00",
  "attempt": 2,
  "dev_agent_name": "dev-P3.6",
  "last_test_report": "<tester 上一轮 FAIL 的报告>"
}
```

只有 ≤ 1 条任务在跑（自动流水线串行）。

---

## tasks_done.jsonl

```jsonl
{"id":"P3.5","milestone":"M2","commit":"a1b2c3d","files_changed":["backend/app/modules/user/services/email_auth.py","backend/tests/test_email_auth.py"],"test_files":["backend/tests/test_email_auth.py"],"test_count":7,"duration_sec":340,"finished_at":"2026-05-06T15:25:00+08:00"}
```

**写入时机**：tester PASS + commit 后立即追加。

---

## tasks_skipped.jsonl

```jsonl
{"id":"P3.6","milestone":"M2","reason":"failed_3_attempts","root_cause_guess":"google-auth 版本与 PyJWT 冲突","attempted_fixes":["downgrade pyjwt","switch to authlib","mock id_token verification"],"blocked_downstream":["P3.7","P3.8"],"finished_at":"..."}
{"id":"P3.7","milestone":"M2","reason":"cascade_skip_from_P3.6","blocked_downstream":["P3.8"],"finished_at":"..."}
```

**写入时机**：
- FAIL 3 轮时立即追加（reason=failed_3_attempts）
- cascade skip 时立即追加（reason=cascade_skip_from_<upstream_id>）

---

## timeline.log（append-only）

每行一个事件，时间戳 + 类型 + 摘要：

```
2026-05-06T14:42:11 RUN_START title="开发完整商用安卓影视 App"
2026-05-06T14:42:30 META_PLANNER_DONE milestones=8
2026-05-06T14:43:00 MILESTONE_START M1 "仓库骨架"
2026-05-06T14:45:11 PLANNER_DONE M1 tasks=30
2026-05-06T14:45:30 TASK_START P1.6
2026-05-06T14:48:22 TASK_PASS P1.6 commit=a1b2c3d duration=172s
2026-05-06T14:48:30 TASK_START P1.7
...
2026-05-06T15:30:11 TASK_FAIL P3.6 attempt=1
2026-05-06T15:31:50 TASK_FAIL P3.6 attempt=2
2026-05-06T15:33:40 TASK_FAIL P3.6 attempt=3
2026-05-06T15:33:41 TASK_SKIP P3.6 reason=failed_3_attempts
2026-05-06T15:33:42 CASCADE_SKIP P3.7 from=P3.6
...
2026-05-06T16:38:22 MILESTONE_DONE M1 push=origin/main
2026-05-06T16:38:30 USER_STOP
```

**事件类型枚举**：
`RUN_START` / `META_PLANNER_DONE` / `MILESTONE_START` / `PLANNER_DONE` / `TASK_START` / `TASK_PASS` / `TASK_FAIL` / `TASK_SKIP` / `CASCADE_SKIP` / `MILESTONE_DONE` / `MILESTONE_PUSH` / `USER_STOP` / `RUN_RESUME` / `RUN_COMPLETE` / `BLOCKED_USER_INPUT`（触红线 / 拆解失败 / 规格歧义停下）

---

## 跨会话恢复流程

新会话启动时（CLAUDE.md §0 强制规则）：

1. 主 Agent 读 `active.json`
2. 若不存在 → 正常处理用户消息
3. 若存在且 `status == running` → 提示：「上次有未完成的 run X，进度 N/M，要 `/继续` 还是 `/状态`？」
4. 若存在且 `status == stopped` → 提示：「上次主动停在 X，要 `/继续` 还是开新需求？」
5. 若存在且 `status == aborted` → 提示：「上次异常中止，要 `/状态` 看进度还是 `/丢弃 <run-id>` 清理？」

`/继续` 内部行为：
1. 加载 active.json + manifest.json + tasks_queue.jsonl
2. 找 status=pending 且 deps 全 done 的下一条 task
3. 若 tasks_running.json 有未结束的任务 → 优先恢复（attempt 计数延续）
4. 进 for-loop 跑下去
5. 触发 4 个必停口子 → 同样停下等用户

---

## Q&A

**Q：为什么 jsonl 不用 json 数组？**
A：append 友好。一条任务完成立即 echo >> 不需要解析整个文件。

**Q：状态文件冲突怎么办？**
A：自动流水线串行运行，不会有并发写。如果用户两个窗口同时 /继续 → 第二个窗口看到 active.json 的 last_event_at 跟 tasks_done.jsonl 末尾不一致 → 警告用户「检测到并发会话，请只保留一个」。

**Q：jsonl 文件改单行很麻烦，状态改用什么方法？**
A：状态从 `pending → running → done/skipped` 单向不回退；改单行用 Read 整文件 + Write 整文件；jsonl 行数 ≤ 几百条不会慢。

**Q：状态进 git 会污染 commit 历史吗？**
A：会。但 Q1=A 选择是为了换电脑能恢复。任务进度 commit 单独 prefix `state:` 跟 `done:` 区分。**或者**只在每个里程碑结束时 commit 一次状态快照（更干净）。建议后者。
