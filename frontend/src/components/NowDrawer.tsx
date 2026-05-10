/**
 * NowDrawer — 「现在有空教室吗」多层抽屉交互
 *
 * 点击触发 → 选校区 → 选楼栋 → 显示当前空闲教室
 * 节次自动检测当前时间。
 */
import { FC, useState, useEffect, useCallback } from "react";
import { X, ChevronRight, School, Building2, DoorOpen, Clock, Loader2 } from "lucide-react";
import { fetchRoomSchedule, type RoomSchedule } from "../api/local-engine";
import { loadData } from "../api/local-engine";
import type { RoomSlot } from "../api/chat";
import { PERIOD_LABELS, PERIOD_TIME_LABELS } from "../api/chat";

// 当前时间节次映射（同 local-engine.ts）
function getCurrentPeriodSlots(): string[] {
  const now = new Date();
  const total = now.getHours() * 60 + now.getMinutes();
  if (total >= 8 * 60 + 0 && total < 9 * 60 + 35) return ["0102"];
  if (total >= 9 * 60 + 35 && total < 9 * 60 + 50) return ["0102", "0304"];
  if (total >= 9 * 60 + 50 && total < 11 * 60 + 25) return ["0304"];
  if (total >= 11 * 60 + 25 && total < 13 * 60 + 30) return [];
  if (total >= 13 * 60 + 30 && total < 15 * 60 + 5) return ["0506"];
  if (total >= 15 * 60 + 5 && total < 15 * 60 + 20) return ["0506", "0708"];
  if (total >= 15 * 60 + 20 && total < 16 * 60 + 55) return ["0708"];
  if (total >= 16 * 60 + 55 && total < 18 * 60 + 30) return [];
  if (total >= 18 * 60 + 30) return ["0910"];
  return [];
}

const WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"];
const PERIOD_LABEL_MAP: Record<string, string> = {
  "0102": "第1-2节", "0304": "第3-4节", "0506": "第5-6节", "0708": "第7-8节", "0910": "第9-10节",
};

interface Props {
  onClose: () => void;
}

type Step = "campuses" | "buildings" | "rooms";

// 从教室名提取楼栋
function extractBld(roomName: string): string {
  if (roomName.startsWith("实验楼")) return "实验楼";
  if (roomName.includes("-")) return roomName.split("-")[0] + "号楼";
  if (/^\d{4}$/.test(roomName)) return roomName[0] + "号楼";
  return roomName;
}

