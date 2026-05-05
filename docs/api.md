# Movie Backend API

> 自动生成，不要手改。改路由后跑 `cd backend && uv run python scripts/export_api_docs.py` 重新生成。

端点总数：**68**  
分组数：**12**  
文档版本：v0.2.0

- 在线交互文档：本地起服后访问 `http://127.0.0.1:8000/docs`
- 健康检查：`GET /healthz` / `GET /readyz`
- 静态资源（dev 期）：`/storage/*`

## admin-auth

_后台账号登录 / 当前管理员_

| 方法 | 路径 | 说明 | operationId |
| --- | --- | --- | --- |
| `POST` | `/api/v1/admin/auth/login` | Admin Login | `admin_login_api_v1_admin_auth_login_post` |
| `GET` | `/api/v1/admin/auth/me` | Admin Me | `admin_me_api_v1_admin_auth_me_get` |

## admin-rbac

| 方法 | 路径 | 说明 | operationId |
| --- | --- | --- | --- |
| `GET` | `/api/v1/admin/rbac/admins` | List Admins | `list_admins_api_v1_admin_rbac_admins_get` |
| `POST` | `/api/v1/admin/rbac/admins` | Create Admin | `create_admin_api_v1_admin_rbac_admins_post` |
| `DELETE` | `/api/v1/admin/rbac/admins/{admin_id}` | Disable Admin | `disable_admin_api_v1_admin_rbac_admins__admin_id__delete` |
| `PATCH` | `/api/v1/admin/rbac/admins/{admin_id}` | Update Admin | `update_admin_api_v1_admin_rbac_admins__admin_id__patch` |
| `GET` | `/api/v1/admin/rbac/permissions/tree` | Get Permission Tree | `get_permission_tree_api_v1_admin_rbac_permissions_tree_get` |
| `GET` | `/api/v1/admin/rbac/roles` | List Roles | `list_roles_api_v1_admin_rbac_roles_get` |
| `POST` | `/api/v1/admin/rbac/roles` | Create Role | `create_role_api_v1_admin_rbac_roles_post` |
| `DELETE` | `/api/v1/admin/rbac/roles/{role_id}` | Delete Role | `delete_role_api_v1_admin_rbac_roles__role_id__delete` |
| `PATCH` | `/api/v1/admin/rbac/roles/{role_id}` | Update Role | `update_role_api_v1_admin_rbac_roles__role_id__patch` |

## admin-users

_后台 — 用户管理（admin token 鉴权）_

| 方法 | 路径 | 说明 | operationId |
| --- | --- | --- | --- |
| `GET` | `/api/v1/admin/users` | List Users | `list_users_api_v1_admin_users_get` |
| `GET` | `/api/v1/admin/users/{user_id}` | Get User | `get_user_api_v1_admin_users__user_id__get` |
| `PATCH` | `/api/v1/admin/users/{user_id}` | Update User | `update_user_api_v1_admin_users__user_id__patch` |

## content-admin

| 方法 | 路径 | 说明 | operationId |
| --- | --- | --- | --- |
| `GET` | `/api/v1/admin/content/categories` | List Categories | `list_categories_api_v1_admin_content_categories_get` |
| `POST` | `/api/v1/admin/content/categories` | Create Category | `create_category_api_v1_admin_content_categories_post` |
| `DELETE` | `/api/v1/admin/content/categories/{cat_id}` | Delete Category | `delete_category_api_v1_admin_content_categories__cat_id__delete` |
| `PATCH` | `/api/v1/admin/content/categories/{cat_id}` | Update Category | `update_category_api_v1_admin_content_categories__cat_id__patch` |
| `GET` | `/api/v1/admin/content/videos` | List Videos | `list_videos_api_v1_admin_content_videos_get` |
| `POST` | `/api/v1/admin/content/videos` | Create Video | `create_video_api_v1_admin_content_videos_post` |
| `DELETE` | `/api/v1/admin/content/videos/{video_id}` | Delete Video | `delete_video_api_v1_admin_content_videos__video_id__delete` |
| `GET` | `/api/v1/admin/content/videos/{video_id}` | Get Video | `get_video_api_v1_admin_content_videos__video_id__get` |
| `PUT` | `/api/v1/admin/content/videos/{video_id}` | Update Video | `update_video_api_v1_admin_content_videos__video_id__put` |
| `GET` | `/api/v1/admin/content/videos/{video_id}/region-visibility` | Get Region Visibility | `get_region_visibility_api_v1_admin_content_videos__video_id__region_visibility_get` |
| `POST` | `/api/v1/admin/content/videos/{video_id}/region-visibility` | Set Region Visibility | `set_region_visibility_api_v1_admin_content_videos__video_id__region_visibility_post` |
| `POST` | `/api/v1/admin/content/videos/{video_id}/secondary-review` | Secondary Review | `secondary_review_api_v1_admin_content_videos__video_id__secondary_review_post` |

