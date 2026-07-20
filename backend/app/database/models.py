"""SQLAlchemy persistence models for downloads and attempts."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DownloadRecord(Base):
    __tablename__ = "downloads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    media_id: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    output_type: Mapped[str] = mapped_column(String(10), nullable=False)
    video_quality: Mapped[int | None] = mapped_column(Integer)
    audio_bitrate: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    attempts: Mapped[list["DownloadAttemptRecord"]] = relationship(
        back_populates="download",
        cascade="all, delete-orphan",
        order_by="DownloadAttemptRecord.number",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_downloads_created_at", "created_at"),)


class DownloadAttemptRecord(Base):
    __tablename__ = "download_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    download_id: Mapped[str] = mapped_column(
        ForeignKey("downloads.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    percentage: Mapped[float | None] = mapped_column(Float)
    downloaded_bytes: Mapped[int | None] = mapped_column(Integer)
    total_bytes: Mapped[int | None] = mapped_column(Integer)
    speed_bytes_per_second: Mapped[float | None] = mapped_column(Float)
    eta_seconds: Mapped[int | None] = mapped_column(Integer)
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_message: Mapped[str | None] = mapped_column(String(500))
    result_filename: Mapped[str | None] = mapped_column(String(500))
    result_extension: Mapped[str | None] = mapped_column(String(20))
    result_size_bytes: Mapped[int | None] = mapped_column(Integer)
    result_effective_quality: Mapped[int | None] = mapped_column(Integer)
    download: Mapped[DownloadRecord] = relationship(back_populates="attempts")

    __table_args__ = (
        Index("ix_attempts_status_created", "status", "created_at"),
        Index("uq_attempt_download_number", "download_id", "number", unique=True),
    )
