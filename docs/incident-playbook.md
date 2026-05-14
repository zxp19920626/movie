# 故障应急手册（Incident Playbook）

> P6.12。打开这份文档时假设：你正坐在电脑前，5 分钟前手机被告警吵醒，脑子还没启动。
> **不要边读边想边操作**——按章节顺序：先评估、再止血、最后修根因。

## 0. 通用准则（被叫醒时优先看）

1. **先记时间戳**：在 #incidents（或 Telegram 告警频道）发一句"我接手了 [告警 ID]，T0 = HH:MM:SS"，方便复盘
2. **先止血再修因**：能 1 分钟切换到健康状态就先切（如切流量到备机），再慢慢查根因
3. **写下你做的每一步**：每条命令在 chat 里贴出来；事后复盘有据可查
4. **危险操作前问一遍**：DB 改写 / 删数据 / 改 secret / kill 进程——动手前先在 chat 里写明意图，等 30 秒看有没有人喊停
5. **永远不要 `git push --force` / `kubectl delete --all`**

### 通用诊断清单（先按这个跑一遍）

```bash
# 看 backend 进程
ssh ecs "docker ps -a | grep movie-backend"
ssh ecs "docker logs --tail 200 movie-backend"

# 看健康检查
curl -fsS https://api.your-domain.com/healthz
curl -fsS https://api.your-domain.com/readyz

# 看流量
ssh ecs "ss -ant | grep :8000 | wc -l"        # 当前连接数
ssh ecs "tail -f /var/log/nginx/access.log"   # 看请求

# 看资源
ssh ecs "top -bn1 | head -20; df -h; free -h"
```

---

## 1. DB 挂了（RDS 不可达 / 连不上 / 慢查询打满）

**症状**：`/readyz` 返回 503；`/api/v1/...` 都 500；日志一片 `OperationalError: (2003, ...)`

### T+0~5min（止血）

```bash
# 1. 确认是 RDS 自身挂还是网络
ssh ecs "mysql -h <RDS_HOST> -u <user> -p<pass> -e 'SELECT 1'"
# 如果返回 ERROR 2003 → 网络/RDS 挂；返回 1 → 应用问题

# 2. 看阿里云 RDS 控制台：CPU / 连接数 / 慢查询
# https://rdsnext.console.aliyun.com/

# 3. 如果连接数打满（max_connections 触顶）：临时把 backend 降到 1 副本
ssh ecs "docker compose -f /opt/movie/docker-compose.yml up -d --scale backend=1"
```

### T+5~30min（恢复）

- **慢查询导致**：在 RDS 控制台 KILL 长事务（`SHOW PROCESSLIST` 找 Time>30 的）
- **连接泄漏**：重启 backend 容器 (`docker restart movie-backend`) 释放所有连接
- **磁盘满**：在 RDS 控制台扩盘（先扩再缩，扩快缩慢，最少留 30% 余量）
- **RDS 自身挂**：阿里云控制台 → 实例 → 主备切换（30 秒内完成）

### T+30min+（修根因）

- 把慢查询打到日志：`SET GLOBAL slow_query_log=1; long_query_time=0.5`
- 加索引 / 改 query / 引入 read replica
- 长期：上 read replica + 写主从分离（P7.2）

---

## 2. CDN 挂了（Cloudflare / 阿里云 CDN）

**症状**：用户报"打不开"；`/healthz` 服务端正常但用户端 524 / 502

### T+0~5min

```bash
# 1. 确认是 CDN 而不是 origin
curl -fsS -H "Host: api.your-domain.com" https://<ECS_IP>/healthz   # 直连 origin
# origin 200 + CDN 5xx → CDN 问题

# 2. 看 Cloudflare 状态
# https://www.cloudflarestatus.com/
```

### T+5~30min

- **Cloudflare 整盘挂**（罕见）：在 Registrar 改 NS 临时绕过 CF（提前演练过 SOP）；阿里云 DNS 改 A 记录指 ECS 直 IP
- **某 region 挂**：Cloudflare Page Rules 临时排除该 region；或切到阿里云 CDN
- **WAF 误杀**：Cloudflare → Security → Events 看哪条规则在 block；点 disable

### 长期

- Cloudflare + 阿里云 CDN 双备（P7.3）；DNS 用 round-robin 切流量

---

## 3. VOD 挂了（阿里云 VOD ap-southeast-1）

