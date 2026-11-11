from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from tez.modules.backup import service
from tez.modules.jobs import service as jobs_service
from tez.modules.library.router import get_library
from tez.modules.library.service import Library

router = APIRouter(prefix="/backups", tags=["backups"])

LibraryDep = Annotated[Library, Depends(get_library)]


class BackupView(BaseModel):
    file_name: str
    size: int
    created_at: datetime
    schema_revision: str | None
    papers: int | None
    attachments: int | None
    app_version: str | None


class BackupStarted(BaseModel):
    job_id: str


@router.get("")
def list_backups(library: LibraryDep) -> list[BackupView]:
    """The library's backups (in its `backups/` folder), newest first."""
    return [
        BackupView(
            file_name=info.path.name,
            size=info.size,
            created_at=info.created_at,
            schema_revision=info.schema_revision,
            papers=info.papers,
            attachments=info.attachments,
            app_version=info.app_version,
        )
        for info in service.list_backups(library.path)
    ]


@router.post("", status_code=202)
def start_backup(library: LibraryDep) -> BackupStarted:
    """Back the library up in the background; follow the job on `/jobs/events`."""
    with library.db.write_session() as session:
        job_id = jobs_service.enqueue(session, service.BACKUP_JOB, {}, dedupe_key="backup")
    return BackupStarted(job_id=job_id)
