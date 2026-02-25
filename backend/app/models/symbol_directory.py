from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SymbolDirectory(Base):
    __tablename__ = "symbol_directory"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(300))
    exchange: Mapped[str] = mapped_column(String(100), default="")
    type: Mapped[str] = mapped_column(String(10), default="stock")
    last_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("symbol_sources.id", ondelete="SET NULL"), nullable=True
    )
