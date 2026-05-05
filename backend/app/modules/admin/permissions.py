"""权限点定义（扁平字符串）+ 模块树（前端权限矩阵渲染用）。

约定：
- 字符串格式 `<module>.<action>`
- 6 大模块：dashboard / cp / content / user / membership / permissions
- 每模块至少 view / edit；细粒度可在 ACTIONS 里追加
- super_admin 短路所有检查；其他角色按 a_admin_roles.permissions 列表
"""

from __future__ import annotations

from typing import TypedDict


class PermissionAction(TypedDict):
    code: str
    label: str


class PermissionModule(TypedDict):
    module: str
    label: str
    actions: list[PermissionAction]


PERMISSION_TREE: list[PermissionModule] = [
    {
        "module": "dashboard",
        "label": "数据看板",
        "actions": [
            {"code": "dashboard.view", "label": "查看"},
        ],
    },
    {
        "module": "cp",
        "label": "App 分发平台",
        "actions": [
            {"code": "cp.view", "label": "查看"},
            {"code": "cp.edit", "label": "编辑"},
            {"code": "cp.delete", "label": "删除"},
            {"code": "cp.regenerate_keys", "label": "重生密钥"},
            {"code": "cp.upload_apk", "label": "上传 APK"},
            {"code": "cp.finalize_version", "label": "Finalize 版本"},
        ],
    },
    {
        "module": "content",
        "label": "影片内容",
        "actions": [
            {"code": "content.view", "label": "查看"},
            {"code": "content.edit", "label": "编辑"},
            {"code": "content.delete", "label": "归档"},
            {"code": "content.review", "label": "二次审核"},
            {"code": "content.region_visibility", "label": "地区可见性"},
        ],
    },
    {
        "module": "user",
        "label": "C 端用户",
        "actions": [
            {"code": "user.view", "label": "查看"},
            {"code": "user.edit", "label": "禁用 / 解禁"},
        ],
    },
    {
        "module": "membership",
        "label": "会员订阅",
        "actions": [
            {"code": "membership.view", "label": "查看"},
            {"code": "membership.edit", "label": "编辑订阅"},
        ],
    },
    {
        "module": "permissions",
        "label": "管理员与权限",
        "actions": [
            {"code": "permissions.view", "label": "查看"},
            {"code": "permissions.edit", "label": "编辑角色"},
            {"code": "permissions.assign", "label": "分配成员"},
        ],
    },
]


def all_permission_codes() -> list[str]:
    return [a["code"] for m in PERMISSION_TREE for a in m["actions"]]


# 预置角色（演练 seed 用，可在 admin-web 里改其 permissions 列）
SEED_ROLES = {
    "super_admin": {
        "name": "超级管理员",
        "is_super_admin": True,
        "permissions": [],  # super_admin 短路，permissions 不参与判定
    },
    "content_manager": {
        "name": "内容运营",
        "is_super_admin": False,
        "permissions": [
            "dashboard.view",
            "content.view",
            "content.edit",
            "content.review",
            "content.region_visibility",
        ],
    },
    "global_ops": {
        "name": "全球运营",
        "is_super_admin": False,
        "permissions": [
            "dashboard.view",
            "cp.view",
            "content.view",
            "user.view",
            "membership.view",
        ],
    },
    "service_auditor": {
        "name": "审计只读",
        "is_super_admin": False,
        "permissions": [
            "dashboard.view",
            "cp.view",
            "content.view",
            "user.view",
            "membership.view",
            "permissions.view",
        ],
    },
}
