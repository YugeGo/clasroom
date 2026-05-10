/**
 * ScheduleModal — 教室周课表热力图
 * 7天 × 5节次 矩阵，绿色=空闲 / 红色=有课
 */
import { FC, useEffect, useState } from "react";
import { X, Clock } from "lucide-react";
import type { RoomSlot } from "../api/chat";
import { PERIOD_LABELS, PERIOD_TIME_LABELS } from "../api/chat";
import { fetchRoomSchedule, type RoomSchedule } from "../api/local-engine";
import { loadData } from "../api/local-engine";

interface Props {
  roomName: string;
  campus: string;
  onClose: () => void;
}

const ALL_SLOTS = ["0102", "0304", "0506", "0708", "0910"];

export const ScheduleModal: FC<Props> = ({ roomName, campus, onClose }) => {
  const [schedule, setSchedule] = useState<RoomSchedule | null>(null);

  useEffect(() => {
    loadData().then((data) => {
      const s = fetchRoomSchedule(data, roomName, campus);
      setSchedule(s);
    });
  }, [roomName, campus]);

  // ESC 关闭
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  if (!schedule) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
          <p className="text-gray-500 dark:text-zinc-400">加载中...</p>
        </div>
      </div>
    );
  }

  const freeCount = schedule.days.reduce((s, d) => s + d.slots.filter((sl) => sl.free).length, 0);
  const totalCount = schedule.days.reduce((s, d) => s + d.slots.length, 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4" onClick={onClose}>
      <div
        className="bg-white dark:bg-zinc-900 rounded-2xl shadow-2xl w-full max-w-[720px] overflow-hidden animate-fade-in border border-gray-200 dark:border-zinc-800"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-zinc-100">
              {roomName}
            </h2>
            <p className="text-sm text-gray-500 dark:text-zinc-400">
              {campus} · 空闲 {freeCount}/{totalCount} 个时段
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-gray-100 dark:bg-zinc-800 flex items-center justify-center text-gray-500 dark:text-zinc-400 hover:text-gray-700 dark:hover:text-zinc-200 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* 课表网格 */}
        <div className="p-4 sm:p-6 overflow-x-auto">
          <div className="min-w-[500px]">
            {/* 表头：星期 */}
            <div className="grid grid-cols-[60px_repeat(7,1fr)] gap-1 mb-1">
              <div className="text-xs text-gray-400 dark:text-zinc-500 font-medium flex items-end pb-1">
                <Clock size={12} className="mr-1" />
                节次
              </div>
              {schedule.days.map((d) => (
                <div key={d.day} className="text-center text-xs font-medium text-gray-600 dark:text-zinc-300 pb-1">
                  {d.day.replace("星期", "周")}
                </div>
              ))}
            </div>

            {/* 每行 = 一个节次 */}
            {ALL_SLOTS.map((slot) => (
              <div key={slot} className="grid grid-cols-[60px_repeat(7,1fr)] gap-1 mb-1">
                <div className="text-[11px] text-gray-400 dark:text-zinc-500 font-mono flex items-center justify-end pr-2">
                  {PERIOD_TIME_LABELS[slot]?.split("-")[0]}
                </div>
                {schedule.days.map((d) => {
                  const s = d.slots.find((s) => s.slot === slot);
                  const free = s?.free ?? false;
                  return (
                    <div
                      key={`${d.day}-${slot}`}
                      title={`${d.day} ${PERIOD_LABELS[slot] ?? slot}: ${free ? "空闲" : "有课"}`}
                      className={`
                        h-9 sm:h-10 rounded-lg flex items-center justify-center
                        text-[11px] font-mono transition-all duration-200
                        ${free
                          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20"
                          : "bg-red-50 text-red-400 dark:bg-red-500/10 dark:text-red-400/60 border border-red-100 dark:border-red-500/10"
                        }
                      `}
                    >
                      {free ? "✓" : "—"}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>

          {/* 图例 */}
          <div className="flex items-center justify-center gap-4 mt-4 pt-3 border-t border-gray-100 dark:border-zinc-800">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded bg-emerald-100 dark:bg-emerald-500/15 border border-emerald-200 dark:border-emerald-500/20" />
              <span className="text-xs text-gray-500 dark:text-zinc-400">空闲</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded bg-red-50 dark:bg-red-500/10 border border-red-100 dark:border-red-500/10" />
              <span className="text-xs text-gray-500 dark:text-zinc-400">有课</span>
            </div>
            <span className="text-xs text-gray-400 dark:text-zinc-500">
              更新时间: 2026-05
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
