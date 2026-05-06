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

直接说要做什么：
- **提新需求** → `/新需求 <一句话描述>`（强制走完整流水线）
- **实施已有任务** → 「做 P3.7」「实施后端任务里的 X」
- **问代码 / 调试** → 直接问

## 多 Agent 工作流（Ralph 方案 — 全自动）

```
主对话（coordinator）
  ↓ 红线预检（触线 → redblue agent → 等你拍板）
  ↓ 改产品文档
  ↓
planner agent → 拆任务到 4 角色文件 + 验收标准 + 专属测试规格
  ↓
[for-loop 自动跑每条任务，不打断]
  developer agent → 实施 + 强制新增专属测试用例
  ↓
  tester agent → pytest + import-linter + admin-web build → PASS/FAIL
  ↓
  PASS → [✓] + commit → 自动取下一条
  FAIL → SendMessage 回 dev 修（最多 3 轮）→ 3 轮 FAIL 标 [~] 进终报告，不停继续
  ↓
全部任务跑完 → 终报告（你只看这个）
```

**全自动诺言**：你只在 `/新需求` 这一刻说一次需求，之后流水线自动跑到底。
唯一会中途停下问你的 4 种情况：触红线 / planner 拆失败 / dev 发现规格歧义 / 触不做清单。
（FAIL 3 轮**不停**，累积到终报告里一次性看。）

Subagent 定义：[`.claude/agents/`](.claude/agents/)
Slash command：[`.claude/commands/新需求.md`](.claude/commands/新需求.md)

## 文档结构

| 文件 | 作用 |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Claude Code 协作硬约束（自动加载） |
| [docs/产品文档.md](docs/产品文档.md) | PRD（新需求先改这里） |
| [docs/架构与红线.md](docs/架构与红线.md) | 技术栈 / 模块边界 / 红线 / 不做清单 |
| [docs/任务/](docs/任务/) | 4 个角色任务文件 |
| [docs/api.md](docs/api.md) | OpenAPI 自动导出 |
| [docs/channel-module-design.md](docs/channel-module-design.md) | App 分发平台模块深设计 |
| [docs/incident-playbook.md](docs/incident-playbook.md) | 故障应急手册 |
