"""
山财空教室数据清洗入库脚本

读取教务系统课表 HTML（含双层表头的矩阵表格），
提取"空闲"单元格，批量存入 sdufe_free_rooms 表。

整合了架构文档附录中的 parse_sdufe_matrix 解析逻辑。

用法:
    python -m scripts.import_data                          # 扫描 ../data/*.html
    python -m scripts.import_data --dir ./data              # 指定目录
    python -m scripts.import_data --file ../data/yc.html    # 单个文件
    python -m scripts.import_data --file a.html --campus 章丘  # 强制指定校区
    python -m scripts.import_data --dry-run                 # 仅预览不写入
"""
import argparse
import asyncio
import glob
import os
import re
import sys
from collections import Counter
from typing import Optional

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup
from loguru import logger
from sqlalchemy import delete, insert, select

from app.config import settings
from app.database.models import SdufeFreeRoom
from app.database.session import async_session_factory

# ============================================================
# 映射表
# ============================================================

# 节次文本 → 短编码  (e.g. "1-2节" → "0102", "第3-4节" → "0304")
# 从配置的 SDUFE_PERIOD_SLOTS 反向构建
_PERIOD_SLOT_REVERSE: dict[str, str] = {}
for code, label in settings.SDUFE_PERIOD_SLOTS.items():
    # label 如 "第1-2节" → 取数字部分 "1-2"
    digits = re.sub(r"[^\d\-]", "", label)
    if digits:
        _PERIOD_SLOT_REVERSE[digits] = code

# 教务系统 HTML 中的节次编码 → 架构文档标准编码
# 山财强智系统使用 091011 表示第9-11节，映射到标准 0910
HTML_PERIOD_MAP: dict[str, str] = {
    "091011": "0910",
}

# 向下兼容的校区名映射
CAMPUS_ALIAS_MAP: dict[str, str] = {
    "圣井": "章丘",
    "燕山": "燕山",
    "舜耕": "舜耕",
    "章丘": "章丘",
}

# ============================================================
# 解析器 — 架构文档附录核心逻辑
# ============================================================

def parse_sdufe_matrix(html: str) -> list[dict]:
    """
    解析山财教务系统"双层表头"课表矩阵。

    表头结构:
        Row 0: 星期行 (colspan 展开，每个星期一列)
        Row 1: 节次行 (具体节次)
        Row 2+: 教室名 + 数据单元格

    数据单元格为空 = 该教室在该时段空闲。

    返回:
        [{"campus", "room", "day_of_week", "period_slot"}, ...]
    """
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")
    if len(rows) < 3:
        logger.warning(f"表格行数不足 ({len(rows)})，跳过")
        return []

    # ---- 第一层表头：星期映射 ----
    days_row = rows[0].find_all(["th", "td"])
    day_columns: list[str] = []
    for cell in days_row:
        text = cell.get_text(strip=True)
        colspan = int(cell.get("colspan", 1))
        if text and "星期" in text:
            day_columns.extend([text] * colspan)

    if not day_columns:
        logger.warning("未解析到星期表头，跳过")
        return []

    # ---- 第二层表头：节次映射 ----
    periods_row = rows[1].find_all(["th", "td"])
    period_columns: list[str] = [
        cell.get_text(strip=True)
        for cell in periods_row
        if cell.get_text(strip=True) and re.match(r"^\d{4,6}$", cell.get_text(strip=True))
    ]

    if not period_columns:
        logger.warning("未解析到节次表头，跳过")
        return []

    # ---- 数据行遍历 ----
    matrix_data: list[dict] = []
    skipped_no_room = 0
    skipped_unknown_campus = 0

    for row in rows[2:]:
        cells = row.find_all("td")
        if not cells:
            continue

        room_cell_text = cells[0].get_text(strip=True)
        if not room_cell_text:
            skipped_no_room += 1
            continue

        # 提取教室名和校区: "3号楼-402(舜耕)" 或 "5204(燕山）" (全角括号)
        match = re.match(r"(.*?)\(([^)]*?)\)", room_cell_text) or \
                re.match(r"(.*?)（([^）]*?)）", room_cell_text)
        room_name = match.group(1).strip() if match else room_cell_text
        campus_name = match.group(2).strip() if match else ""

        # 跳过未知校区的记录
        campus_mapped = CAMPUS_ALIAS_MAP.get(campus_name)
        if not campus_mapped:
            skipped_unknown_campus += 1
            continue

        for i in range(len(period_columns)):
            cell_index = i + 1
            if cell_index >= len(cells):
                continue

            cell_content = cells[cell_index].get_text(strip=True)

            # 核心逻辑：格子为空 = 空教室！
            if not cell_content:
                day_val = day_columns[i] if i < len(day_columns) else ""
                period_text = period_columns[i]

                # 节次文本 → 短编码
                period_code = _map_period_slot(period_text)
                if not period_code:
                    continue

                matrix_data.append({
                    "campus": campus_mapped,
                    "room": room_name,
                    "day_of_week": day_val,
                    "period_slot": period_code,
                })

    logger.info(
        f"解析完成: {len(matrix_data)} 条空闲记录"
        f" (跳过无教室名: {skipped_no_room}, 未知校区: {skipped_unknown_campus})"
    )
    return matrix_data