export const NowDrawer: FC<Props> = ({ onClose }) => {
  const [step, setStep] = useState<Step>("campuses");
  const [data, setData] = useState<RoomSlot[]>([]);
  const [selectedCampus, setSelectedCampus] = useState("");
  const [selectedBld, setSelectedBld] = useState("");
  const [loading, setLoading] = useState(true);

  const currentSlots = getCurrentPeriodSlots();
  const today = WEEKDAY_CN[new Date().getDay() === 0 ? 6 : new Date().getDay() - 1];

  useEffect(() => {
    loadData().then((d) => { setData(d); setLoading(false); });
  }, []);

  // 各校区楼栋列表
  const getBuildings = useCallback((campus: string) => {
    const blds = new Set<string>();
    for (const r of data) {
      if (r.campus !== campus) continue;
      blds.add(extractBld(r.room_name));
    }
    return [...blds].sort();
  }, [data]);

  // 当前空闲的房间
  const getFreeRooms = useCallback((campus: string, bld: string) => {
    return data.filter((r) => {
      if (r.campus !== campus) return false;
      if (r.day_of_week !== today) return false;
      if (!currentSlots.includes(r.period_slot)) return false;
      if (extractBld(r.room_name) !== bld) return false;
      return true;
    });
  }, [data, today, currentSlots]);

  const campuses = ["舜耕", "燕山", "章丘"];

  // ESC 关闭
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const periodLabel = currentSlots.length > 0
    ? currentSlots.map((s) => PERIOD_LABEL_MAP[s] || s).join("、")
    : "休息时间";

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center" onClick={onClose}>
      {/* 遮罩 */}
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />

      {/* 抽屉面板 */}
      <div
        className="relative bg-white dark:bg-zinc-900 rounded-t-2xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-hidden animate-slide-up border-t border-gray-200 dark:border-zinc-800"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-zinc-800">
          <div className="flex items-center gap-2">
            <Clock size={16} className="text-blue-500" />
            <span className="font-semibold text-gray-900 dark:text-zinc-100 text-sm">现在有空教室</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 font-mono">
              {periodLabel}
            </span>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-zinc-800 text-gray-400">
            <X size={18} />
          </button>
        </div>

        {/* 面包屑 */}
        <div className="flex items-center gap-1 px-5 py-2 text-xs text-gray-400 dark:text-zinc-500">
          <button onClick={() => { setStep("campuses"); setSelectedCampus(""); setSelectedBld(""); }}
            className="hover:text-gray-700 dark:hover:text-zinc-300">
            校区
          </button>
          {selectedCampus && (
            <>
              <ChevronRight size={12} />
              <button onClick={() => { setStep("buildings"); setSelectedBld(""); }}
                className="hover:text-gray-700 dark:hover:text-zinc-300">
                {selectedCampus}
              </button>
            </>
          )}
          {selectedBld && (
            <><ChevronRight size={12} /><span className="text-gray-700 dark:text-zinc-300">{selectedBld}</span></>
          )}
        </div>

        {/* 内容 */}
        <div className="overflow-y-auto px-5 pb-6" style={{ maxHeight: "calc(80vh - 120px)" }}>
          {loading ? (
            <div className="flex items-center justify-center py-12 text-gray-400">
              <Loader2 size={20} className="animate-spin mr-2" /> 加载中...
            </div>
          ) : step === "campuses" ? (
            <div className="space-y-2">
              {campuses.map((c) => {
                const count = getFreeRooms(c, "").length;
                // 实际上 getFreeRooms 需要 building 参数，这里只是展示
                const bldCount = getBuildings(c).length;
                return (
                  <button key={c}
                    onClick={() => { setSelectedCampus(c); setStep("buildings"); }}
                    className="w-full flex items-center gap-3 bg-gray-50 dark:bg-zinc-800/50 rounded-xl px-4 py-3.5 hover:bg-gray-100 dark:hover:bg-zinc-800 transition-colors text-left"
                  >
                    <span className="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-500/10 flex items-center justify-center text-blue-500 dark:text-blue-400">
                      <School size={20} />
                    </span>
                    <div className="flex-1">
                      <p className="font-medium text-gray-900 dark:text-zinc-200">{c}</p>
                      <p className="text-xs text-gray-500 dark:text-zinc-400">{bldCount} 栋教学楼</p>
                    </div>
                    <ChevronRight size={18} className="text-gray-300 dark:text-zinc-600" />
                  </button>
                );
              })}
            </div>
          ) : step === "buildings" ? (
            <div className="space-y-1.5">
              {getBuildings(selectedCampus).map((b) => {
                const freeRooms = getFreeRooms(selectedCampus, b);
                return (
                  <button key={b}
                    onClick={() => { setSelectedBld(b); setStep("rooms"); }}
                    className="w-full flex items-center gap-3 bg-gray-50 dark:bg-zinc-800/50 rounded-xl px-4 py-3 hover:bg-gray-100 dark:hover:bg-zinc-800 transition-colors text-left"
                  >
                    <Building2 size={18} className="text-gray-400 dark:text-zinc-500" />
                    <div className="flex-1">
                      <p className="font-medium text-gray-900 dark:text-zinc-200 text-sm">{b}</p>
                      <p className="text-xs text-gray-500 dark:text-zinc-400">
                        {freeRooms.length > 0
                          ? `${freeRooms.length} 间当前空闲`
                          : "当前暂无空闲教室"}
                      </p>
                    </div>
                    {freeRooms.length > 0 && (
                      <span className="text-xs font-mono text-emerald-500 bg-emerald-50 dark:bg-emerald-500/10 px-2 py-0.5 rounded-full">
                        {freeRooms.length}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          ) : (
            /* 房间列表 */
            <div className="space-y-2">
              {(() => {
                const rooms = getFreeRooms(selectedCampus, selectedBld);
                if (rooms.length === 0) {
                  return (
                    <div className="text-center py-12 text-gray-400 dark:text-zinc-500">
                      <DoorOpen size={32} className="mx-auto mb-2 opacity-40" />
                      <p className="text-sm">{selectedBld} 当前暂无空闲教室</p>
                    </div>
                  );
                }
                // 按教室名分组
                const byRoom = new Map<string, { room: string; slots: string[] }>();
                for (const r of rooms) {
                  if (!byRoom.has(r.room_name)) {
                    byRoom.set(r.room_name, { room: r.room_name, slots: [] });
                  }
                  byRoom.get(r.room_name)!.slots.push(r.period_slot);
                }
                return [...byRoom.values()].sort((a, b) => a.room.localeCompare(b.room)).map((item) => (
                  <div key={item.room}
                    className="bg-gray-50 dark:bg-zinc-800/50 rounded-xl px-4 py-3 border border-gray-100 dark:border-zinc-800"
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-semibold text-gray-900 dark:text-zinc-200">{item.room}</span>
                      <span className="text-xs text-gray-400 dark:text-zinc-500 font-mono">{today}</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {item.slots.sort().map((s) => (
                        <span key={s} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20">
                          <Clock size={10} />
                          {PERIOD_LABELS[s] || s}
                          <span className="text-emerald-300 dark:text-emerald-500/50">|</span>
                          {PERIOD_TIME_LABELS[s] || s}
                        </span>
                      ))}
                    </div>
                  </div>
                ));
              })()}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
