/**
 * RoomCard — 空教室结果卡片（极客风）
 * 展示教室名 + 校区 Tag + 空闲节次标签
 */
import { FC } from "react";
import { Clock, MapPin } from "lucide-react";
import type { GroupedRoom } from "../api/chat";
import { CAMPUS_COLORS, PERIOD_TIME_LABELS, PERIOD_LABELS } from "../api/chat";

interface Props {
  room: GroupedRoom;
}

export const RoomCard: FC<Props> = ({ room }) => {
  return (
    <div className="group relative bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-xl p-4 hover:border-blue-400 dark:hover:border-zinc-700 hover:shadow-md dark:hover:shadow-sm hover:-translate-y-1 transition-all duration-300 shadow-sm dark:shadow-none">
      {/* 第一行：校区 Tag + 教室名 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-600 border border-gray-200 dark:bg-zinc-800 dark:text-zinc-400 dark:border-zinc-700/50 transition-colors duration-300">
            <MapPin size={12} />
            {room.campus}
          </span>
          <span className="text-base font-semibold text-gray-900 dark:text-zinc-200 truncate transition-colors duration-300">
            {room.room_name}
          </span>
        </div>
        <span className="text-xs text-gray-500 dark:text-zinc-500 font-medium transition-colors duration-300">{room.day_of_week}</span>
      </div>

      {/* 第二行：空闲节次标签 */}
      <div className="flex flex-wrap gap-2">
        {room.period_slots.map((slot) => (
          <span
            key={slot}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-blue-50 text-blue-600 border border-blue-100 dark:bg-blue-500/10 dark:text-blue-400 dark:border-blue-500/20 text-xs font-medium transition-colors duration-300"
          >
            <Clock size={12} className="opacity-70" />
            {PERIOD_LABELS[slot] ?? slot}
            <span className="text-blue-300 dark:text-blue-400/40 mx-0.5">|</span>
            <span className="opacity-80">{PERIOD_TIME_LABELS[slot] ?? slot}</span>
          </span>
        ))}
      </div>
    </div>
  );
};
