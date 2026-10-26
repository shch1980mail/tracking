from datetime import date, datetime, timezone
from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

def now():
    return datetime.now(timezone.utc)

class Shipment(Base):
    __tablename__ = "shipments"
    order_id: Mapped[str] = mapped_column(String, primary_key=True)
    direction: Mapped[str | None] = mapped_column(String)
    address: Mapped[str | None] = mapped_column(String)
    weight: Mapped[float | None] = mapped_column(Float)
    ship_date: Mapped[date | None] = mapped_column(Date)
    plan_arrival: Mapped[date | None] = mapped_column(Date)
    carrier: Mapped[str | None] = mapped_column(String)
    vehicle_raw: Mapped[str | None] = mapped_column(String)
    vehicle_tractor: Mapped[str | None] = mapped_column(String)
    vehicle_trailer: Mapped[str | None] = mapped_column(String)
    vehicle_container: Mapped[str | None] = mapped_column(String)
    vehicle_type: Mapped[str | None] = mapped_column(String)
    driver_raw: Mapped[str | None] = mapped_column(String)
    driver_fio: Mapped[str | None] = mapped_column(String)
    driver_phone: Mapped[str | None] = mapped_column(String)
    driver_passport: Mapped[str | None] = mapped_column(String)
    gps_link: Mapped[str | None] = mapped_column(String)
    comment: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="planned")  # in_transit|planned|delivered
    status_raw: Mapped[str | None] = mapped_column(String)
    rate: Mapped[int | None] = mapped_column(Integer)
    rate_plan: Mapped[int | None] = mapped_column(Integer)
    transit_days: Mapped[int | None] = mapped_column(Integer)
    termologer: Mapped[str | None] = mapped_column(String)
    location_raw: Mapped[str | None] = mapped_column(String)
    week_number: Mapped[int | None] = mapped_column(Integer)
    excel_row_num: Mapped[int | None] = mapped_column(Integer)
    current_lat: Mapped[float | None] = mapped_column(Float)
    current_lng: Mapped[float | None] = mapped_column(Float)
    ship_lat: Mapped[float | None] = mapped_column(Float)
    ship_lng: Mapped[float | None] = mapped_column(Float)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    missing_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_position_update: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    link_invalid: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class Position(Base):
    __tablename__ = "shipment_positions"
    __table_args__ = (Index("ix_pos_order_time", "order_id", "fetched_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("shipments.order_id"))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)

class GpsLink(Base):
    __tablename__ = "gps_links"
    order_id: Mapped[str] = mapped_column(ForeignKey("shipments.order_id"), primary_key=True)
    url: Mapped[str] = mapped_column(String)
    parser_type: Mapped[str | None] = mapped_column(String)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    is_invalid: Mapped[bool] = mapped_column(Boolean, default=False)
