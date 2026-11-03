from sqlalchemy import select
from sqlalchemy.orm import Session

from tez.modules.files.models import Attachment, AttachmentKind


class FilesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_attachment(
        self,
        paper_id: str,
        *,
        rel_path: str,
        sha256: str,
        kind: AttachmentKind = AttachmentKind.PDF,
        page_count: int | None = None,
        source: str | None = None,
    ) -> Attachment:
        attachment = Attachment(
            paper_id=paper_id,
            rel_path=rel_path,
            sha256=sha256,
            kind=kind,
            page_count=page_count,
            source=source,
        )
        self.session.add(attachment)
        self.session.flush()
        return attachment

    def find_by_sha256(self, sha256: str) -> Attachment | None:
        return self.session.scalar(select(Attachment).where(Attachment.sha256 == sha256))

    def for_paper(self, paper_id: str) -> list[Attachment]:
        return list(
            self.session.scalars(
                select(Attachment)
                .where(Attachment.paper_id == paper_id)
                .order_by(Attachment.created_at)
            )
        )