## content-public

| 方法 | 路径 | 说明 | operationId |
| --- | --- | --- | --- |
| `GET` | `/api/v1/videos` | List Videos | `list_videos_api_v1_videos_get` |
| `GET` | `/api/v1/videos/home` | Home Aggregate | `home_aggregate_api_v1_videos_home_get` |
| `GET` | `/api/v1/videos/search` | Search Videos | `search_videos_api_v1_videos_search_get` |
| `GET` | `/api/v1/videos/{video_id}` | Get Video | `get_video_api_v1_videos__video_id__get` |
| `GET` | `/api/v1/videos/{video_id}/play-token` | Get Play Token | `get_play_token_api_v1_videos__video_id__play_token_get` |

## cp-admin

_渠道包平台后台（admin token 鉴权）_

| 方法 | 路径 | 说明 | operationId |
| --- | --- | --- | --- |
| `GET` | `/api/v1/admin/cp/apps` | List Apps | `list_apps_api_v1_admin_cp_apps_get` |
| `POST` | `/api/v1/admin/cp/apps` | Create App | `create_app_api_v1_admin_cp_apps_post` |
| `DELETE` | `/api/v1/admin/cp/apps/{app_id}` | Delete App | `delete_app_api_v1_admin_cp_apps__app_id__delete` |
| `GET` | `/api/v1/admin/cp/apps/{app_id}` | Get App | `get_app_api_v1_admin_cp_apps__app_id__get` |
| `PATCH` | `/api/v1/admin/cp/apps/{app_id}` | Update App | `update_app_api_v1_admin_cp_apps__app_id__patch` |
| `GET` | `/api/v1/admin/cp/apps/{app_id}/channels` | List Channels | `list_channels_api_v1_admin_cp_apps__app_id__channels_get` |
| `POST` | `/api/v1/admin/cp/apps/{app_id}/channels` | Create Channel | `create_channel_api_v1_admin_cp_apps__app_id__channels_post` |
| `DELETE` | `/api/v1/admin/cp/apps/{app_id}/channels/{channel_id}` | Delete Channel | `delete_channel_api_v1_admin_cp_apps__app_id__channels__channel_id__delete` |
| `PATCH` | `/api/v1/admin/cp/apps/{app_id}/channels/{channel_id}` | Update Channel | `update_channel_api_v1_admin_cp_apps__app_id__channels__channel_id__patch` |
| `POST` | `/api/v1/admin/cp/apps/{app_id}/regenerate-keys` | Regenerate Keys | `regenerate_keys_api_v1_admin_cp_apps__app_id__regenerate_keys_post` |
| `GET` | `/api/v1/admin/cp/apps/{app_id}/rules` | List Rules | `list_rules_api_v1_admin_cp_apps__app_id__rules_get` |
| `POST` | `/api/v1/admin/cp/apps/{app_id}/rules` | Create Rule | `create_rule_api_v1_admin_cp_apps__app_id__rules_post` |
| `POST` | `/api/v1/admin/cp/apps/{app_id}/rules/preview` | Preview Rule | `preview_rule_api_v1_admin_cp_apps__app_id__rules_preview_post` |
| `DELETE` | `/api/v1/admin/cp/apps/{app_id}/rules/{rule_id}` | Delete Rule | `delete_rule_api_v1_admin_cp_apps__app_id__rules__rule_id__delete` |
| `PATCH` | `/api/v1/admin/cp/apps/{app_id}/rules/{rule_id}` | Update Rule | `update_rule_api_v1_admin_cp_apps__app_id__rules__rule_id__patch` |
| `GET` | `/api/v1/admin/cp/apps/{app_id}/signing-jobs` | List Signing Jobs | `list_signing_jobs_api_v1_admin_cp_apps__app_id__signing_jobs_get` |
| `POST` | `/api/v1/admin/cp/apps/{app_id}/signing-jobs/{job_id}/retry` | Retry Signing Job | `retry_signing_job_api_v1_admin_cp_apps__app_id__signing_jobs__job_id__retry_post` |
| `GET` | `/api/v1/admin/cp/apps/{app_id}/versions` | List Versions | `list_versions_api_v1_admin_cp_apps__app_id__versions_get` |
| `POST` | `/api/v1/admin/cp/apps/{app_id}/versions` | Upload Version | `upload_version_api_v1_admin_cp_apps__app_id__versions_post` |
| `DELETE` | `/api/v1/admin/cp/apps/{app_id}/versions/{version_id}` | Delete Version | `delete_version_api_v1_admin_cp_apps__app_id__versions__version_id__delete` |
| `POST` | `/api/v1/admin/cp/apps/{app_id}/versions/{version_id}/finalize` | Finalize Version | `finalize_version_api_v1_admin_cp_apps__app_id__versions__version_id__finalize_post` |

