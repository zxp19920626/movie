# cp 升级弹窗按钮 — 端到端联调验证说明

> 本次需求 M1+M2+M3 已实现的后端 + 前端，本文件给"想真的跑起来调一调"的人当参考。
> 不是自动化脚本，是给人看的步骤。所有命令假设你站在仓库根 `/Users/yikong/Downloads/work/movie`。

---

## 1. 起服务（两端）

### 1.1 后端
```bash
cd backend
# Redis / Postgres 走 docker-compose 或本地实例，按 README
uv run python seed.py            # 种 admin、app、channel、version
uv run uvicorn app.main:app --reload --port 8000
```

后端起来后访问 `http://localhost:8000/docs` 看 swagger，里面 `cp_admin` 命名空间有 rules / apps 相关 CRUD。

### 1.2 admin-web
```bash
cd admin-web
pnpm install
pnpm dev      # 默认 :5173
```

登 admin 后台 → 切到「应用分发 → 升级规则」页面，能看到规则列表 + 编辑器。

---

## 2. 3 个样例规则（手动建，验联调）

> 用 admin-web 的"新建规则"或直接打 POST `/api/v1/admin/cp/apps/{app_id}/rules` 都行。

### 样例 A — 无按钮（兼容性最低，验老客户端走老 4 字段）

```json
{
  "name": "v100 → v101 简单提示（无按钮）",
  "enabled": true,
  "version_code_min": 100,
  "version_code_max": 100,
  "channel_codes": ["direct"],
  "target_version_code": 101,
  "is_force": false,
  "can_skip": true,
  "popup_interval_hours": 24,
  "priority": 50,
  "popup_title": "新版本可用",
  "popup_content": "修复若干问题",
  "popup_confirm": "更新",
  "popup_cancel": "稍后",
  "popup_buttons": null
}
```

预期 /upgrade/check response：**无 popup_buttons 字段**或为 null，只有老 4 字段。

### 样例 B — 多语言多按钮（验 i18n fallback + resolve）

前置：把 `apk.movie.app` 和 `play.google.com` 加进该 app 的 `allowed_upgrade_hosts`。

```json
{
  "name": "v101 → v102 多按钮",
  "enabled": true,
  "version_code_min": 101,
  "version_code_max": 101,
  "channel_codes": ["direct"],
  "target_version_code": 102,
  "is_force": false,
  "can_skip": true,
  "popup_interval_hours": 24,
  "priority": 50,
  "popup_title": "Update available",
  "popup_content": "Bug fixes",
  "popup_confirm": "Update",
  "popup_cancel": "Later",
  "popup_buttons": [
    {
      "id": "primary",
      "type": "inapp_apk",
      "text_i18n": {"en": "Update now", "vi": "Cập nhật", "id": "Perbarui"},
      "url_i18n": {"en": "https://apk.movie.app/v102/direct.apk"},
      "style": "primary"
    },
    {
      "id": "playstore_fallback",
      "type": "playstore",
      "text_i18n": {"en": "Open Play Store", "vi": "Mở Play Store"},
      "url_i18n": {"en": "https://play.google.com/store/apps/details?id=com.movie.app"},
      "style": "secondary"
    },
    {
      "id": "later",
      "type": "none",
      "text_i18n": {"en": "Later", "vi": "Để sau", "id": "Nanti"},
      "style": "text"
    }
  ]
}
```

验证调用：
```bash
# 模拟越南用户
curl "http://localhost:8000/api/v1/cp/upgrade/check?app_id=<tenant_uuid>&version_code=101&channel=direct&device_id=test123&country=VN" \
  -H "Accept-Language: vi-VN,vi;q=0.9,en;q=0.5" \
  -H "X-CP-Timestamp: $(date +%s)" \
  -H "X-CP-Signature: <算好>"
```

预期：
- `popup_buttons[0].text == "Cập nhật"`（vi 命中）
- `popup_buttons[0].url == "https://apk.movie.app/v102/direct.apk"`（en fallback）
- `popup_buttons[2].url == null`（type=none）
- 老 4 字段同时下发（C5 兼容）

### 样例 C — Play 渠道纯外链（验 Play 兜底）

前置：建一个 channel `gp` 且 `is_play_store=true`；`allowed_upgrade_hosts` 含 `play.google.com`。

```json
{
  "name": "Play 渠道引导跳市场",
  "enabled": true,
  "version_code_min": 100,
  "version_code_max": 200,
  "channel_codes": ["gp"],
  "target_version_code": 102,
  "is_force": false,
  "can_skip": true,
  "popup_interval_hours": 24,
  "priority": 50,
  "popup_buttons": [
    {
      "id": "go_play",
      "type": "playstore",
      "text_i18n": {"en": "Open Play Store"},
      "url_i18n": {"en": "https://play.google.com/store/apps/details?id=com.movie.app"},
      "style": "primary"
    }
  ]
}
```

预期：
- 保存成功（playstore 类型在 Play 渠道允许）
- 如果把 `type` 改成 `inapp_apk` → 保存 422
- 调 `/upgrade/check?channel=gp` → **直接 `{"has_update": false}`**（第三道闸：Play 渠道不查规则）

---

## 3. 负向用例（必跑）

### 3.1 host 不在白名单
建一条规则，按钮 url 用 `https://evil.example.com/x.apk` → 后端 422 + 前端弹错。

### 3.2 http://
按钮 url 用 `http://apk.movie.app/x.apk` → 422 "url must be https"。

### 3.3 缩短白名单
App 的 allowed_upgrade_hosts 删掉 `apk.movie.app`（已被样例 B 引用）→ PATCH 409 + affected_rules 含样例 B 的 rule_id。

### 3.4 切 is_play_store
样例 A 的 channel `direct`（含 inapp_apk 规则）→ PATCH `is_play_store=true` → 409 + violations 列样例 B 的 id（如果 direct 渠道被样例 B 引用）。

### 3.5 popup_buttons 超 5
传 6 个 button → 422 "List should have at most 5 items"。

### 3.6 type 拼错
传 `type=dismiss` → 422 "Input should be 'browser', 'playstore', 'inapp_apk', 'deeplink' or 'none'"。

---

## 4. 缓存验证

- 同一组 (app_id, version_code, channel, country, hash_bucket) 第一次打查 DB，第二次打 Redis → response 二进制等价
- 编辑规则 → invalidate `cp:upgrade:{app_id}:*` → 下次请求重查 DB

---

## 5. 跑完确认

- [ ] 样例 A response 不含 popup_buttons / 为 null
- [ ] 样例 B 越南用户拿到 vi 文案 + en url
- [ ] 样例 B response 同时含老 4 字段（兼容老客户端）
- [ ] 样例 C Play 渠道 has_update=false
- [ ] 3.1-3.6 全部正确拒绝
- [ ] 缓存命中第二次 < 50ms（Redis）
