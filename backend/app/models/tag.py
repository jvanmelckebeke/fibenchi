from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

tag_assets = Table(
    "tag_assets",
    Base.metadata,
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    Column("asset_id", ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    color: Mapped[str] = mapped_column(String(7), default="#3b82f6")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    assets: Mapped[list["Asset"]] = relationship(secondary=tag_assets, lazy="selectin", overlaps="tags")


from app.models.asset import Asset  # noqa: E402, F401
