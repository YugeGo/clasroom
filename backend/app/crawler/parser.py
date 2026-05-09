"""
教务系统课表 HTML 解析器

将教务系统导出的课表 HTML 表格/JSON 解析为标准化数据结构。
支持常见的正方、强智、URP 系统的表格格式。

输出格式 (ScheduleRecord):
  {
    "building_name": "3号楼",
    "room_number": "402",
    "day_of_week": 1,        # 1=周一 … 7=周日
    "start_period": 1,       # 起始节次 (1-13)
    "end_period": 2,         # 结束节次
    "course_name": "高等数学",
    "teacher": "张三",
    "weeks": "1-16"          # 上课周次
  }
"""
import re
from typing import Optional

from bs4 import BeautifulSoup
from loguru import logger


class ScheduleRecord:
    """单条排课记录"""

    def __init__(
        self,
        building_name: str = "",
        room_number: str = "",
        day_of_week: int = 0,
        start_period: int = 0,
        end_period: int = 0,
        course_name: str = "",
        teacher: str = "",
        weeks: str = "",
    ):
        self.building_name = building_name
        self.room_number = room_number
        self.day_of_week = day_of_week
        self.start_period = start_period
        self.end_period = end_period
        self.course_name = course_name
        self.teacher = teacher
        self.weeks = weeks

    def to_dict(self) -> dict:
        return {
            "building_name": self.building_name,
            "room_number": self.room_number,
            "day_of_week": self.day_of_week,
            "start_period": self.start_period,
            "end_period": self.end_period,
            "course_name": self.course_name,
            "teacher": self.teacher,
            "weeks": self.weeks,
        }

    def __repr__(self):
        return (
            f"<{self.building_name}-{self.room_number} "
            f"周{self.day_of_week} 第{self.start_period}-{self.end_period}节 "
            f"{self.course_name}>"
        )


class ScheduleParser:
    """课表 HTML 解析器 — 工厂模式，根据系统类型分发"""

    @staticmethod
    def create(system_type: str = ""):
        if system_type == "zhengfang":
            return ZhengFangParser()
        elif system_type == "qiangzhi":
            return QiangZhiParser()
        elif system_type == "urp":
            return URPParser()
        return GenericParser()

    def parse(self, html: str, building: str = "", room: str = "") -> list[dict]:
        raise NotImplementedError


