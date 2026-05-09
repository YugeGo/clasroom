"""
数据同步 API — 触发爬虫抓取课表并入库
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crawler.client import EduSystemClient
from app.crawler.parser import ScheduleParser
from app.database.models import Building, Room, Schedule, Semester, SyncJob
from app.database.redis_client import redis_manager
from app.database.session import get_db

router = APIRouter(prefix="/api/sync", tags=["同步"])


@router.post("/trigger")
async def trigger_sync(
    username: str = "",
    password: str = "",
    db: AsyncSession = Depends(get_db),
):
    """
    触发一次完整的课表数据同步

    流程:
      1. 创建 SyncJob 记录
      2. 获取分布式锁（防止并发同步）
      3. 登录教务系统
      4. 遍历所有教学楼抓取课表
      5. 解析 HTML → 清洗 → 入库 (UPSERT)
      6. 更新 SyncJob 状态
    """
    # 防重复执行
    locked = await redis_manager.acquire_lock("sync_job", ttl=600)
    if not locked:
        return {"error": "已有同步任务正在执行，请稍后再试"}

    job = SyncJob(status="running", started_at=datetime.now(timezone.utc))
    db.add(job)
    await db.commit()
    await db.refresh(job)

    try:
        # 登录教务系统
        client = EduSystemClient()
        ok = await client.login(username, password)
        if not ok:
            job.status = "failed"
            job.error_message = "教务系统登录失败"
            await db.commit()
            return {"error": "登录失败", "job_id": job.id}

        # 确保当前学期存在
        semester = await _get_or_create_semester(db)

        # 抓取所有课表
        pages = await client.fetch_all_schedules()
        job.records_fetched = len(pages)

        # 解析 + 入库
        total_upserted = 0
        for building_name, html in pages.items():
            parser = ScheduleParser.create(settings.EDU_SYSTEM_TYPE)
            records = parser.parse(html, building=building_name)

            for rec in records:
                await _upsert_schedule(db, rec, semester.id)
                total_upserted += 1

        job.records_upserted = total_upserted
        job.status = "done"
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()

        logger.info(f"同步完成: {total_upserted} 条记录入库")
        return {
            "job_id": job.id,
            "status": "done",
            "records_fetched": len(pages),
            "records_upserted": total_upserted,
        }

    except Exception as e:
        logger.error(f"同步失败: {e}")
        job.status = "failed"
        job.error_message = str(e)
        await db.commit()
        return {"error": str(e), "job_id": job.id}

    finally:
        await redis_manager.release_lock("sync_job")


@router.get("/status/{job_id}")
async def sync_status(job_id: int, db: AsyncSession = Depends(get_db)):
    """查询同步任务状态"""
    from sqlalchemy import select
    result = await db.execute(select(SyncJob).where(SyncJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        return {"error": "任务不存在"}
    return {
        "id": job.id,
        "status": job.status,
        "records_fetched": job.records_fetched,
        "records_upserted": job.records_upserted,
        "error_message": job.error_message,
        "started_at": str(job.started_at) if job.started_at else None,
        "finished_at": str(job.finished_at) if job.finished_at else None,
    }


# ──────────────────────────────────────────────
# 内部辅助
# ──────────────────────────────────────────────

async def _get_or_create_semester(db: AsyncSession) -> Semester:
    """获取当前学期，如果不存在则创建"""
    from sqlalchemy import select

    result = await db.execute(
        select(Semester).where(Semester.is_current == True)
    )
    semester = result.scalar_one_or_none()

    if not semester:
        # 自动生成当前学期名称
        now = datetime.now()
        year = now.year
        month = now.month
        if month >= 8:
            name = f"{year}-{year + 1}-1"
        elif month >= 2:
            name = f"{year - 1}-{year}-2"
        else:
            name = f"{year - 1}-{year}-1"

        semester = Semester(name=name, is_current=True)
        db.add(semester)
        await db.commit()
        await db.refresh(semester)

    return semester


async def _upsert_schedule(db: AsyncSession, record: dict, semester_id: int):
    """
    将一条解析后的排课记录 UPSERT 到数据库

    自动创建不存在的 Building 和 Room
    """
    building_name = record.get("building_name", "未知")
    room_number = record.get("room_number", "000")

    # 查找或创建 Building
    result = await db.execute(
        select(Building).where(Building.name == building_name)
    )
    building = result.scalar_one_or_none()
    if not building:
        building = Building(name=building_name)
        db.add(building)
        await db.flush()

    # 查找或创建 Room
    result = await db.execute(
        select(Room).where(
            Room.building_id == building.id,
            Room.room_number == room_number,
        )
    )
    room = result.scalar_one_or_none()
    if not room:
        room = Room(
            building_id=building.id,
            room_number=room_number,
            floor=int(room_number[0]) if room_number and room_number[0].isdigit() else 0,
        )
        db.add(room)
        await db.flush()

    # UPSERT Schedule (insert or update)
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = pg_insert(Schedule).values(
        room_id=room.id,
        semester_id=semester_id,
        day_of_week=record.get("day_of_week", 0),
        start_period=record.get("start_period", 0),
        end_period=record.get("end_period", 0),
        course_name=record.get("course_name", ""),
        teacher_name=record.get("teacher", ""),
        weeks=record.get("weeks", ""),
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_schedule",
        set_={
            "course_name": stmt.excluded.course_name,
            "teacher_name": stmt.excluded.teacher_name,
            "weeks": stmt.excluded.weeks,
            "updated_at": datetime.now(timezone.utc),
        },
    )
    await db.execute(stmt)
