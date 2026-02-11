import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AssetType(str, enum.Enum):
    STOCK = "stock"
    ETF = "etf"


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[AssetType] = mapped_column(Enum(AssetType))
    watchlisted: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    prices: Mapped[list["PriceHistory"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    annotations: Mapped[list["Annotation"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    thesis: Mapped["Thesis | None"] = relationship(back_populates="asset", cascade="all, delete-orphan", uselist=False)
    tags: Mapped[list["Tag"]] = relationship(secondary="tag_assets", lazy="selectin")


# Avoid circular import issues - these are resolved at runtime
from app.models.price import PriceHistory  # noqa: E402, F401
from app.models.annotation import Annotation  # noqa: E402, F401
from app.models.thesis import Thesis  # noqa: E402, F401
from app.models.tag import Tag, tag_assets  # noqa: E402, F401
