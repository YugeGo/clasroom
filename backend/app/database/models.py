"""
SQLAlchemy ORM 模型

与 schema.sql 中的表结构一一对应，用于代码中操作数据库。
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey,
    Index, Integer, SmallInteger, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database.session import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Building(Base):
    __tablename__ = "buildings"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, unique=True)
    alias = Column(String(64), default="")
    campus = Column(String(64), default="主校区")
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    rooms = relationship("Room", back_populates="building")

    def __repr__(self):
        return f"<Building {self.name}>"


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=False)
    room_number = Column(String(32), nullable=False)
    capacity = Column(Integer, default=0)
    room_type = Column(String(32), default="教室")
    floor = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    building = relationship("Building", back_populates="rooms")
    schedules = relationship("Schedule", back_populates="room")

    __table_args__ = (
        UniqueConstraint("building_id", "room_number"),
    )

    def __repr__(self):
        return f"<Room {self.building.name}-{self.room_number}>"


class Semester(Base):
    __tablename__ = "semesters"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, unique=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_current = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    def __repr__(self):
        return f"<Semester {self.name}>"


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    semester_id = Column(Integer, ForeignKey("semesters.id"), nullable=True)
    day_of_week = Column(SmallInteger, nullable=False)  # 1-7
    start_period = Column(SmallInteger, nullable=False)  # 1-13
    end_period = Column(SmallInteger, nullable=False)  # 1-13
    course_name = Column(String(256), nullable=False)
    teacher_name = Column(String(64), default="")
    weeks = Column(String(64), default="")
    week_count = Column(SmallInteger, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    room = relationship("Room", back_populates="schedules")

    __table_args__ = (
        UniqueConstraint(
            "room_id", "semester_id", "day_of_week", "start_period",
            name="uq_schedule",
        ),
        CheckConstraint(
            "end_period >= start_period",
            name="chk_period_range",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "building_name": self.room.building.name if self.room else "",
            "room_number": self.room.room_number if self.room else "",
            "day_of_week": self.day_of_week,
            "start_period": self.start_period,
            "end_period": self.end_period,
            "course_name": self.course_name,
            "teacher_name": self.teacher_name,
            "weeks": self.weeks,
        }

    def __repr__(self):
        bld = self.room.building.name if self.room else "?"
        room_num = self.room.room_number if self.room else "?"
        return (
            f"<Schedule {bld}-{room_num} "
            f"周{self.day_of_week} 第{self.start_period}-{self.end_period}节 "
            f"{self.course_name}>"
        )


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id = Column(Integer, primary_key=True)
    status = Column(String(16), nullable=False, default="running")
    records_fetched = Column(Integer, default=0)
    records_upserted = Column(Integer, default=0)
    error_message = Column(Text, default="")
    started_at = Column(DateTime(timezone=True), default=_utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<SyncJob {self.id} [{self.status}]>"


class SdufeFreeRoom(Base):
    """
    山财「只存空闲」模型 — 架构文档核心设计。

    与传统的存全部课表不同，本表只存储"空闲"状态的记录，
    大幅提升查询速度。数据由离线脚本解析教务系统 HTML 后清洗入库。
    """
    __tablename__ = "sdufe_free_rooms"

    id = Column(Integer, primary_key=True)
    campus = Column(String(50), nullable=False)       # 校区: 舜耕 / 燕山 / 章丘
    room_name = Column(String(100), nullable=False)    # 教室名: "3号楼-402"
    day_of_week = Column(String(20), nullable=False)   # 星期: "星期一" ~ "星期日"
    period_slot = Column(String(20), nullable=False)   # 节次: "0102" / "0304" / "0506" / "0708" / "0910"
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("campus", "room_name", "day_of_week", "period_slot",
                         name="uq_free_room_slot"),
        Index("idx_campus_day_period", "campus", "day_of_week", "period_slot"),
    )

    def __repr__(self):
        return (
            f"<SdufeFreeRoom {self.campus} {self.room_name} "
            f"{self.day_of_week} {self.period_slot}>"
        )
