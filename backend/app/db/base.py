import json
import uuid
from typing import Any, List, Optional
from sqlalchemy import String, TypeDecorator, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class VectorType(TypeDecorator):
    """
    Dialect-aware vector column:
    Uses pgvector's Vector type on PostgreSQL, and JSON-encoded list on SQLite/other dialects.
    """
    impl = Text
    cache_ok = True

    def __init__(self, dimensions: int = 1536, *args: Any, **kwargs: Any) -> None:
        self.dimensions = dimensions
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import Vector
                return dialect.type_descriptor(Vector(self.dimensions))
            except ImportError:
                return dialect.type_descriptor(postgresql.ARRAY(postgresql.FLOAT))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        if isinstance(value, (list, tuple)):
            return json.dumps(list(value))
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> Optional[List[float]]:
        if value is None:
            return None
        if dialect.name == "postgresql":
            if hasattr(value, "tolist"):
                return value.tolist()
            return list(value)
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return []
        return list(value)


class TSVectorType(TypeDecorator):
    """
    Dialect-aware TSVector column:
    Uses postgresql.TSVECTOR on PostgreSQL, and Text on SQLite/other dialects.
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.TSVECTOR())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        return value


def generate_uuid() -> str:
    return str(uuid.uuid4())
