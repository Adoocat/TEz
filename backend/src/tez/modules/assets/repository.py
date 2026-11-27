from sqlalchemy import select
from sqlalchemy.orm import Session

from tez.modules.assets.models import AssetKind, ExtractedAsset


class AssetsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, asset: ExtractedAsset) -> ExtractedAsset:
        self.session.add(asset)
        self.session.flush()
        return asset

    def get(self, asset_id: str) -> ExtractedAsset | None:
        return self.session.get(ExtractedAsset, asset_id)

    def all(self, kind: AssetKind | None = None) -> list[ExtractedAsset]:
        query = select(ExtractedAsset).order_by(
            ExtractedAsset.created_at.desc(), ExtractedAsset.id.desc()
        )
        if kind is not None:
            query = query.where(ExtractedAsset.kind == kind)
        return list(self.session.scalars(query))

    def delete(self, asset: ExtractedAsset) -> None:
        self.session.delete(asset)
        self.session.flush()
