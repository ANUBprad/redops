"""SQLAlchemy declarative base for all ORM models."""

from datetime import datetime
from typing import ClassVar

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    # Every timestamp column in the migrations is TIMESTAMP WITH TIME ZONE and
    # the codebase only ever binds aware UTC datetimes (datetime.now(UTC)).
    # Left at SQLAlchemy's naive default, ``Mapped[datetime]`` compiles to
    # ``::TIMESTAMP WITHOUT TIME ZONE`` bind casts, which asyncpg rejects for
    # aware values, so inserts fail on PostgreSQL. SQLite tests hid this
    # because the SQLite dialect does not enforce the timezone distinction.
    type_annotation_map: ClassVar[dict[type, DateTime]] = {datetime: DateTime(timezone=True)}
