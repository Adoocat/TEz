"""Registry of ORM models.

Import every module's `models` here so `Base.metadata` is complete for Alembic
autogenerate and the models-match-migrations test.
"""

from tez.core.db import Base
from tez.modules.anchors import models as anchors_models
from tez.modules.annotations import models as annotations_models
from tez.modules.files import models as files_models
from tez.modules.fulltext import models as fulltext_models
from tez.modules.jobs import models as jobs_models
from tez.modules.library import models as library_models
from tez.modules.notes import models as notes_models
from tez.modules.quality import models as quality_models
from tez.modules.reviews import models as reviews_models
from tez.modules.search import models as search_models
from tez.modules.settings import models as settings_models

__all__ = [
    "Base",
    "anchors_models",
    "annotations_models",
    "files_models",
    "fulltext_models",
    "jobs_models",
    "library_models",
    "notes_models",
    "quality_models",
    "reviews_models",
    "search_models",
    "settings_models",
]