## cp-public

_渠道包平台公开端（HMAC 鉴权，App 调）_

| 方法 | 路径 | 说明 | operationId |
| --- | --- | --- | --- |
| `GET` | `/api/v1/cp/healthz` | Healthz | `healthz_api_v1_cp_healthz_get` |
| `GET` | `/api/v1/cp/upgrade/check` | Upgrade Check | `upgrade_check_api_v1_cp_upgrade_check_get` |

## default

_其他（healthz/readyz/storage 等）_

| 方法 | 路径 | 说明 | operationId |
| --- | --- | --- | --- |
| `GET` | `/healthz` | Healthz | `healthz_healthz_get` |
| `GET` | `/readyz` | Readyz | `readyz_readyz_get` |

## user-auth

_C 端用户认证（email / google / phone OTP / refresh）_

| 方法 | 路径 | 说明 | operationId |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/email/login` | Email Login | `email_login_api_v1_auth_email_login_post` |
| `POST` | `/api/v1/auth/email/register` | Email Register | `email_register_api_v1_auth_email_register_post` |
| `POST` | `/api/v1/auth/google` | Google Login | `google_login_api_v1_auth_google_post` |
| `POST` | `/api/v1/auth/phone/send-otp` | Phone Send Otp | `phone_send_otp_api_v1_auth_phone_send_otp_post` |
| `POST` | `/api/v1/auth/phone/verify` | Phone Verify | `phone_verify_api_v1_auth_phone_verify_post` |
| `POST` | `/api/v1/auth/refresh` | Refresh | `refresh_api_v1_auth_refresh_post` |

## user-devices

_C 端设备注册_

| 方法 | 路径 | 说明 | operationId |
| --- | --- | --- | --- |
| `POST` | `/api/v1/devices/register` | Register Device | `register_device_api_v1_devices_register_post` |

## user-me

| 方法 | 路径 | 说明 | operationId |
| --- | --- | --- | --- |
| `GET` | `/api/v1/users/me` | Me | `me_api_v1_users_me_get` |
| `POST` | `/api/v1/users/me/delete-request` | Request Delete | `request_delete_api_v1_users_me_delete_request_post` |

## watch-history

| 方法 | 路径 | 说明 | operationId |
| --- | --- | --- | --- |
| `GET` | `/api/v1/watch-history` | List Watch History | `list_watch_history_api_v1_watch_history_get` |
| `POST` | `/api/v1/watch-history` | Upsert Watch History | `upsert_watch_history_api_v1_watch_history_post` |
| `DELETE` | `/api/v1/watch-history/{history_id}` | Delete Watch History | `delete_watch_history_api_v1_watch_history__history_id__delete` |

