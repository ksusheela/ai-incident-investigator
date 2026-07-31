"""Declarative base for SQLAlchemy ORM models.

Every ORM model (introduced starting with the log-upload feature) inherits
from `Base`. Alembic's autogenerate points at `Base.metadata` to diff the
database against these models.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
