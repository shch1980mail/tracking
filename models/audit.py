from datetime import datetime
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from models.shipment import Base, now

class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    login: Mapped[str | None] = mapped_column(String, index=True)  # и для Basic-входа из env
    action: Mapped[str] = mapped_column(String, index=True)
    entity: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str | None] = mapped_column(String)
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
