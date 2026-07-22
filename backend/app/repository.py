from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    delete,
    desc,
    func,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .contracts import Event, SummaryPoint, ZoneCollection, ZoneConfig, ZoneMetric
from .time import utc_now


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


class ZoneRow(Base):
    __tablename__ = "zones"

    camera_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    zone_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    zone_type: Mapped[str] = mapped_column(String(20))
    polygon_json: Mapped[str] = mapped_column(Text)
    capacity: Mapped[int] = mapped_column(Integer)
    dwell_alert_seconds: Mapped[float] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    color: Mapped[str | None] = mapped_column(String(7))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ZoneRevisionRow(Base):
    __tablename__ = "zone_revisions"

    camera_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ZoneRevisionConflict(Exception):
    def __init__(self, current_revision: int) -> None:
        super().__init__(f"Zone configuration changed; current revision is {current_revision}")
        self.current_revision = current_revision


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

    def seed_zones(self, camera_id: str, zones: list[ZoneConfig]) -> ZoneCollection:
        with self.session_factory.begin() as session:
            revision = session.get(ZoneRevisionRow, camera_id)
            if revision is None:
                now = utc_now()
                revision = ZoneRevisionRow(camera_id=camera_id, revision=1, updated_at=now)
                session.add(revision)
                session.add_all(
                    self._zone_row(camera_id, zone, index, now) for index, zone in enumerate(zones)
                )
        return self.zones(camera_id)

    def zones(self, camera_id: str) -> ZoneCollection:
        with Session(self.engine) as session:
            revision = session.get(ZoneRevisionRow, camera_id)
            if revision is None:
                raise LookupError(f"No zone configuration for camera {camera_id}")
            rows = session.scalars(
                select(ZoneRow)
                .where(ZoneRow.camera_id == camera_id)
                .order_by(ZoneRow.sort_order, ZoneRow.zone_id)
            )
            return ZoneCollection(
                camera_id=camera_id,
                revision=revision.revision,
                updated_at=_aware(revision.updated_at),
                zones=[self._zone(row) for row in rows],
            )

    def create_zone(
        self, camera_id: str, zone: ZoneConfig, expected_revision: int
    ) -> ZoneCollection:
        with self.session_factory.begin() as session:
            revision = self._require_revision(session, camera_id, expected_revision)
            if session.get(ZoneRow, (camera_id, zone.zone_id)) is not None:
                raise ValueError(f"Zone {zone.zone_id} already exists")
            max_order = session.scalar(
                select(func.max(ZoneRow.sort_order)).where(ZoneRow.camera_id == camera_id)
            )
            now = utc_now()
            session.add(self._zone_row(camera_id, zone, int(max_order or -1) + 1, now))
            self._bump_revision(revision, now)
        return self.zones(camera_id)

    def update_zone(
        self, camera_id: str, zone_id: str, zone: ZoneConfig, expected_revision: int
    ) -> ZoneCollection:
        if zone.zone_id != zone_id:
            raise ValueError("Zone ID in the body must match the URL")
        with self.session_factory.begin() as session:
            revision = self._require_revision(session, camera_id, expected_revision)
            row = session.get(ZoneRow, (camera_id, zone_id))
            if row is None:
                raise LookupError(f"Zone {zone_id} was not found")
            now = utc_now()
            self._apply_zone(row, zone, now)
            self._bump_revision(revision, now)
        return self.zones(camera_id)

    def delete_zone(self, camera_id: str, zone_id: str, expected_revision: int) -> ZoneCollection:
        with self.session_factory.begin() as session:
            revision = self._require_revision(session, camera_id, expected_revision)
            row = session.get(ZoneRow, (camera_id, zone_id))
            if row is None:
                raise LookupError(f"Zone {zone_id} was not found")
            session.delete(row)
            self._bump_revision(revision, utc_now())
        return self.zones(camera_id)

    def replace_zones(
        self, camera_id: str, zones: list[ZoneConfig], expected_revision: int
    ) -> ZoneCollection:
        with self.session_factory.begin() as session:
            revision = self._require_revision(session, camera_id, expected_revision)
            now = utc_now()
            session.execute(delete(ZoneRow).where(ZoneRow.camera_id == camera_id))
            session.add_all(
                self._zone_row(camera_id, zone, index, now) for index, zone in enumerate(zones)
            )
            self._bump_revision(revision, now)
        return self.zones(camera_id)

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

    @staticmethod
    def _zone_row(
        camera_id: str, zone: ZoneConfig, sort_order: int, updated_at: datetime
    ) -> ZoneRow:
        return ZoneRow(
            camera_id=camera_id,
            zone_id=zone.zone_id,
            name=zone.name,
            zone_type=zone.zone_type,
            polygon_json=json.dumps(zone.polygon_normalized),
            capacity=zone.capacity,
            dwell_alert_seconds=zone.dwell_alert_seconds,
            enabled=zone.enabled,
            color=zone.color,
            sort_order=sort_order,
            updated_at=updated_at,
        )

    @staticmethod
    def _apply_zone(row: ZoneRow, zone: ZoneConfig, updated_at: datetime) -> None:
        row.name = zone.name
        row.zone_type = zone.zone_type
        row.polygon_json = json.dumps(zone.polygon_normalized)
        row.capacity = zone.capacity
        row.dwell_alert_seconds = zone.dwell_alert_seconds
        row.enabled = zone.enabled
        row.color = zone.color
        row.updated_at = updated_at

    @staticmethod
    def _zone(row: ZoneRow) -> ZoneConfig:
        return ZoneConfig(
            zone_id=row.zone_id,
            name=row.name,
            zone_type=row.zone_type,
            polygon_normalized=json.loads(row.polygon_json),
            capacity=row.capacity,
            dwell_alert_seconds=row.dwell_alert_seconds,
            enabled=row.enabled,
            color=row.color,
        )

    @staticmethod
    def _require_revision(
        session: Session, camera_id: str, expected_revision: int
    ) -> ZoneRevisionRow:
        revision = session.get(ZoneRevisionRow, camera_id)
        if revision is None:
            raise LookupError(f"No zone configuration for camera {camera_id}")
        if revision.revision != expected_revision:
            raise ZoneRevisionConflict(revision.revision)
        return revision

    @staticmethod
    def _bump_revision(revision: ZoneRevisionRow, now: datetime) -> None:
        revision.revision += 1
        revision.updated_at = now
