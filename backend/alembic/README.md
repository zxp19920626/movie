# Alembic 多 head 迁移

## 目录结构

```
backend/
├── alembic.ini                    主配置（指向 4 个 version 目录）
└── alembic/
    ├── env.py                     连 DB + 加载所有模块的 Base
    ├── script.py.mako             revision 模板
    └── versions/
        ├── channel_pack/          P2 渠道包模块的 schema 演化
        ├── user/                  P3 用户模块
        ├── content/               P4 内容模块
        └── admin/                 后台账号 / 权限模块
```

## MVP 阶段策略

当前 `app/main.py` 用 `Base.metadata.create_all()` 建表。**在 P0 RDS 上线 + 第一次正式发版前**，建表脚本 + alembic 双轨并行：

- 新建本地 dev 库 → `create_all` 一把建
- 改 schema → 写 alembic 迁移（每个模块独立）；不再用 create_all

**绝对不许在生产数据库上跑 create_all**——那会忽略约束差异、漏掉 default 等。

## 工作流（之后切换 alembic 时用）

### 第一次：每个模块各起 head

```bash
cd backend
uv run alembic revision -m "init channel_pack" --version-path alembic/versions/channel_pack --branch-label channel_pack --head base
uv run alembic revision -m "init user"         --version-path alembic/versions/user         --branch-label user         --head base
uv run alembic revision -m "init content"      --version-path alembic/versions/content      --branch-label content      --head base
uv run alembic revision -m "init admin"        --version-path alembic/versions/admin        --branch-label admin        --head base
```

### 后续修 schema：在对应模块的 head 上加 revision

```bash
# 例：channel_pack 加新字段
uv run alembic revision -m "cp_apps add foo" --autogenerate --head channel_pack@head
```

`--autogenerate` 会基于 `Base.metadata` 与当前 DB 的 diff 生成；**永远人工 review 一遍**再 apply。

### 升级 / 回滚

```bash
uv run alembic upgrade heads          # 升所有 head 到最新
uv run alembic upgrade channel_pack@head
uv run alembic downgrade channel_pack@-1
uv run alembic history --verbose
uv run alembic current                 # 看当前 DB 各 head 位置
```

## 红线

- **只新增 head，不动已有 revision**——已 apply 的 revision 改 down_revision 链会让回滚错乱
- **生产改 schema 必须有降级 SQL**——`downgrade()` 不能 pass
- **大表加列分两步**：先 NULLABLE 加列上线 → 后续 backfill + ALTER NOT NULL，不要一把梭
- 每条 migration 独立部署一次再做下一条，方便回滚定位
