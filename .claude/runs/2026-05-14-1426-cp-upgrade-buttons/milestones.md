# Milestones — cp 模块升级规则增强（popup_buttons + Play 硬约束 + 域名白名单 + Admin UI）

## 总览

- 里程碑数：4（≤ 10 约束内，小优化级）
- 估算总任务：32 条
- 不可自动化里程碑：**无**（全程不依赖账户实名/法务/商务/物理）
- 红蓝决策：GO_with_5_constraints（已用户拍板）
- 本期不做：Android 客户端

## 5 条硬约束 → 里程碑覆盖矩阵

| 约束 | 落点里程碑 |
|---|---|
| C1 Service 入口校验 Play 拒 inapp_apk + is_play_store 切换回溯 | **M1**（后端） + **M3**（UI 提示） |
| C2 cp_apps.allowed_upgrade_hosts 白名单 | **M1**（表+校验） + **M3**（UI 管理） |
| C3 Pydantic 严格 schema (5/200/ISO 639-1) | **M1** |
| C4 /upgrade/check 出口 i18n fallback + 缺 url 丢弃 | **M1**（helper） + **M2**（API 出口接线） |
| C5 老规则 [] vs 不存在 语义文档化 | **M4** |

## 拓扑序

```
M1 (后端数据模型 + Service) ─┬─→ M2 (公开 API 出口) ─┐
                              │                        ├─→ M4 (文档 + 联调)
                              └─→ M3 (Admin UI)        ┘
```

- [✓] **M1** 后端数据模型 + Service 入口硬约束 — 12/12 任务 PASS，commits=12，push=45810b2
- [✓] **M2** 公开 API /upgrade/check response 输出 + 兼容性 — 6/6 任务 PASS，commits=3（批量 T2+T3 / T4+T5+T6），push=cc629e7
- [✓] **M3** Admin UI 白名单管理 + 按钮编辑器 — 8/8 任务 PASS，commits=4，push=1efbc70
- [✓] **M4** 文档对齐 + 联调验收 — 6/6 任务 PASS，commit=58ae29b（含 channel-module-design §6.1 + incident-playbook §7.5 + 测试用例映射表 + integration_check.md）

## 并行机会

M2 和 M3 在 M1 完成后可并行（一个动 backend/app/channel_pack/api，一个动 admin-web）。如果资源充足主 Agent 可同时拆解，但当前流水线串行执行也只是 +1 个里程碑串行时间，影响小。

## 关键阻塞点

**无阻塞**。所有任务在本地代码 + alembic + pytest + pnpm build 可闭环。不依赖：
- 阿里云/Cloudflare 等外部账户
- Android 客户端实现（PRD 已说明客户端解析逻辑由后续 A1/A2 实现，本期只保证后端 response 正确）
- 真实流量 / 真实租户接入

## 推荐起跑里程碑：M1

理由：
1. **无依赖**，可立即开跑
2. **承载 4/5 硬约束**（C1/C2 后端部分/C3/C4 helper），是整个需求的根基
3. **解锁后续全部里程碑**（M2/M3 都依赖 M1 的模型 + Service helper）
4. **风险集中处理**：Pydantic schema + Service 校验 + alembic 迁移在 M1 一次性收口，后面 UI 和 API 出口只是消费者
5. 单元测试在 M1 内部覆盖，FAIL 不会扩散到下游里程碑

## 验收口子（M4 终报告必查项）

- [ ] alembic upgrade head 成功 + downgrade 可回滚
- [ ] `cd backend && uv run pytest -v` 全绿（含本期新增用例）
- [ ] `cd backend && uv run lint-imports` 通过（模块边界不破）
- [ ] `cd admin-web && pnpm build` 通过
- [ ] `cd backend && uv run python scripts/export_api_docs.py` 刷新 docs/api.md 已 commit
- [ ] docs/channel-module-design.md 含 4.2.5.1 + 兼容性矩阵
- [ ] 5 条硬约束在测试任务文件能逐条对到测试用例编号
