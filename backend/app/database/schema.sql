-- =============================================
-- Campus Room AI Sniper - 数据库建表 SQL
-- PostgreSQL 16+
-- =============================================

-- =============================================
-- 新架构：山财空教室「只存空闲」表
-- 架构文档核心设计。只存储空闲教室记录，
-- 大幅提升查询速度。
-- =============================================

CREATE TABLE IF NOT EXISTS sdufe_free_rooms (
    id SERIAL PRIMARY KEY,
    campus VARCHAR(50) NOT NULL,       -- 校区 (仅限: 舜耕, 燕山, 章丘)
    room_name VARCHAR(100) NOT NULL,   -- 教室名 (如: 3号楼-402)
    day_of_week VARCHAR(20) NOT NULL,  -- 星期 (如: 星期一, 星期二)
    period_slot VARCHAR(20) NOT NULL,  -- 节次 (如: 0102, 0304, 0506, 0708, 0910)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 唯一约束：同一校区+教室+星期+节次不重复
ALTER TABLE sdufe_free_rooms ADD CONSTRAINT uq_free_room_slot
    UNIQUE (campus, room_name, day_of_week, period_slot);

-- 建立联合索引以加速按校区+星期+节次的筛选查询
CREATE INDEX IF NOT EXISTS idx_campus_day_period
    ON sdufe_free_rooms (campus, day_of_week, period_slot);

-- =============================================
-- ⚠️ 以下保留原有架构（爬虫/教务系统同步使用）
-- =============================================

-- 教学楼字典表
CREATE TABLE IF NOT EXISTS buildings (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(64)  NOT NULL UNIQUE,   -- "3号楼"
    alias       VARCHAR(64),                     -- 别名 "第三教学楼"
    campus      VARCHAR(64) DEFAULT '主校区',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 教室字典表
CREATE TABLE IF NOT EXISTS rooms (
    id              SERIAL PRIMARY KEY,
    building_id     INTEGER      NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
    room_number     VARCHAR(32)  NOT NULL,       -- "402"
    capacity        INTEGER      DEFAULT 0,      -- 座位数
    room_type       VARCHAR(32)  DEFAULT '教室', -- 普通教室/多媒体/实验室
    floor           INTEGER      DEFAULT 0,
    is_active       BOOLEAN      DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE(building_id, room_number)
);

-- 学期字典表
CREATE TABLE IF NOT EXISTS semesters (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(64)  NOT NULL UNIQUE,   -- "2024-2025-1"
    start_date  DATE,
    end_date    DATE,
    is_current  BOOLEAN      DEFAULT FALSE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 排课记录表（核心业务表）
CREATE TABLE IF NOT EXISTS schedules (
    id              SERIAL PRIMARY KEY,
    room_id         INTEGER      NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    semester_id     INTEGER      REFERENCES semesters(id) ON DELETE CASCADE,
    day_of_week     SMALLINT     NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    start_period    SMALLINT     NOT NULL CHECK (start_period BETWEEN 1 AND 13),
    end_period      SMALLINT     NOT NULL CHECK (end_period BETWEEN 1 AND 13),
    course_name     VARCHAR(256) NOT NULL,
    teacher_name    VARCHAR(64)  DEFAULT '',
    weeks           VARCHAR(64)  DEFAULT '',     -- "1-16" 或 "1,3,5,7-16"
    week_count      SMALLINT     DEFAULT 0,      -- 实际上课周数
    is_active       BOOLEAN      DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- 约束：同一房间同一时段不能有两门课
    CONSTRAINT uq_schedule
        UNIQUE (room_id, semester_id, day_of_week, start_period),

    -- 约束：end_period >= start_period
    CONSTRAINT chk_period_range
        CHECK (end_period >= start_period)
);

-- 同步日志表（追踪每次爬虫任务）
CREATE TABLE IF NOT EXISTS sync_jobs (
    id              SERIAL PRIMARY KEY,
    status          VARCHAR(16)  NOT NULL DEFAULT 'running',  -- running/done/failed
    records_fetched INTEGER      DEFAULT 0,
    records_upserted INTEGER     DEFAULT 0,
    error_message   TEXT,
    started_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ
);

-- =============================================
-- 索引
-- =============================================

-- 空教室查询核心索引
CREATE INDEX IF NOT EXISTS idx_schedules_room_period
    ON schedules (room_id, day_of_week, start_period, end_period);

-- 按楼栋查询
CREATE INDEX IF NOT EXISTS idx_rooms_building
    ON rooms (building_id);

-- 按学期筛选
CREATE INDEX IF NOT EXISTS idx_schedules_semester
    ON schedules (semester_id);

-- 同步状态
CREATE INDEX IF NOT EXISTS idx_sync_jobs_status
    ON sync_jobs (status, started_at DESC);

-- =============================================
-- 视图：空教室查询视图
-- =============================================
CREATE OR REPLACE VIEW v_available_rooms AS
SELECT
    r.id AS room_id,
    b.name AS building_name,
    r.room_number,
    r.capacity,
    r.floor
FROM rooms r
JOIN buildings b ON b.id = r.building_id
WHERE r.is_active = TRUE
  AND NOT EXISTS (
      SELECT 1 FROM schedules s
      WHERE s.room_id = r.id
        AND s.is_active = TRUE
  );
