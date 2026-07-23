import enum
from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

thesis_assets = Table(
    "thesis_assets",
    Base.metadata,
    Column("thesis_id", ForeignKey("theses.id", ondelete="CASCADE"), primary_key=True),
    Column("asset_id", ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
)


class ThesisStatus(str, enum.Enum):
    """Lifecycle of a thesis.

    Stored as its string value in a plain ``String`` column (not a Postgres
    ENUM) to avoid the enum name/value drift that bit the asset-type enum
    (see migration 0013) and to keep new statuses trivial to add.
    """

    WATCHING = "watching"
    LIVE = "live"
    PLAYED_OUT = "played_out"


class Thesis(Base):
    """A global, cross-cutting thematic container — a basket of tickers tracked
    under one investment hypothesis (e.g. "El Niño", "Cables"). An asset can
    belong to many theses; a thesis spans groups."""

    __tablename__ = "theses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    color: Mapped[str] = mapped_column(String(7), default="#3b82f6", server_default="#3b82f6")
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default=ThesisStatus.WATCHING.value,
        server_default=ThesisStatus.WATCHING.value,
    )
    opened_at: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    assets: Mapped[list["Asset"]] = relationship(
        secondary=thesis_assets, lazy="selectin", overlaps="theses"
    )


from app.models.asset import Asset  # noqa: E402, F401
