from __future__ import annotations

from typing import Any, Generic, Sequence, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """SQLAlchemy 仓储基类。子类设置 model = SomeModel 即可获得通用 CRUD。

    设计取舍：
    - 不在 repo 里 commit。事务边界由 service 层（或 FastAPI dependency）负责，
      避免一个请求里多个 repo 互相打架。
    - list 故意不暴露任意 filter，子类按需写显式查询；防止仓储 API 退化成 ORM 透传。
    """

    model: type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, id_: Any) -> ModelT | None:
        return self.db.get(self.model, id_)

    def get_or_404(self, id_: Any) -> ModelT:
        obj = self.get(id_)
        if obj is None:
            raise LookupError(f"{self.model.__name__} {id_} not found")
        return obj

    def list_all(self, *, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        stmt = select(self.model).limit(limit).offset(offset)
        return self.db.execute(stmt).scalars().all()

    def add(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        self.db.flush()
        return obj

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.flush()