**症状**：App 里影片黑屏 / "无法播放"；后端 `/play-token` 返回正常但实际播不出

### T+0~5min

```bash
# 1. 直接在 VOD 控制台试播一个文件
# https://vod.console.aliyun.com/
# 控制台播 → 媒资管理 → 任意已转码的视频 → "在线播放"

# 2. 测一下 GetPlayInfo SDK
ssh ecs "docker exec movie-backend python -c 'from app.shared.media_provider import ...; print(...)'"
```

### T+5~30min

- **VOD 转码积压**：控制台看转码任务队列；新上传影片不发布给 App
- **PlayAuth 签发失败**：检查 RAM 角色（MovieBackendVodReader）是否被吊销 / 凭证过期
- **某 region 不可用**：通过 CDN 切到 cn-shanghai region 的副本（提前同步过）
- **VOD 全挂**：把已知影片切到本地 OSS + 自建 HLS（应急回退）

### 长期

- 不依赖单 SaaS：保留自建 HLS 出口的能力（IMediaProvider 抽象层正是为此）

---

## 4. 域名挂了（DNS / 续费 / 解析）

**症状**：所有用户 NXDOMAIN

### T+0~5min

```bash
dig your-domain.com @1.1.1.1
dig your-domain.com @8.8.8.8
# 不一致 → DNS 缓存问题；都 NXDOMAIN → 解析挂

# 看 Registrar 后台：是不是过期？
# 看 Cloudflare DNS：A 记录还在吗？被改了吗？
```

### T+5~30min

- **域名过期**：Registrar 后台续费（通常宽限期 30 天）；同时检查为啥 自动续费没生效（信用卡过期）
- **DNS 记录被改**：恢复正确的 A / CNAME；查谁改的（Cloudflare audit log）
- **Cloudflare 整体宕机**：Registrar 改 NS 到阿里云 DNS（提前导出过 zone file）

### 长期

- 域名续费跟踪进入 P6.2 月度账单 review
- 域名 + DNS 配置版本化（terraform / Cloudflare API）

---

## 5. Cloudflare 全挂（极端场景）

**症状**：Cloudflare status 红；几乎所有外部流量异常

### T+0~5min

```bash
# 1. 改 NS：Registrar 后台 → DNS Servers → 切回 Registrar 默认 / 阿里云 DNS
# 提前在 1Password 存好阿里云 DNS 的 NS 地址

# 2. 在备用 DNS 上预先建好 A 记录（指 ECS 直 IP），平时 disable
#    Cloudflare 挂 → enable
```

### T+5~30min

- 通知用户：在 status page（statuspage.io / instatus）发公告
- 流量直连 ECS 后，临时关 Sentry / Datadog 等会反向 outbound 增加 ECS 出口压力的服务

### 长期

- Cloudflare 不是单点：DNS 备份 + WAF 备份（用阿里云 WAF）+ CDN 备份

---

## 6. 应用层 5xx 暴增（业务 bug）

**症状**：Sentry 突然刷一片报错；某个端点 5xx 比例 > 5%

### T+0~5min

```bash
# 1. Sentry 看 Top issue
# 2. 看是不是刚发版引起的：git log --oneline -5; docker images | head
# 3. 如果是：回滚到上一版镜像

ssh ecs "docker tag movie-backend:vN-1 movie-backend:current && docker compose up -d backend"
```

### T+5~30min

- 修复后写 hotfix 分支 → push main → CI 自动 build & deploy
- 如果短期不能修，对该端点加临时降级（返回固定假数据 + 503）

### 复盘

- 每个 5xx 事故必须写 postmortem（docs/postmortems/YYYY-MM-DD-{slug}.md）：
  - 影响：多少用户 / 多长时间
  - 根因：1 句话
  - 时间线：T0 / T+? 各做了什么
  - 教训：哪条监控失效 / 哪个测试该写没写
  - Action items：每条要有 owner + 截止日期

---

## 7. 安全事件（凭据泄露 / DDoS）

### 凭据泄露

1. **立即吊销**：Cloudflare API Token / 阿里云 AK / GitHub PAT —— 所有可能泄露的 token 立刻 revoke
2. **轮换 HMAC 密钥**：跑 `scripts/cp_rotate_hmac.py`（参见 P6.10）
3. **审计 git 历史**：`git log -p | grep -E "(api[_-]?key|secret|token)"`，确认是否进了 git
4. **如进了 git**：用 `git filter-branch` 或 BFG 重写历史 + 强制所有 contributor 重新 clone（破坏性，需要团队同步）