class ZhengFangParser(ScheduleParser):
    """正方教务系统表格解析器

    正方系统课表 HTML 结构特征:
      - <table> 包含 7 列 (周一~周日)
      - 每行代表一个节次 (1-2节, 3-4节, ...)
      - 单元格内容: "课程名\n教师\n(周次)\n教室"
    """

    DAY_MAP = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7}

    def parse(self, html: str, building: str = "", room: str = "") -> list[dict]:
        records = []
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        if not table:
            logger.warning("未找到课表表格")
            return records

        rows = table.find_all("tr")
        # 跳过表头行
        period_map = {"1-2": (1, 2), "3-4": (3, 4), "5-6": (5, 6),
                       "7-8": (7, 8), "9-10": (9, 10), "11-13": (11, 13)}

        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            # 第一列是节次说明
            period_text = cells[0].get_text(strip=True)
            periods = self._parse_period(period_text, period_map)
            if not periods:
                continue

            start_p, end_p = periods

            # 第1~7列对应周一~周日
            for col_idx in range(1, min(len(cells), 8)):
                cell = cells[col_idx]
                content = cell.get_text("\n", strip=True)
                if not content or content == " ":
                    continue

                parsed = self._parse_cell_content(content)
                if parsed:
                    parsed["day_of_week"] = self.DAY_MAP.get(col_idx - 1, col_idx)
                    parsed["start_period"] = start_p
                    parsed["end_period"] = end_p
                    if building:
                        parsed["building_name"] = building
                    records.append(parsed)

        logger.info(f"正方解析器: 提取到 {len(records)} 条排课记录")
        return records

    def _parse_period(self, text: str, period_map: dict) -> Optional[tuple]:
        for key, (start, end) in period_map.items():
            if key in text:
                return (start, end)
        # 尝试正则匹配 "第X-Y节"
        m = re.search(r"(\d+)-(\d+)", text)
        if m:
            return (int(m.group(1)), int(m.group(2)))
        return None

    def _parse_cell_content(self, content: str) -> Optional[dict]:
        """解析单元格内的多行文本"""
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        if len(lines) < 1:
            return None

        record = {
            "course_name": "",
            "teacher": "",
            "room_number": "",
            "weeks": "",
        }

        # 正方典型格式: "高等数学\n张三\n(1-16周)\n3号楼402"
        for line in lines:
            # 周次: (1-16周) 或 1-16
            if re.match(r"^[\(（]?\d+[-–]\d+[周]?[\)）]?", line):
                record["weeks"] = re.sub(r"[\(\)（）]", "", line)
            # 楼栋+教室: 包含"楼"或纯数字/字母
            elif "楼" in line or re.match(r"^[A-Z]?\d{2,4}[A-Z]?$", line):
                room = self._parse_room(line)
                if room:
                    record["room_number"] = room
            # 教师名: 2-4个中文字符
            elif re.match(r"^[一-龥]{2,4}$", line):
                record["teacher"] = line
            # 课程名
            else:
                record["course_name"] = line

        if not record["course_name"]:
            return None
        return record

    def _parse_room(self, text: str) -> str:
        """从文本中提取教室号"""
        m = re.search(r"(\d+号楼)?\s*(\d{2,5}[A-Za-z]?)", text)
        if m:
            return m.group(2)
        return text


class QiangZhiParser(ScheduleParser):
    """强智教务系统解析器 (占位，结构与正方类似)"""

    def parse(self, html: str, building: str = "", room: str = "") -> list[dict]:
        logger.info("强智解析器暂用通用逻辑")
        return GenericParser().parse(html, building, room)


class URPParser(ScheduleParser):
    """URP 教务系统解析器 (占位)"""

    def parse(self, html: str, building: str = "", room: str = "") -> list[dict]:
        logger.info("URP 解析器暂用通用逻辑")
        return GenericParser().parse(html, building, room)


class GenericParser(ScheduleParser):
    """通用解析器：尝试从各种表格结构中提取数据"""

    DAY_CN = {"周一": 1, "周二": 2, "周三": 3, "周四": 4,
              "周五": 5, "周六": 6, "周日": 7}

    def parse(self, html: str, building: str = "", room: str = "") -> list[dict]:
        records = []
        soup = BeautifulSoup(html, "lxml")

        # 尝试所有 <table>
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                text = " ".join(c.get_text(strip=True) for c in cells)
                if not text.strip():
                    continue

                record = self._parse_line(text, building)
                if record:
                    records.append(record)

        logger.info(f"通用解析器: 提取到 {len(records)} 条记录")
        return records

    def _parse_line(self, text: str, building: str = "") -> Optional[dict]:
        """用正则从一行文本中提取课程信息"""
        rec = {}

        # 提取星期
        for cn, num in self.DAY_CN.items():
            if cn in text:
                rec["day_of_week"] = num
                break

        # 提取节次 "第X-Y节" / "X-Y节"
        m = re.search(r"第?(\d+)[-–](\d+)节?", text)
        if m:
            rec["start_period"] = int(m.group(1))
            rec["end_period"] = int(m.group(2))

        # 提取课程名 (位于"楼"字之后或开头的中英文混合)
        m = re.search(r"([一-龥\w]{2,30}?)\(?[\d-]+周?", text)
        if m:
            rec["course_name"] = m.group(1)

        # 教室号
        m = re.search(r"(\d{2,5})\s*室?", text)
        if m:
            rec["room_number"] = m.group(1)

        if building:
            rec["building_name"] = building

        # 必须有课程名才算有效记录
        if "course_name" in rec and "day_of_week" in rec:
            return rec
        return None
