from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Currency(Base):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    display_code: Mapped[str] = mapped_column(String(10))
    divisor: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
