# movie

海外影视 App 服务端 + 管理后台 + 多租户 App 分发平台。Monorepo。

## 目录

```
movie/
├── backend/         FastAPI + MySQL + Redis + Celery
├── admin-web/       Vue3 + Vite + TS + Element Plus + Pinia
├── android/         Android App（待建，规格见 docs/任务/安卓任务.md）
├── infra/           docker-compose / nginx / k8s（预留）
├── docs/            产品文档 + 架构红线 + 任务拆分 + 运维手册
│   ├── 产品文档.md           ← PRD（先看这个）
│   ├── 架构与红线.md          ← 技术栈 / 模块边界 / 红线 / 不做清单
│   ├── 任务/
│   │   ├── 后端任务.md
│   │   ├── 管理后台任务.md
│   │   ├── 安卓任务.md
│   │   └── 测试任务.md
│   ├── api.md               ← OpenAPI 自动导出
│   ├── channel-module-design.md
│   ├── incident-playbook.md
│   └── archive/             ← 历史归档（admin 搬迁记录等）
└── scripts/         部署 / 备份 / APK 渠道签名 / Locust 压测
```

## 目标

- 东南亚（印尼/越南/菲律宾/泰国）+ 中东 + 拉美 + 非洲
- 不服务国内、不备案
- 12 个月 DAU 100 万

## 技术栈

FastAPI · MySQL（阿里云国际 RDS）· Redis · Vue3 · 阿里云国际版 · OSS · CDN · VOD · Cloudflare · GitHub Actions

## 开新会话怎么开始

仓库已内置 [`CLAUDE.md`](CLAUDE.md) 自动加载，Claude Code 启动时直接读到协作约束。无需手动粘贴提示词。

新会话启动时主 Agent 会先检查 `.claude/runs/active.json` — 如有未完成的流水线会先提示你 `/继续` 还是开新需求。

直接说要做什么：

| 命令 / 自然语言 | 行为 |
|---|---|
| `/新需求 <一句话描述>` | 起新流水线，全自动跑到底 |
| `/继续` | 接续上次中断的流水线 |
| `/状态` | 查看当前 run 进度（只读） |
| `/停止` | 优雅停止当前 run（关窗口前用） |
| 「做 P3.7」「把后端剩下的任务都做了」 | 已有任务，自动 for-loop |
| 「X 是怎么实现的 / 这段代码为什么报错」 | 答疑，不走流程 |

## 多 Agent 工作流（Ralph 方案 — 全自动 + 里程碑分层 + 跨会话恢复）

```
主对话（coordinator）
  ↓ 起 run（.claude/runs/<run-id>/）
  ↓ 红线预检（触线 → redblue → 停下等你拍板）
  ↓ 改产品文档
  ↓
meta-planner agent → 切里程碑 ≤ 10 个
  ↓
[里程碑层 for-loop]
  for milestone:
    阻塞用户的里程碑 → 输出 checklist → 停下等你 /继续
    planner agent → 拆任务 ≤ 30 条
    [任务层 for-loop]
      developer agent → 实施 + 强制新增专属测试用例
      tester agent → pytest + import-linter + admin-web build → PASS/FAIL
      PASS → [✓] + commit → 下一条
      FAIL 1/2 → SendMessage 回 dev 修
      FAIL 3 → 标 [~] + cascade skip 下游 → 不停继续
    里程碑结束 → push origin main（每里程碑 push 一次）
  ↓
全部里程碑完成 → 终报告（你只看这个）
```

**全自动诺言**：你只在 `/新需求` 这一刻说一次需求，之后流水线自动跑到底。
所有进度写盘到 `.claude/runs/<run-id>/`（进 git，跨电脑可恢复）。
关窗口 / 几天后回来 → 任意新窗口 `/继续` 接着跑。

**5 个必停口子**：
1. 触红线 → 调 redblue 等你拍板
2. planner / meta-planner 拆解失败 → 等你补需求
3. dev 发现规格歧义 → 等你改产品文档
4. 跑到阻塞用户里程碑（账户实名 / 法务 / 商务） → 输出 checklist 等你做完
5. FAIL 3 轮（**不停**） → 标 `[~]` + cascade skip 进终报告

**不可自动化的事**：账户实名 / 法务 / 商务 / 运营 / 物理操作 5 大类，详见 [`docs/不可自动化清单.md`](docs/不可自动化清单.md)。

Subagent 定义：[`.claude/agents/`](.claude/agents/)
Slash command：[`.claude/commands/新需求.md`](.claude/commands/新需求.md)

## 文档结构

| 文件 | 作用 |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Claude Code 协作硬约束（自动加载） |
| [docs/产品文档.md](docs/产品文档.md) | PRD（新需求先改这里） |
| [docs/架构与红线.md](docs/架构与红线.md) | 技术栈 / 模块边界 / 红线 / 不做清单 |
| [docs/不可自动化清单.md](docs/不可自动化清单.md) | Claude 永远做不了的 5 类事（账户/法务/商务/运营/物理） |
| [docs/任务/](docs/任务/) | 4 个角色任务文件 |
| [docs/api.md](docs/api.md) | OpenAPI 自动导出 |
| [docs/channel-module-design.md](docs/channel-module-design.md) | App 分发平台模块深设计 |
| [docs/incident-playbook.md](docs/incident-playbook.md) | 故障应急手册 |
| [.claude/runs/README.md](.claude/runs/README.md) | 跨会话流水线状态规范 |
