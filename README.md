# movie

海外影视 App 服务端 + 管理后台。Monorepo。

## 目录
- `backend/` — FastAPI + MySQL + Redis + Celery
- `admin-web/` — Vue3 + Vite + TS + Element Plus + Pinia
- `infra/` — docker-compose / nginx / k8s（预留）
- `docs/` — 架构 / API / 运维手册（中文大白话）
- `scripts/` — 部署、备份、APK 渠道签名等脚本
- `PROMPT.md` — **Claude Code 主提示词，开新会话先粘贴这个**

## 目标
- 东南亚（印尼/越南/菲律宾/泰国）+ 中东 + 拉美 + 非洲
- 不服务国内、不备案
- 12 个月 DAU 100 万

## 技术栈
FastAPI · MySQL（阿里云国际 RDS）· Redis · Vue3 · 阿里云国际版 · OSS · CDN · VOD · Cloudflare · GitHub Actions

## 与 Claude Code 协作
打开新会话后第一句：

> 请先读 `/Users/yikong/Downloads/work/movie/PROMPT.md` 再开始工作。
> 我这次要做：__________

`PROMPT.md` 是项目的长期"宪法"，包含锁定技术栈、架构、API、风险红线、不做清单、起步路径。重大决策遇到红线要开 Agent 红蓝对抗复议。
