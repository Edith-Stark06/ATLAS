from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import ActivityTone


class ActivityItem(Base):
    """An entry in the live governance activity feed."""

    __tablename__ = "activity_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    message: Mapped[str] = mapped_column(String(400))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    tone: Mapped[ActivityTone] = mapped_column(
        Enum(ActivityTone, name="activity_tone", values_callable=lambda e: [m.value for m in e])
    )
