"""P6.10 HMAC 密钥轮换演练脚本。

故事场景：cp_apps.hmac_secret 怀疑泄露 / 例行 90 天轮换。
要求：换密钥后 App SDK 不掉调用——双接受窗口（dual-accept）。

执行步骤：
  1. (本脚本) POST /admin/cp/apps/{app_id}/regenerate-keys → 拿到新 api_key + hmac_secret
  2. (本脚本) 把新密钥发给 App 团队（控制台/IM/1Password）
  3. App 端发布新版 SDK：先用新密钥；旧版仍流通时后端继续接受旧密钥（24~72h 窗口）
  4. 窗口过后，所有运行中的旧 SDK 也升级了；脚本第二阶段才允许"硬切"
        （hard cutover 后端拒旧密钥）

注意：MVP 阶段后端 cp_apps 模型只持有当前 hmac_secret，**没有 prev_hmac_secret 列**。
要做到真正双接受必须扩 schema（加 prev_hmac_secret + prev_valid_until）+ 改 verifier。
本脚本提示该 TODO，并把当前能做的部分（一键换 key）跑通。

用法：
  cd backend && uv run python scripts/cp_rotate_hmac.py \
      --base-url http://localhost:8000 \
      --admin-email admin@movie.local --admin-password admin123 \
      --app-id 1 \
      --dry-run
  # 去掉 --dry-run 真换；输出新密钥后立刻存入 1Password。
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx


def login(client: httpx.Client, email: str, password: str) -> str:
    r = client.post("/api/v1/admin/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def regenerate(client: httpx.Client, token: str, app_id: int) -> dict[str, Any]:
    r = client.post(
        f"/api/v1/admin/cp/apps/{app_id}/regenerate-keys",
        headers={"Authorization": f"Bearer {token}"},
    )
    r.raise_for_status()
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser(description="P6.10 HMAC 密钥轮换演练")
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--admin-email", required=True)
    ap.add_argument("--admin-password", required=True)
    ap.add_argument("--app-id", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true", help="仅登录验证；不真的换密钥")
    args = ap.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=10) as c:
        try:
            token = login(c, args.admin_email, args.admin_password)
        except httpx.HTTPStatusError as e:
            print(f"[ERR] 登录失败：{e.response.status_code} {e.response.text}", file=sys.stderr)
            return 1
        print(f"[OK] 登录成功，token 前 16 位: {token[:16]}...")

        if args.dry_run:
            print("[DRY-RUN] 跳过密钥轮换。去掉 --dry-run 真换。")
            return 0

        print(f"[..] 调用 regenerate-keys for app_id={args.app_id}")
        try:
            result = regenerate(c, token, args.app_id)
        except httpx.HTTPStatusError as e:
            print(f"[ERR] {e.response.status_code} {e.response.text}", file=sys.stderr)
            return 2

        print("[OK] 新密钥已生成，请立即存入 1Password：")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print()
        print("=== 接下来手动做（不能让脚本替你做）===")
        print("1. 把新 api_key + hmac_secret 提交给 App 团队（IM/1Password）")
        print("2. App 团队发布新版 SDK；旧版仍流通时——")
        print("   ⚠️ 当前后端模型不支持 prev_hmac_secret；旧 SDK 调用会立即 401！")
        print("   生产前应扩 cp_apps schema：增加 prev_hmac_secret + prev_valid_until 列；")
        print("   改 hmac_verifier.verify_signature 双 secret 校验；本脚本第二阶段一并补。")
        print('3. 旧 SDK 全部升级后再 "硬切"（清掉 prev_*）')
        return 0


if __name__ == "__main__":
    sys.exit(main())
