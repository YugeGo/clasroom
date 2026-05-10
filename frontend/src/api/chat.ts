/**
 * API 客户端 — 对接后端 POST /api/chat
 */

// 节次时间标签（前端展示用）
export const PERIOD_TIME_LABELS: Record<string, string> = {
  "0102": "08:30-10:00",
  "0304": "10:20-11:50",
  "0506": "14:00-15:30",
  "0708": "15:50-17:20",
  "0910": "18:40-20:10",
};

export const PERIOD_LABELS: Record<string, string> = {
  "0102": "第 1-2 节",
  "0304": "第 3-4 节",
  "0506": "第 5-6 节",
  "0708": "第 7-8 节",
  "0910": "第 9-10 节",
};

// 校区配色
export const CAMPUS_COLORS: Record<string, string> = {
  "舜耕": "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  "燕山": "bg-sky-500/10 text-sky-400 border-sky-500/30",
  "章丘": "bg-amber-500/10 text-amber-400 border-amber-500/30",
};

/** 后端返回的原始房间记录 */
export interface RoomSlot {
  campus: string;
  room_name: string;
  day_of_week: string;
  period_slot: string;
}

/** 后端返回的查询参数 */
export interface QueryParams {
  campus: string | null;
  building: string | null;
  room: string | null;
  day_of_week: string;
  period_slots: string[];
}

// ─── 浏览模式 API ───

export interface CampusInfo {
  name: string;
  building_count: number;
  room_count: number;
}

export interface BuildingInfo {
  name: string;
  display_name: string;
  room_count: number;
}

export interface BrowseResponse<T> {
  campuses?: CampusInfo[];
  campus?: string;
  buildings?: BuildingInfo[];
  building?: string;
  rooms?: string[];
}

export async function fetchCampuses(): Promise<CampusInfo[]> {
  const r = await fetch("/api/browse/campuses");
  const d: BrowseResponse<CampusInfo> = await r.json();
  return d.campuses ?? [];
}

export async function fetchBuildings(campus: string): Promise<BuildingInfo[]> {
  const r = await fetch(`/api/browse/campuses/${encodeURIComponent(campus)}/buildings`);
  const d = await r.json();
  return d.buildings ?? [];
}

export async function fetchRooms(campus: string, building: string): Promise<string[]> {
  const r = await fetch(`/api/browse/campuses/${encodeURIComponent(campus)}/buildings/${encodeURIComponent(building)}/rooms`);
  const d = await r.json();
  return d.rooms ?? [];
}

/** 后端完整响应 */
export interface ChatResponse {
  params: QueryParams;
  count: number;
  rooms: RoomSlot[];
}

/** 前端分组后的房间（聚合多个空闲节次） */
export interface GroupedRoom {
  campus: string;
  room_name: string;
  period_slots: string[];
  day_of_week: string;
}

/** 按楼栋分组 */
export interface BuildingGroup {
  building: string;
  campus: string;
  rooms: GroupedRoom[];
}

/** 从教室名提取楼栋名 */
export function extractBuilding(roomName: string): string {
  if (roomName.startsWith("实验楼")) return "实验楼";
  if (roomName.startsWith("操场")) return "操场";
  if (roomName.includes("-")) return roomName.split("-")[0] + "号楼";
  if (/^\d{4}$/.test(roomName)) return roomName[0] + "号楼";
  return roomName.slice(0, 2);
}

/** 将分组后的房间按楼栋二次分组 */
export function groupByBuilding(groups: GroupedRoom[]): BuildingGroup[] {
  const map = new Map<string, BuildingGroup>();
  for (const room of groups) {
    const bld = extractBuilding(room.room_name);
    const key = `${room.campus}|${bld}`;
    if (!map.has(key)) {
      map.set(key, { building: bld, campus: room.campus, rooms: [] });
    }
    map.get(key)!.rooms.push(room);
  }
  return Array.from(map.values()).sort((a, b) => a.building.localeCompare(b.building));
}

/**
 * 将后端返回的 rooms 按 room_name 分组
 */
export function groupRooms(rooms: RoomSlot[]): GroupedRoom[] {
  const map = new Map<string, GroupedRoom>();
  for (const r of rooms) {
    const key = `${r.campus}|${r.room_name}`;
    const existing = map.get(key);
    if (existing) {
      if (!existing.period_slots.includes(r.period_slot)) {
        existing.period_slots.push(r.period_slot);
      }
    } else {
      map.set(key, {
        campus: r.campus,
        room_name: r.room_name,
        day_of_week: r.day_of_week,
        period_slots: [r.period_slot],
      });
    }
  }
  // 按教室名排序，每间教室的节次也排序
  return Array.from(map.values())
    .sort((a, b) => a.room_name.localeCompare(b.room_name))
    .map((r) => ({
      ...r,
      period_slots: r.period_slots.sort(),
    }));
}

/**
 * 发送自然语言查询 — 简单 JSON 接口（非 SSE）
 */
export async function sendChatMessage(
  message: string
): Promise<ChatResponse> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    const errBody = await response.json().catch(() => ({}));
    throw new Error(errBody.detail || `请求失败 (${response.status})`);
  }

  return response.json();
}
