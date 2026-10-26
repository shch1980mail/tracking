from datetime import date
from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from models.shipment import Base

def _s(): return mapped_column(String)
def _f(): return mapped_column(Float)
def _i(): return mapped_column(Integer)
def _d(): return mapped_column(Date)

class InboundShipment(Base):
    __tablename__ = "inbound_shipments"
    order_id: Mapped[str] = mapped_column(String, primary_key=True)
    week_number: Mapped[int | None] = _i(); cargo: Mapped[str | None] = _s(); loading_city: Mapped[str | None] = _s()
    weight: Mapped[float | None] = _f(); sender: Mapped[str | None] = _s()
    ship_date: Mapped[date | None] = _d(); plan_arrival: Mapped[date | None] = _d()
    carrier: Mapped[str | None] = _s(); vehicle: Mapped[str | None] = _s(); driver: Mapped[str | None] = _s()
    rate: Mapped[int | None] = _i(); transit_days: Mapped[int | None] = _i()

class LocalShipment(Base):
    __tablename__ = "local_shipments"
    order_id: Mapped[str] = mapped_column(String, primary_key=True)
    number: Mapped[int | None] = _i(); cargo: Mapped[str | None] = _s(); loading_city: Mapped[str | None] = _s()
    sender: Mapped[str | None] = _s(); unloading_city: Mapped[str | None] = _s(); receiver: Mapped[str | None] = _s()
    weight: Mapped[float | None] = _f(); ship_date: Mapped[date | None] = _d()
    carrier: Mapped[str | None] = _s(); vehicle: Mapped[str | None] = _s(); driver: Mapped[str | None] = _s()
    rate: Mapped[int | None] = _i()

class MoscowShipment(Base):
    __tablename__ = "moscow_shipments"
    order_id: Mapped[str] = mapped_column(String, primary_key=True)
    week_number: Mapped[int | None] = _i(); cargo: Mapped[str | None] = _s(); loading_city: Mapped[str | None] = _s()
    unloading_city: Mapped[str | None] = _s(); weight: Mapped[float | None] = _f()
    sender: Mapped[str | None] = _s(); receiver: Mapped[str | None] = _s()
    ship_date: Mapped[date | None] = _d(); plan_arrival: Mapped[date | None] = _d()
    carrier: Mapped[str | None] = _s(); vehicle: Mapped[str | None] = _s(); driver: Mapped[str | None] = _s()
    rate: Mapped[int | None] = _i(); transit_days: Mapped[int | None] = _i()

class TransitToTencard(Base):
    __tablename__ = "transit_to_tencard"
    order_id: Mapped[str] = mapped_column(String, primary_key=True)
    city: Mapped[str | None] = _s(); weight: Mapped[float | None] = _f()
    ship_date: Mapped[date | None] = _d(); plan_arrival: Mapped[date | None] = _d()
    carrier: Mapped[str | None] = _s(); vehicle: Mapped[str | None] = _s(); driver: Mapped[str | None] = _s()
    vehicle_type: Mapped[str | None] = _s()
