from fastapi import APIRouter

from tez import __version__
from tez.modules.system.schemas import Health

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> Health:
    return Health(status="ok", version=__version__)
