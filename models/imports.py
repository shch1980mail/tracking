from datetime import datetime
from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from models.shipment import Base, now

class ImportBatch(Base):
    """Один батч = один лист файла. status: pending|success|partial|failed|rolled_back.
    snapshot: {"created": [order_id], "updated": [{"order_id", "prev": {поле: было}, "new": {поле: стало}}]}"""
    __tablename__ = "import_batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str | None] = mapped_column(String)
    uploaded_by: Mapped[str | None] = mapped_column(String)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    sheet_name: Mapped[str] = mapped_column(String)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="pending")
    snapshot: Mapped[dict | None] = mapped_column(JSON)

class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict | None] = mapped_column(JSON)
