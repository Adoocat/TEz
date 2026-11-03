"""Registry of ORM models.

Import every module's `models` here so `Base.metadata` is complete for Alembic
autogenerate and the models-match-migrations test. Tables arrive in Task 6.
"""

from tez.core.db import Base

__all__ = ["Base"]
