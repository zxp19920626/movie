from __future__ import annotations

from typing import Protocol


class AuthPrincipal(Protocol):
    """已通过鉴权的主体（admin / user / cp_app 任一）的最小契约。"""

    @property
    def subject_id(self) -> str: ...

    @property
    def scope(self) -> str: ...


class IAuthGuard(Protocol):
    """JWT 校验入口；user 模块实现，跨模块调用方只依赖接口。"""

    def verify_access(self, token: str, expected_scope: str) -> AuthPrincipal: ...

    def verify_refresh(self, token: str, expected_scope: str) -> AuthPrincipal: ...
