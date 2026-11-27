"""Figures and tables kept from PDFs (Task 55, ADR 0036).

The user marks an area in the reader and says what it is. The area becomes an anchor, so the
gallery leads back to the place; the picture the reader drew is kept under
`derived/<attachment>/assets/`. A picture must be a PNG.
"""

import base64
import binascii
import logging
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy.orm import Session

from tez.core.errors import ErrorCode, TezError
from tez.modules.anchors import service as anchors
from tez.modules.anchors.models import AnchorKind
from tez.modules.anchors.schemas import AnchorCreate
from tez.modules.assets.models import AssetKind, ExtractedAsset
from tez.modules.assets.repository import AssetsRepository
from tez.modules.assets.schemas import AssetCreate, AssetPatch, AssetView
from tez.modules.files import service as files_service
from tez.modules.library.service import Library

log = logging.getLogger(__name__)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def _not_found(asset_id: str) -> TezError:
    return TezError(ErrorCode.ASSET_NOT_FOUND, {"asset_id": asset_id}, status=404)


def _png(text: str) -> bytes:
    try:
        data = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as error:
        raise TezError(ErrorCode.ASSET_IMAGE_INVALID) from error
    if not data.startswith(PNG_SIGNATURE) or len(data) > MAX_IMAGE_BYTES:
        raise TezError(ErrorCode.ASSET_IMAGE_INVALID)
    return data


def _views(session: Session, assets: Sequence[ExtractedAsset]) -> list[AssetView]:
    found = anchors.by_id(session, [asset.anchor_id for asset in assets])
    views: list[AssetView] = []
    for asset in assets:
        anchor = found.get(asset.anchor_id)
        if anchor is None:
            log.warning("asset %s points at a missing anchor %s", asset.id, asset.anchor_id)
            continue
        views.append(
            AssetView(
                id=asset.id,
                kind=asset.kind,
                label=asset.label,
                caption=asset.caption,
                page=asset.page_index + 1,
                attachment_id=asset.attachment_id,
                anchor_id=asset.anchor_id,
                anchor_status=anchor.status,
                paper=anchor.paper,
                created_at=asset.created_at,
            )
        )
    return views


def add(library: Library, attachment_id: str, body: AssetCreate) -> AssetView:
    """Keep a marked area as a figure or table, with its picture."""
    image = _png(body.image_base64)
    files_service.get_attachment(library.db, attachment_id)
    with library.db.write_session() as session:
        anchor = anchors.create(
            session,
            attachment_id,
            AnchorCreate(kind=AnchorKind.AREA, page=body.page, rects=[body.rect]),
        )
        asset = ExtractedAsset(
            attachment_id=attachment_id,
            kind=body.kind,
            label=body.label,
            caption=body.caption,
            page_index=body.page - 1,
            bbox_json=list(body.rect),
            anchor_id=anchor.id,
            file_rel_path="",
        )
        AssetsRepository(session).add(asset)
        relative = Path("derived") / attachment_id / "assets" / f"{asset.id}.png"
        target = library.path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(image)
        asset.file_rel_path = relative.as_posix()
        session.flush()
        return _views(session, [asset])[0]


def list_assets(library: Library, kind: AssetKind | None = None) -> list[AssetView]:
    with library.db.session() as session:
        return _views(session, AssetsRepository(session).all(kind))


def image_path(library: Library, asset_id: str) -> Path:
    with library.db.session() as session:
        asset = AssetsRepository(session).get(asset_id)
        if asset is None:
            raise _not_found(asset_id)
        path = library.path / asset.file_rel_path
    if not path.is_file():
        raise TezError(ErrorCode.ASSET_IMAGE_MISSING, {"asset_id": asset_id}, status=404)
    return path


def update(library: Library, asset_id: str, body: AssetPatch) -> AssetView:
    with library.db.write_session() as session:
        asset = AssetsRepository(session).get(asset_id)
        if asset is None:
            raise _not_found(asset_id)
        if body.kind is not None:
            asset.kind = body.kind
        if body.label is not None:
            asset.label = body.label
        if body.caption is not None:
            asset.caption = body.caption
        session.flush()
        return _views(session, [asset])[0]


def delete(library: Library, asset_id: str) -> None:
    """Delete the figure or table and its picture. The anchor stays (ADR 0033)."""
    with library.db.write_session() as session:
        repository = AssetsRepository(session)
        asset = repository.get(asset_id)
        if asset is None:
            raise _not_found(asset_id)
        path = library.path / asset.file_rel_path
        repository.delete(asset)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        log.warning("could not delete %s", path, exc_info=True)
