/**
 * RoomCard — 空教室结果卡片
 * 精确展示楼栋 + 教室号 + 时间段时间
 * 点击卡片弹出周课表热力图
 */
import { FC, useMemo } from "react";
import { Clock, CalendarDays, Building2 } from "lucide-react";
import type { GroupedRoom } from "../api/chat";
import { PERIOD_TIME_LABELS, PERIOD_LABELS } from "../api/chat";

interface Props {
  room: GroupedRoom;
  onScheduleClick?: (roomName: string, campus: string) => void;
}

function extractBuilding(roomName: string, campus: string): string {
  if (roomName.startsWith("实验楼")) return "实验楼";
  if (roomName.startsWith("操场")) return "操场";
  if (roomName.includes("-")) return roomName.split("-")[0] + "号楼";
  // 4位数字：首字为楼号
  if (/^\d{4}$/.test(roomName)) return roomName[0] + "号楼";
  return "";
}

export const RoomCard: FC<Props> = ({ room, onScheduleClick }) => {
  const building = useMemo(() => extractBuilding(room.room_name, room.campus), [room.room_name, room.campus]);

  return (
    <div
      className="group relative bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-xl overflow-hidden hover:border-blue-400 dark:hover:border-zinc-700 hover:shadow-md dark:hover:shadow-sm hover:-translate-y-0.5 transition-all duration-300 shadow-sm dark:shadow-none cursor-pointer"
      onClick={() => onScheduleClick?.(room.room_name, room.campus)}
    >
      {/* 顶部：校区色条 + 楼栋标签 */}
      <div className="flex items-center gap-2 px-4 pt-3 pb-1.5">
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400 border border-blue-100 dark:border-blue-500/20">
          {room.campus}
        </span>
        {building && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-gray-100 text-gray-500 dark:bg-zinc-800 dark:text-zinc-400 border border-gray-200 dark:border-zinc-700/50">
            <Building2 size={11} />
            {building}
          </span>
        )}
        <span className="ml-auto text-[11px] text-gray-400 dark:text-zinc-500 font-mono">
          {room.day_of_week.replace("星期", "周")}
        </span>
        <CalendarDays size={13} className="text-gray-300 dark:text-zinc-600 group-hover:text-blue-400 transition-colors" />
      </div>

      {/* 中间：教室号（大号突出） */}
      <div className="px-4 py-1">
        <span className="text-lg font-bold text-gray-900 dark:text-zinc-100 tracking-tight">
          {room.room_name}
        </span>
      </div>

      {/* 底部：时间段标签 */}
      <div className="px-4 pb-3 pt-1.5 flex flex-wrap gap-1.5">
        {room.period_slots.map((slot) => (
          <span
            key={slot}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/20 text-xs font-medium"
          >
            <Clock size={11} />
            <span>{PERIOD_LABELS[slot]?.replace("第 ", "").replace(" 节", "") ?? slot}</span>
            <span className="text-emerald-400 dark:text-emerald-400/50 mx-0.5">·</span>
            <span className="font-mono">{PERIOD_TIME_LABELS[slot]?.split("-")[0]}-{PERIOD_TIME_LABELS[slot]?.split("-")[1]}</span>
          </span>
        ))}
      </div>
    </div>
  );
};
