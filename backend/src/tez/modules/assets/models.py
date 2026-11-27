"""Figures and tables kept from PDFs (plan, data model group 4; Task 55, ADR 0036).

In Phase 3 they come from an area the user marks in the reader: the area is an anchor
(ADR 0033), and the picture of it as the reader drew it is kept under `derived/`.
`data_json` (a table's cells) and other extractors come later.
"""

from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tez.core.db import Base, TimestampMixin, enum_type


class AssetKind(StrEnum):
    FIGURE = "figure"
    TABLE = "table"


class ExtractedAsset(TimestampMixin, Base):
    __tablename__ = "extracted_asset"

    attachment_id: Mapped[str] = mapped_column(
        ForeignKey("attachment.id", ondelete="RESTRICT"), index=True
    )
    kind: Mapped[AssetKind] = mapped_column(enum_type(AssetKind, "asset_kind"))
    # "Figure 3", "Tablo 2": as the paper names it.
    label: Mapped[str] = mapped_column(Text, default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    page_index: Mapped[int] = mapped_column(Integer)
    # [left, bottom, right, top] in PDF user space.
    bbox_json: Mapped[list[float]] = mapped_column(JSON)
    anchor_id: Mapped[str] = mapped_column(ForeignKey("anchor.id", ondelete="RESTRICT"), index=True)
    # The picture, relative to the library folder.
    file_rel_path: Mapped[str] = mapped_column(Text)
    data_json: Mapped[Any] = mapped_column(JSON(none_as_null=True), nullable=True)
    extractor: Mapped[str] = mapped_column(String(32), default="manual")
    extractor_version: Mapped[str] = mapped_column(String(32), default="1")
