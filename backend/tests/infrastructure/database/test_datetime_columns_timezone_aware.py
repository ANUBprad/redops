"""ORM datetime columns must be timezone-aware to match the database schema.

Every timestamp column created by the migrations is ``TIMESTAMP WITH TIME
ZONE`` and the application only ever binds aware UTC datetimes
(``datetime.now(UTC)``). If an ORM model declares a naive ``DateTime`` for such
a column, SQLAlchemy emits a ``::TIMESTAMP WITHOUT TIME ZONE`` bind cast and
asyncpg rejects the aware value, so the write fails on PostgreSQL. The SQLite
test suite does not catch this because the SQLite dialect ignores the timezone
flag, which is why this invariant is asserted directly against the model
metadata for every ORM model.
"""

from __future__ import annotations

import importlib
import pkgutil
from datetime import datetime

from sqlalchemy import DateTime

from app.infrastructure.database import models as models_pkg
from app.infrastructure.database.models.base import Base


def _import_all_models() -> None:
    """Import every model module so ``Base.metadata`` is fully populated."""
    for module_info in pkgutil.iter_modules(models_pkg.__path__):
        importlib.import_module(f"{models_pkg.__name__}.{module_info.name}")


def test_every_datetime_column_is_timezone_aware() -> None:
    _import_all_models()

    naive_columns = [
        f"{table.name}.{column.name}"
        for table in Base.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, DateTime) and not column.type.timezone
    ]

    assert naive_columns == [], (
        "ORM datetime columns must use DateTime(timezone=True) to match the "
        f"TIMESTAMP WITH TIME ZONE schema; naive columns found: {naive_columns}"
    )


def test_mapped_datetime_resolves_to_timezone_aware_type() -> None:
    assert Base.type_annotation_map[datetime].timezone is True