def _map_period_slot(text: str) -> Optional[str]:
    """将节次文本映射为短编码

    支持两种格式:
      - 教务系统直接编码: "0102", "091011" → "0102", "0910"
      - 口语文本: "1-2节" → "0102", "第3-4节" → "0304"
    """
    # 先尝试直接编码匹配（如 "091011" → "0910"）
    if text in HTML_PERIOD_MAP:
        return HTML_PERIOD_MAP[text]
    if text in settings.SDUFE_PERIOD_SLOTS:
        return text

    # 再尝试口语文本映射
    digits = re.sub(r"[^\d\-]", "", text)
    if not digits:
        return None
    return _PERIOD_SLOT_REVERSE.get(digits)


# ============================================================
# 文件扫描与加载
# ============================================================

def find_html_files(path: str) -> list[str]:
    """递归查找 .html / .htm 文件"""
    if os.path.isfile(path):
        return [path]

    if os.path.isdir(path):
        files = []
        for ext in ("*.html", "*.htm"):
            files.extend(glob.glob(os.path.join(path, ext)))
            files.extend(glob.glob(os.path.join(path, "**", ext), recursive=True))
        # 去重
        return sorted(set(files))

    logger.warning(f"路径不存在: {path}")
    return []


def load_and_parse(file_paths: list[str]) -> list[dict]:
    """加载多个 HTML 文件并解析"""
    all_records: list[dict] = []
    file_stats: list[tuple[str, int]] = []

    for fp in file_paths:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                html = f.read()
        except Exception as e:
            logger.error(f"读取失败 {fp}: {e}")
            continue

        records = parse_sdufe_matrix(html)
        all_records.extend(records)
        file_stats.append((os.path.basename(fp), len(records)))
        logger.info(f"  {os.path.basename(fp)}: {len(records)} 条空闲记录")

    # 打印汇总
    total = sum(s[1] for s in file_stats)
    if file_stats:
        logger.info(f"文件汇总: {len(file_stats)} 个文件, {total} 条记录")
    return all_records


# ============================================================
# 清洗与去重
# ============================================================

def clean_and_dedup(records: list[dict]) -> list[dict]:
    """去重并清洗数据"""
    seen: set[tuple] = set()
    cleaned: list[dict] = []
    dup_count = 0

    for r in records:
        key = (r["campus"], r["room"], r["day_of_week"], r["period_slot"])
        if key in seen:
            dup_count += 1
            continue
        seen.add(key)
        cleaned.append(r)

    if dup_count:
        logger.info(f"去重: 移除 {dup_count} 条重复记录")

    return cleaned


# ============================================================
# 数据库批量写入
# ============================================================

async def batch_insert(records: list[dict], batch_size: int = 500) -> dict:
    """批量写入 sdufe_free_rooms，返回统计信息"""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    if not records:
        return {"inserted": 0, "total": 0}

    async with async_session_factory() as session:
        # 先清空旧数据（全量刷新）
        await session.execute(delete(SdufeFreeRoom))

        # 分批插入
        total = len(records)
        inserted = 0
        for i in range(0, total, batch_size):
            batch = records[i : i + batch_size]
            stmt = pg_insert(SdufeFreeRoom).values([
                {
                    "campus": r["campus"],
                    "room_name": r["room"],
                    "day_of_week": r["day_of_week"],
                    "period_slot": r["period_slot"],
                }
                for r in batch
            ])
            # 防重复：若同一记录已存在则跳过
            stmt = stmt.on_conflict_do_nothing()
            await session.execute(stmt)
            inserted += len(batch)

        await session.commit()

    return {"inserted": inserted, "total": total}


