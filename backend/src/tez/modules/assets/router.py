from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse

from tez.modules.assets import service
from tez.modules.assets.models import AssetKind
from tez.modules.assets.schemas import AssetCreate, AssetPatch, AssetView
from tez.modules.library.router import get_library
from tez.modules.library.service import Library

router = APIRouter(tags=["assets"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.post("/attachments/{attachment_id}/assets", status_code=201)
def add_asset(attachment_id: str, body: AssetCreate, library: LibraryDep) -> AssetView:
    """Keep an area marked in the reader as a figure or table, with its picture (PNG)."""
    return service.add(library, attachment_id, body)


@router.get("/assets")
def list_assets(library: LibraryDep, kind: AssetKind | None = None) -> list[AssetView]:
    """Every kept figure and table, newest first."""
    return service.list_assets(library, kind)


@router.get(
    "/assets/{asset_id}/image",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}},
)
def asset_image(asset_id: str, library: LibraryDep) -> FileResponse:
    return FileResponse(service.image_path(library, asset_id), media_type="image/png")


@router.patch("/assets/{asset_id}")
def update_asset(asset_id: str, body: AssetPatch, library: LibraryDep) -> AssetView:
    return service.update(library, asset_id, body)


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(asset_id: str, library: LibraryDep) -> Response:
    """Delete it and its picture; the place in the PDF stays an anchor."""
    service.delete(library, asset_id)
    return Response(status_code=204)
