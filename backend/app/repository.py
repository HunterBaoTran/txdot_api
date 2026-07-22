from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime, Float, Integer, String, Text, create_engine, desc, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .contracts import Event, SummaryPoint, ZoneMetric


class Base(DeclarativeBase):
    pass


class EventRow(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    camera_id: Mapped[str] = mapped_column(String(100), index=True)
    zone_id: Mapped[str | None] = mapped_column(String(100), index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    severity: Mapped[str] = mapped_column(String(20))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    track_id: Mapped[int | None] = mapped_column(Integer)
    attributes_json: Mapped[str] = mapped_column(Text, default="{}")
    snapshot_ref: Mapped[str | None] = mapped_column(String(500))
    feedback_status: Mapped[str | None] = mapped_column(String(20))
    feedback_reason: Mapped[str | None] = mapped_column(String(500))


class MetricRow(Base):
    __tablename__ = "zone_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(String(100), index=True)
    zone_id: Mapped[str] = mapped_column(String(100), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    occupancy: Mapped[int] = mapped_column(Integer)
    capacity: Mapped[int] = mapped_column(Integer)
    utilization_pct: Mapped[float] = mapped_column(Float)
    entries_total: Mapped[int] = mapped_column(Integer)
    exits_total: Mapped[int] = mapped_column(Integer)
    average_dwell_seconds: Mapped[float] = mapped_column(Float)


class AnalyticsRepository(ABC):
    @abstractmethod
    def add_events(self, events: list[Event]) -> None: ...

    @abstractmethod
    def add_metrics(self, metrics: list[ZoneMetric]) -> None: ...

    @abstractmethod
    def recent_events(self, limit: int = 50, event_type: str | None = None) -> list[Event]: ...

    @abstractmethod
    def summary(self, zone_id: str | None = None, minutes: int = 30) -> list[SummaryPoint]: ...

    @abstractmethod
    def feedback(self, event_id: str, status: str, reason: str | None) -> Event | None: ...


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class SqlAlchemyRepository(AnalyticsRepository):
    def __init__(self, database_url: str | None = None) -> None:
        url = database_url or os.getenv("VERATEX_DATABASE_URL", "sqlite:///./data/veratex.db")
        if url.startswith("sqlite:///./"):
            os.makedirs("data", exist_ok=True)
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=connect_args)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)

    def add_events(self, events: list[Event]) -> None:
        if not events:
            return
        with self.session_factory.begin() as session:
            session.add_all(
                EventRow(
                    event_id=item.event_id,
                    camera_id=item.camera_id,
                    zone_id=item.zone_id,
                    event_type=item.event_type,
                    severity=item.severity,
                    occurred_at=item.occurred_at,
                    track_id=item.track_id,
                    attributes_json=json.dumps(item.attributes),
                    snapshot_ref=item.snapshot_ref,
                )
                for item in events
            )

    def add_metrics(self, metrics: list[ZoneMetric]) -> None:
        if not metrics:
            return
        with self.session_factory.begin() as session:
            session.add_all(
                MetricRow(
                    camera_id=item.camera_id,
                    zone_id=item.zone_id,
                    timestamp=item.timestamp,
                    occupancy=item.occupancy,
                    capacity=item.capacity,
                    utilization_pct=item.utilization_pct,
                    entries_total=item.entries_total,
                    exits_total=item.exits_total,
                    average_dwell_seconds=item.average_dwell_seconds,
                )
                for item in metrics
            )

    def recent_events(self, limit: int = 50, event_type: str | None = None) -> list[Event]:
        statement = select(EventRow).order_by(desc(EventRow.occurred_at)).limit(limit)
        if event_type:
            statement = statement.where(EventRow.event_type == event_type)
        with Session(self.engine) as session:
            return [self._event(row) for row in session.scalars(statement)]

    def summary(self, zone_id: str | None = None, minutes: int = 30) -> list[SummaryPoint]:
        cutoff = datetime.now(UTC) - timedelta(minutes=minutes)
        bucket = func.strftime("%Y-%m-%d %H:%M:%S", MetricRow.timestamp)
        statement = (
            select(
                bucket.label("bucket"),
                func.avg(MetricRow.occupancy).label("occupancy"),
                func.avg(MetricRow.utilization_pct).label("utilization"),
            )
            .where(MetricRow.timestamp >= cutoff)
            .group_by(bucket)
            .order_by(bucket)
        )
        if zone_id:
            statement = statement.where(MetricRow.zone_id == zone_id)
        with Session(self.engine) as session:
            return [
                SummaryPoint(
                    timestamp=datetime.fromisoformat(row.bucket).replace(tzinfo=UTC),
                    occupancy=round(float(row.occupancy), 2),
                    utilization_pct=round(float(row.utilization), 2),
                )
                for row in session.execute(statement)
            ]

    def feedback(self, event_id: str, status: str, reason: str | None) -> Event | None:
        with self.session_factory.begin() as session:
            row = session.get(EventRow, event_id)
            if row is None:
                return None
            row.feedback_status = status
            row.feedback_reason = reason
            session.flush()
            return self._event(row)

    @staticmethod
    def _event(row: EventRow) -> Event:
        return Event(
            event_id=row.event_id,
            camera_id=row.camera_id,
            zone_id=row.zone_id,
            event_type=row.event_type,
            severity=row.severity,
            occurred_at=_aware(row.occurred_at),
            track_id=row.track_id,
            attributes=json.loads(row.attributes_json),
            snapshot_ref=row.snapshot_ref,
            feedback_status=row.feedback_status,
            feedback_reason=row.feedback_reason,
        )

    def healthy(self) -> bool:
        with Session(self.engine) as session:
            session.execute(select(1))
        return True