### DDoS

1. Cloudflare WAF → "I'm under attack" 模式
2. 阿里云高防 IP 临时切入（贵，按量付费，事后下掉）
3. 看攻击特征写 WAF rule 永久阻断

---

## 7.5 升级规则编辑相关 422 / 409

> 后台保存 cp_upgrade_rules 时容易踩的两类合规拦截，给值班同学的速查。

### 7.5.1 按钮 url host 不在白名单 → 422

**症状**：管理后台保存规则时返回
```json
{"detail": "host xxx not in allowed_upgrade_hosts"}
```

**根因**：popup_buttons 的某个 `url_i18n` 值的 host 不在 `cp_apps.allowed_upgrade_hosts`。

**处理**：
1. 管理员去 **App 详情页** → "白名单 hosts" 卡片 → 把缺失的 host 追加进 `allowed_upgrade_hosts`
2. 注意 host 形态：纯 host、全小写、无 `https://` 前缀、无 path / port、不做后缀匹配（`cdn.movie.app` 必须显式加，加 `movie.app` 不够）
3. 保存 App 后**重试保存规则**

⚠️ 不能为了"放行"把白名单清空；前端 schema 校验 + 后端校验都会拒绝非 https 或非白名单 host，绕不过去。

### 7.5.2 Play 渠道误配 inapp_apk → 422 / 409

**症状 A（保存规则 422）**：
```json
{"detail": "inapp_apk not allowed on Play channel"}
```
含义：该规则的 `channel_codes` 命中了一个 `is_play_store=true` 的渠道（或 `channel_codes=[]` apply-to-all 也被兜底拦下）。

**症状 B（切渠道 409）**：管理员把某 channel 的 `is_play_store` 从 false 改成 true，PATCH 返回
```json
{
  "error": "existing_rules_have_inapp_apk",
  "violations": [{"rule_id": 123, "name": "全量强升 v102"}]
}
```
含义：rescan 存量规则发现仍有引用了该渠道的 inapp_apk 按钮。

**处理（A）**：
1. 改按钮 `type` 为 `playstore`（推荐：跳应用市场让 Play 拉新版）或 `browser`（落地页）或 `none`（仅"我知道了"）
2. 或缩小 `channel_codes` 到不含 Play 渠道的范围

**处理（B）**：
1. 拿到 `violations` 列表的 rule_id
2. 逐条进规则编辑页，把 inapp_apk 按钮改成 playstore / browser / none
3. 或把规则的 `channel_codes` 收紧、不再包含该渠道
4. 全部处理完再切 is_play_store

⚠️ **不要**为了"先切过去再改规则"绕过 409；切过去之后，老客户端按缓存 response 仍会拿到 inapp_apk 引导，是红线 #2 实锤。

---

## 8. 各场景"千万别做"清单

- ❌ DROP TABLE / TRUNCATE，没 dry-run 先在 staging 跑
- ❌ `git push --force` 到 main
- ❌ 不打 tag 直接重启容器（无法回滚）
- ❌ 高峰期改 schema / 改 nginx 配置 / 改 DNS
- ❌ 凭一个人 30 秒判断就改生产；任何不可逆操作都要 chat 里 confirm + 等回应
- ❌ 静默压住 Sentry 告警（"先静音再说"）；要么修要么写 ticket，不能黑掉

---

## 9. 关键资料（提前在 1Password 备份）

> 这些资料"出事时必须 30 秒拿到"。**不要存仓库里**。1Password vault: "Movie Production"

- 阿里云控制台账号 + MFA recovery code
- Cloudflare 控制台账号 + MFA recovery
- GitHub admin token
- Registrar 账号
- Telegram bot token
- 数据库 root 密码
- ECS SSH key（保存离线）
- VOD / OSS RAM 子账号 AK 列表

---

## 10. 演练（**每季度做一次，不演练 = 等于没有**）

- 模拟 RDS 主备切换：实际点切换按钮，看应用多久恢复
- 模拟 Cloudflare 挂：实际改 NS，看 DNS 收敛时间
- 模拟 keystore 丢失：从 1Password 取出备份，能不能签出可发布的 APK
- 模拟 HMAC 密钥泄露：跑轮换脚本，看 App SDK 是否平滑过渡
- 演练完写一份"我们用了 X 分钟恢复"的总结，更新本文档