# ============================================================
# JSON 导出（无需数据库）
# ============================================================

def export_to_json(records: list[dict], output_path: str):
    """将解析后的数据导出为 JSON 文件，供前端/Mock 模式加载"""
    import json
    # 格式化为前端需要的结构
    export_data = [
        {
            "campus": r["campus"],
            "room_name": r["room"],
            "day_of_week": r["day_of_week"],
            "period_slot": r["period_slot"],
        }
        for r in records
    ]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    logger.info(f"✅ 已导出 {len(export_data)} 条记录到 {output_path}")


# ============================================================
# 预览（dry-run）
# ============================================================

def print_preview(records: list[dict]):
    """打印预览统计"""
    if not records:
        logger.info("(无记录)")
        return

    # 按校区统计
    by_campus = Counter(r["campus"] for r in records)
    # 按星期统计
    by_day = Counter(r["day_of_week"] for r in records)
    # 按期次统计
    by_period = Counter(r["period_slot"] for r in records)

    logger.info(f"共 {len(records)} 条空闲记录")
    logger.info("")

    logger.info("按校区:")
    for campus, count in sorted(by_campus.items()):
        logger.info(f"  {campus}: {count} 条")

    logger.info("按星期:")
    for day, count in sorted(by_day.items()):
        logger.info(f"  {day}: {count} 条")

    logger.info("按节次:")
    for period, count in sorted(by_period.items()):
        label = settings.SDUFE_PERIOD_SLOTS.get(period, period)
        logger.info(f"  {label} ({period}): {count} 条")

    logger.info("")
    logger.info("前 10 条示例:")
    for r in records[:10]:
        logger.info(f"  [{r['campus']}] {r['room']}  {r['day_of_week']}  {r['period_slot']}")


# ============================================================
# CLI
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="山财空教室数据清洗入库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python -m scripts.import_data\n"
            "  python -m scripts.import_data --dir ../data\n"
            "  python -m scripts.import_data --file ../data/sdufe_schedule.html --dry-run\n"
            "  python -m scripts.import_data --to-json ../data/sdufe_rooms.json\n"
        ),
    )
    parser.add_argument("--dir", default="", help="HTML 文件所在目录 (默认: ../data)")
    parser.add_argument("--file", default="", help="单个 HTML 文件路径")
    parser.add_argument("--dry-run", action="store_true", help="仅预览不写入数据库")
    parser.add_argument("--to-json", default="", help="导出为 JSON 文件路径（替代数据库写入）")
    return parser.parse_args()


def main():
    args = parse_args()

    # 确定文件路径
    if args.file:
        file_paths = find_html_files(args.file)
    else:
        data_dir = args.dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
        )
        file_paths = find_html_files(data_dir)

    if not file_paths:
        logger.warning("未找到任何 HTML 文件")
        logger.info("请将教务系统课表页面保存为 HTML 文件放在 data/ 目录下")
        return

    logger.info(f"找到 {len(file_paths)} 个 HTML 文件:")
    for fp in file_paths:
        logger.info(f"  {fp}")

    # 解析
    raw_records = load_and_parse(file_paths)
    if not raw_records:
        logger.warning("未解析到任何空闲教室记录")
        return

    # 清洗去重
    records = clean_and_dedup(raw_records)

    # 预览
    print_preview(records)

    # dry-run
    if args.dry_run:
        logger.info("[DRY-RUN] 未写入数据库")
        return

    # 导出 JSON
    if args.to_json:
        export_to_json(records, args.to_json)
        return

    # 写入数据库
    stats = asyncio.run(batch_insert(records))
    logger.info(
        f"✅ 导入完成: {stats['total']} 条入库"
        f" (sdufe_free_rooms 表)"
    )


if __name__ == "__main__":
    main()
