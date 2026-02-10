from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

pseudo_etf_constituents = Table(
    "pseudo_etf_constituents",
    Base.metadata,
    Column("pseudo_etf_id", Integer, ForeignKey("pseudo_etfs.id", ondelete="CASCADE"), primary_key=True),
    Column("asset_id", Integer, ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
)


class PseudoETF(Base):
    __tablename__ = "pseudo_etfs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_date: Mapped[date] = mapped_column(Date, nullable=False)
    base_value: Mapped[float] = mapped_column(Numeric(12, 4), default=100.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    constituents = relationship("Asset", secondary=pseudo_etf_constituents, lazy="selectin")
