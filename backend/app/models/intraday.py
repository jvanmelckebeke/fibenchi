from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IntradayPrice(Base):
    __tablename__ = "intraday_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    price: Mapped[float] = mapped_column(Numeric(12, 4, asdecimal=False))
    volume: Mapped[int] = mapped_column(BigInteger, default=0)
    session: Mapped[str] = mapped_column(String(7), default="regular")  # pre/regular/post

    __table_args__ = (
        UniqueConstraint("asset_id", "timestamp", name="uq_intraday_asset_ts"),
        Index("ix_intraday_asset_time", "asset_id", "timestamp"),
    )
