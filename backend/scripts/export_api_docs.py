"""从 FastAPI app 的 OpenAPI 导出 docs/api.md。

用法：
    cd backend && uv run python scripts/export_api_docs.py
输出：
    ../docs/api.md（覆盖式生成；改源码后重跑即可）

设计：
- 按 tag 分组，每组一个二级标题
- 每条端点列：method / path / summary / 鉴权 scope（从 Security 推断）
- 不导出参数/请求体细节——保持单页轻量；详细字段查代码或 /docs Swagger
"""

from __future__ import annotations

import sys
from pathlib import Path

# 让脚本可以被 `uv run python scripts/...` 直接跑
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402

OUTPUT = Path(__file__).resolve().parent.parent.parent / "docs" / "api.md"

TAG_DESC = {
    "admin-auth": "后台账号登录 / 当前管理员",
    "user-auth": "C 端用户认证（email / google / phone OTP / refresh）",
    "user-devices": "C 端设备注册",
    "cp-public": "渠道包平台公开端（HMAC 鉴权，App 调）",
    "cp-admin": "渠道包平台后台（admin token 鉴权）",
    "admin-users": "后台 — 用户管理（admin token 鉴权）",
    "default": "其他（healthz/readyz/storage 等）",
}


def main() -> None:
    schema = app.openapi()
    paths = schema.get("paths", {})

    # tag → list[(method, path, summary, op_id)]
    grouped: dict[str, list[tuple[str, str, str, str]]] = {}
    for path, methods in sorted(paths.items()):
        for method, op in methods.items():
            if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            tags = op.get("tags") or ["default"]
            tag = tags[0]
            summary = (
                op.get("summary") or op.get("description", "").splitlines()[0]
                if op.get("description")
                else op.get("summary", "")
            )
            op_id = op.get("operationId", "")
            grouped.setdefault(tag, []).append((method.upper(), path, summary, op_id))

    lines: list[str] = []
    lines.append("# Movie Backend API")
    lines.append("")
    lines.append(
        "> 自动生成，不要手改。改路由后跑 `cd backend && uv run python scripts/export_api_docs.py` 重新生成。"
    )
    lines.append("")
    lines.append(f"端点总数：**{sum(len(v) for v in grouped.values())}**  ")
    lines.append(f"分组数：**{len(grouped)}**  ")
    lines.append(f"文档版本：v{schema.get('info', {}).get('version', '?')}")
    lines.append("")
    lines.append("- 在线交互文档：本地起服后访问 `http://127.0.0.1:8000/docs`")
    lines.append("- 健康检查：`GET /healthz` / `GET /readyz`")
    lines.append("- 静态资源（dev 期）：`/storage/*`")
    lines.append("")

    for tag in sorted(grouped.keys()):
        lines.append(f"## {tag}")
        if tag in TAG_DESC:
            lines.append("")
            lines.append(f"_{TAG_DESC[tag]}_")
        lines.append("")
        lines.append("| 方法 | 路径 | 说明 | operationId |")
        lines.append("| --- | --- | --- | --- |")
        for method, path, summary, op_id in sorted(grouped[tag], key=lambda x: (x[1], x[0])):
            safe_summary = (summary or "").replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{method}` | `{path}` | {safe_summary} | `{op_id}` |")
        lines.append("")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"wrote {OUTPUT} ({sum(len(v) for v in grouped.values())} endpoints, {len(grouped)} tags)"
    )


if __name__ == "__main__":
    main()
