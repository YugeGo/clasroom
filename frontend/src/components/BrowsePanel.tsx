/**
 * BrowsePanel — 浏览查找模式
 * 校园 → 楼栋 → 教室 三层导航，点击教室后查询空闲时段
 */
import { FC, useState, useEffect, useCallback } from "react";
import {
  Building2,
  ChevronRight,
  DoorOpen,
  School,
  Clock,
  Loader2,
} from "lucide-react";
import { localFetchCampuses, localFetchBuildings, localFetchRooms, localSendChatMessage } from "../api/local-engine";
import { groupRooms } from "../api/chat";
import { RoomCard } from "./RoomCard";

interface Props {
  onQueryResult: (groups: any[], summary: string) => void;
  onScheduleClick?: (roomName: string, campus: string) => void;
}

type Step = "campus" | "building" | "room" | "result";

export const BrowsePanel: FC<Props> = ({ onQueryResult, onScheduleClick }) => {
  const [step, setStep] = useState<Step>("campus");
  const [campuses, setCampuses] = useState<any[]>([]);
  const [buildings, setBuildings] = useState<any[]>([]);
  const [rooms, setRooms] = useState<string[]>([]);
  const [selectedCampus, setSelectedCampus] = useState<string>("");
  const [selectedBuilding, setSelectedBuilding] = useState<string>("");
  const [selectedRoom, setSelectedRoom] = useState<string>("");
  const [selectedDay, setSelectedDay] = useState<string>("");
  const [loading, setLoading] = useState(false);

  // 本地结果状态（为了在 browse 模式中直接展示）
  const [resultGroups, setResultGroups] = useState<any[]>([]);
  const [resultSummary, setResultSummary] = useState<string>("");
  const [resultContent, setResultContent] = useState<string>("");

  // 星期选择
  const weekDays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"];
  const today = new Date().getDay();
  const todayCn = weekDays[today === 0 ? 6 : today - 1];

  useEffect(() => {
    setSelectedDay(todayCn);
    localFetchCampuses().then(setCampuses);
  }, []);

  const handleCampusClick = useCallback(async (name: string) => {
    setSelectedCampus(name);
    setLoading(true);
    const blds = await localFetchBuildings(name);
    setBuildings(blds);
    setSelectedBuilding("");
    setSelectedRoom("");
    setStep("building");
    setLoading(false);
  }, []);

  const handleBuildingClick = useCallback(async (name: string) => {
    setSelectedBuilding(name);
    setLoading(true);
    const rms = await localFetchRooms(selectedCampus, name);
    setRooms(rms);
    setSelectedRoom("");
    setStep("room");
    setLoading(false);
  }, [selectedCampus]);

  const handleRoomQuery = useCallback(async (roomName: string) => {
    setSelectedRoom(roomName);
    setLoading(true);
    setStep("result");
    try {
      // 用楼栋显示名代替原始 key（"4" → "4号楼"），让解析器能识别
      const bld = buildings.find((b) => b.name === selectedBuilding);
      const bldName = bld?.display_name || selectedBuilding;
      const data = await localSendChatMessage(
        `${selectedCampus} ${bldName} ${roomName} ${selectedDay} 有空吗`
      );
      const groups = groupRooms(data.rooms);
      const summary = `[${selectedCampus}] ${roomName} · ${selectedDay}`;
      
      setResultGroups(groups);
      setResultSummary(summary);
      setResultContent(data.count === 0 ? "该教室在所选时间无空闲时段" : "");
      
      onQueryResult(groups, summary);
    } catch {
      setResultGroups([]);
      setResultSummary("查询失败");
      setResultContent("查询时发生错误，请稍后重试");
      onQueryResult([], "查询失败");
    }
    setLoading(false);
  }, [selectedCampus, selectedBuilding, selectedDay, onQueryResult]);

  const reset = useCallback(() => {
    setStep("campus");
    setSelectedCampus("");
    setSelectedBuilding("");
    setSelectedRoom("");
  }, []);

  return (
    <div className="p-4 space-y-6 max-w-3xl mx-auto">
      {/* 面包屑导航 */}
      <div className="flex items-center gap-2 text-sm font-medium text-gray-500 dark:text-zinc-500 transition-colors duration-300">
        <button onClick={reset} className="hover:text-gray-900 dark:hover:text-zinc-300 transition-colors">校区选择</button>
        {selectedCampus && (
          <>
            <ChevronRight size={14} className="opacity-50" />
            <button onClick={() => { setStep("building"); setSelectedBuilding(""); }} className="hover:text-gray-900 dark:hover:text-zinc-300 transition-colors">{selectedCampus}</button>
          </>
        )}
        {selectedBuilding && (
          <>
            <ChevronRight size={14} className="opacity-50" />
            <button onClick={() => setStep("room")} className="hover:text-gray-900 dark:hover:text-zinc-300 transition-colors">{selectedBuilding}</button>
          </>
        )}
      </div>

      {/* 步骤面板 */}
      {step === "campus" && (
        <div className="space-y-3 animate-fade-in">
          <p className="text-xs text-gray-400 dark:text-zinc-500 font-medium uppercase tracking-wider transition-colors duration-300">选择校区</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {campuses.map((c) => {
              return (
                <button
                  key={c.name}
                  onClick={() => handleCampusClick(c.name)}
                  className="group flex items-center gap-4 bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-2xl p-4 hover:border-blue-400 dark:hover:border-zinc-700 hover:shadow-md dark:hover:shadow-sm hover:-translate-y-1 transition-all duration-300 text-left shadow-sm dark:shadow-none"
                >
                  <span className="w-12 h-12 rounded-xl bg-gray-50 dark:bg-zinc-800 flex items-center justify-center text-gray-500 dark:text-zinc-400 border border-gray-100 dark:border-zinc-700/50 group-hover:text-blue-500 dark:group-hover:text-blue-400 group-hover:border-blue-200 dark:group-hover:border-blue-500/30 transition-colors duration-300">
                    <School size={24} />
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-gray-900 dark:text-zinc-200 font-semibold text-[15px] transition-colors duration-300">{c.name}</p>
                    <p className="text-xs text-gray-500 dark:text-zinc-500 mt-0.5 transition-colors duration-300">{c.building_count} 栋教学楼 · {c.room_count} 间教室</p>
                  </div>
                  <ChevronRight size={18} className="text-gray-300 dark:text-zinc-600 group-hover:text-blue-400 dark:group-hover:text-zinc-400 transition-colors" />
                </button>
              );
            })}
          </div>
        </div>
      )}

      {step === "building" && (
        <div className="space-y-3 animate-fade-in">
          <p className="text-xs text-gray-400 dark:text-zinc-500 font-medium uppercase tracking-wider transition-colors duration-300">
            {selectedCampus} · 选择教学楼
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {buildings.map((b) => (
              <button
                key={b.name}
                onClick={() => handleBuildingClick(b.name)}
                className="group flex items-center gap-3 bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-xl p-3.5 hover:border-blue-400 dark:hover:border-zinc-700 hover:shadow-md dark:hover:shadow-sm hover:-translate-y-1 transition-all duration-300 text-left shadow-sm dark:shadow-none"
              >
                <Building2 size={18} className="text-gray-400 dark:text-zinc-500 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors" />
                <div className="flex-1 min-w-0">
                  <p className="text-gray-800 dark:text-zinc-200 text-[15px] font-medium truncate transition-colors duration-300">{b.display_name || b.name}</p>
                  <p className="text-xs text-gray-400 dark:text-zinc-500 mt-0.5 transition-colors duration-300">{b.room_count} 间</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {step === "room" && (
        <div className="space-y-4 animate-fade-in">
          <p className="text-xs text-gray-400 dark:text-zinc-500 font-medium uppercase tracking-wider transition-colors duration-300">
            {selectedCampus} · {selectedBuilding} · 选择教室与时间
          </p>

          {/* 星期选择 */}
          <div className="flex gap-2 flex-wrap mb-2">
            {weekDays.map((d) => (
              <button
                key={d}
                onClick={() => setSelectedDay(d)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-300 hover:-translate-y-0.5 ${
                  d === selectedDay
                    ? "bg-blue-500 text-white shadow-sm dark:bg-blue-500/20 dark:text-blue-400 border border-transparent dark:border-blue-500/30"
                    : "bg-white text-gray-600 border border-gray-200 hover:text-gray-900 hover:border-gray-300 dark:bg-zinc-900 dark:text-zinc-400 dark:border-zinc-800 dark:hover:text-zinc-200 dark:hover:border-zinc-700 shadow-sm dark:shadow-none"
                }`}
              >
                {d}
              </button>
            ))}
          </div>

          {/* 教室列表 */}
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {rooms.map((r) => (
              <button
                key={r}
                onClick={() => handleRoomQuery(r)}
                className={`flex items-center gap-2 px-3 py-2.5 rounded-xl text-left transition-all duration-300 hover:-translate-y-0.5 hover:shadow-sm ${
                  selectedRoom === r
                    ? "bg-blue-50 text-blue-600 border border-blue-200 dark:bg-blue-500/20 dark:text-blue-400 dark:border-blue-500/30"
                    : "bg-white text-gray-700 border border-gray-100 hover:bg-gray-50 hover:border-gray-200 dark:bg-zinc-900 dark:text-zinc-400 dark:border-zinc-800 dark:hover:bg-zinc-800 dark:hover:text-zinc-200 shadow-sm dark:shadow-none"
                }`}
              >
                <DoorOpen size={16} className="opacity-50" />
                <span className="text-sm font-medium">{r}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {step === "result" && (
        <div className="space-y-4 animate-fade-in">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400 dark:text-zinc-500 transition-colors duration-300">
              <Loader2 size={28} className="animate-spin mb-3 text-blue-500" />
              <p className="text-sm font-medium">正在查询中...</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* 结果头部 */}
              <div className="flex items-center justify-between pb-4 border-b border-gray-200 dark:border-zinc-800/50">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-zinc-100">{resultSummary}</h3>
                  <p className="text-sm text-gray-500 dark:text-zinc-500 mt-1">
                    {resultGroups.length > 0 ? `共找到 ${resultGroups.length} 条空闲记录` : "无空闲记录"}
                  </p>
                </div>
                <button
                  onClick={() => setStep("room")}
                  className="px-4 py-2 text-sm font-medium text-blue-500 bg-blue-50 hover:bg-blue-100 dark:text-blue-400 dark:bg-blue-500/10 dark:hover:bg-blue-500/20 rounded-lg transition-colors duration-300"
                >
                  重新选择
                </button>
              </div>

              {/* 结果内容 */}
              {resultGroups.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {resultGroups.map((room) => (
                    <RoomCard key={`${room.campus}-${room.room_name}`} room={room} onScheduleClick={onScheduleClick} />
                  ))}
                </div>
              ) : (
                <div className="py-12 flex flex-col items-center justify-center bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-2xl shadow-sm dark:shadow-none">
                  <div className="w-12 h-12 rounded-full bg-gray-50 dark:bg-zinc-800 flex items-center justify-center mb-4">
                    <DoorOpen size={24} className="text-gray-400 dark:text-zinc-500" />
                  </div>
                  <p className="text-gray-600 dark:text-zinc-400 font-medium">{resultContent}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
