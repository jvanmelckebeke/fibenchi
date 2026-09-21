from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VolumeCurvePoint(Base):
    """One point on a venue's intraday volume profile.

    Keyed on *session progress*, not clock minutes: bucket b covers elapsed
    fractions ((b-1)/N, b/N] of the regular session, so a half day folds into
    the same curve as a full one instead of needing its own.

    A venue, not a symbol. Per-symbol profiles would need 20 sessions of 5m
    bars each to fit anything stable, and the shape they would find is the
    venue's auction structure — the opening cross, the lunch trough, the
    closing auction — which is what actually moves volume around the day. A
    symbol's own deviation from that is smaller than the noise in fitting it.
    """

    __tablename__ = "volume_curve_points"

    calendar: Mapped[str] = mapped_column(String(32), primary_key=True)
    bucket: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    #: Mean fraction of a regular session's volume traded by the END of this
    #: bucket. Monotone non-decreasing across buckets; the last is 1.0.
    cumulative_fraction: Mapped[float] = mapped_column(Numeric(6, 5, asdecimal=False))
    #: Symbol-sessions the median was taken over. Consumers refuse a thin fit
    #: rather than normalise by a curve drawn through two noisy days.
    samples: Mapped[int] = mapped_column(Integer, default=0)
    fitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
