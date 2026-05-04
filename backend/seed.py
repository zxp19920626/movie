"""
seed 脚本：创建 4 个 seed 角色 + 1 个超管账号。
首次运行：uv run python seed.py
重复运行：幂等，已存在不会重复创建。
"""

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.modules.admin.models import AdminRole, AdminUser

SEED_ROLES = [
    {
        "code": "super_admin",
        "name": "超级管理员",
        "is_super_admin": True,
        "is_builtin": True,
        "permissions": [],  # super_admin 走 is_super_admin 短路所有检查
    },
    {
        "code": "content_manager",
        "name": "内容运营",
        "is_super_admin": False,
        "is_builtin": True,
        "permissions": [
            "dashboard.view",
            "content.view", "content.edit",
            "user.view",
        ],
    },
    {
        "code": "global_ops",
        "name": "全球运营",
        "is_super_admin": False,
        "is_builtin": True,
        "permissions": [
            "dashboard.view",
            "cp.view", "cp.edit",
            "content.view",
            "user.view",
        ],
    },
    {
        "code": "service_auditor",
        "name": "审计只读",
        "is_super_admin": False,
        "is_builtin": True,
        "permissions": [
            "dashboard.view",
            "cp.view",
            "content.view",
            "user.view",
            "membership.view",
            "permissions.view",
        ],
    },
]


def main() -> None:
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        for r in SEED_ROLES:
            existing = db.query(AdminRole).filter_by(code=r["code"]).one_or_none()
            if existing is None:
                db.add(AdminRole(**r))
                print(f"[+] 创建角色 {r['code']}")
            else:
                print(f"[=] 角色 {r['code']} 已存在")
        db.commit()

        super_role = db.query(AdminRole).filter_by(code="super_admin").one()
        admin = db.query(AdminUser).filter_by(email=settings.seed_admin_email.lower()).one_or_none()
        if admin is None:
            admin = AdminUser(
                email=settings.seed_admin_email.lower(),
                password_hash=hash_password(settings.seed_admin_password),
                display_name="Super Admin",
                role_id=super_role.id,
                app_scope=[],
                status="active",
            )
            db.add(admin)
            db.commit()
            print(
                f"[+] 创建超管账号 {settings.seed_admin_email} / {settings.seed_admin_password}"
            )
        else:
            print(f"[=] 超管账号 {admin.email} 已存在（如忘记密码请改 seed.py 重跑）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
