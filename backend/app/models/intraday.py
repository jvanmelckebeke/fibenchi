from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IntradayPrice(Base):
    __tablename__ = "intraday_prices"

    # Natural composite key — it's also the upsert's conflict target. There is
    # deliberately no surrogate id: its sequence exhausted at int32 max because
    # ON CONFLICT burns a value per attempted row (~20M/day; migrations
    # 0018/0019). No id, no sequence, no way to exhaust it.
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    price: Mapped[float] = mapped_column(Numeric(12, 4, asdecimal=False))
    volume: Mapped[int] = mapped_column(BigInteger, default=0)
    session: Mapped[str] = mapped_column(String(7), default="regular")  # pre/regular/post
