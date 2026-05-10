/**
 * LocalEngine — 浏览器端离线 API 引擎
 *
 * 直接加载 sdufe_rooms.json，在浏览器中完成所有查询和筛选，
 * 无需任何后端服务器。部署到 Netlify 等静态托管即可运行。
 */
import { RoomSlot, QueryParams, CampusInfo, BuildingInfo } from "./chat";

// ─── 常量 ───
const WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"];
const CN_DIGITS: Record<string, string> = {
  "一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
  "六": "6", "七": "7", "八": "8", "九": "9", "十": "10",
};
const TIME_KEYWORDS: Record<string, string[]> = {
  "上午": ["0102", "0304"], "中午": ["0506"],
  "下午": ["0506", "0708"], "晚上": ["0910"],
  "全天": ["0102", "0304", "0506", "0708", "0910"],
};
const PERIOD_NUMS: Record<string, string> = {
  "1": "0102", "2": "0102", "3": "0304", "4": "0304",
  "5": "0506", "6": "0506", "7": "0708", "8": "0708",
  "9": "0910", "10": "0910",
};

// 楼栋别名
const BUILDING_ALIAS: Record<string, string> = {};
const CN = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"];
for (let n = 1; n <= 10; n++) {
  const c = CN[n - 1];
  for (const alias of [`${n}号楼`, `${n}号教学楼`, `${c}号楼`, `${c}号教学楼`,
    `第${c}教学楼`, `${n}教`, `${c}教`]) {
    BUILDING_ALIAS[alias] = `${n}号楼`;
  }
}

// ─── 数据 ───
let _data: RoomSlot[] | null = null;

export async function loadData(): Promise<RoomSlot[]> {
  if (_data) return _data;
  const resp = await fetch("/sdufe_rooms.json");
  const raw: any[] = await resp.json();
  _data = raw.map((r) => ({
    campus: r.campus,
    room_name: r.room_name,
    day_of_week: r.day_of_week,
    period_slot: r.period_slot,
  }));
  return _data;
}

// ─── 意图解析 ───

function parseIntent(text: string) {
  const now = new Date();
  const todayIdx = (now.getDay() + 6) % 7; // 0=星期一

  // 校区
  let campus: string | null = null;
  if (text.includes("舜耕")) campus = "舜耕";
  else if (text.includes("燕山")) campus = "燕山";
  else if (text.includes("章丘") || text.includes("圣井")) campus = "章丘";

  // 星期
  let dayOfWeek = WEEKDAY_CN[todayIdx];
  if (text.includes("明天")) dayOfWeek = WEEKDAY_CN[(todayIdx + 1) % 7];
  else if (text.includes("后天")) dayOfWeek = WEEKDAY_CN[(todayIdx + 2) % 7];
  else {
    const m = text.match(/(星期|周)([一二三四五六日])/);
    if (m) {
      const idx = { "一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6 }[m[2]];
      if (idx !== undefined) dayOfWeek = WEEKDAY_CN[idx];
    }
  }

  // 节次
  let periodSlots = ["0102", "0304", "0506", "0708", "0910"];
  for (const [kw, slots] of Object.entries(TIME_KEYWORDS)) {
    if (text.includes(kw)) { periodSlots = slots; break; }
  }

  const rangeMatch = text.match(/第?(\d+)\s*[-–到至]\s*(\d+)\s*节/);
  if (rangeMatch) {
    const slots = new Set<string>();
    for (let n = +rangeMatch[1]; n <= +rangeMatch[2]; n++) {
      if (PERIOD_NUMS[String(n)]) slots.add(PERIOD_NUMS[String(n)]);
    }
    if (slots.size) periodSlots = [...slots].sort();
  }

  const cnMatch = text.match(/第?([一二三四五六七八九十两])[、]?([到至]?)([一二三四五六七八九十两]?)\s*节/);
  if (cnMatch) {
    const s = CN_DIGITS[cnMatch[1]], e = CN_DIGITS[cnMatch[3] || cnMatch[1]];
    if (s && e) {
      const slots = new Set<string>();
      for (let n = +s; n <= +e; n++) {
        if (PERIOD_NUMS[String(n)]) slots.add(PERIOD_NUMS[String(n)]);
      }
      if (slots.size) periodSlots = [...slots].sort();
    }
  }

  // 楼栋
  let building: string | null = null;
  for (const [alias, std] of Object.entries(BUILDING_ALIAS).sort((a, b) => b[0].length - a[0].length)) {
    if (text.includes(alias)) { building = std; break; }
  }

  // 教室号
  let room: string | null = null;
  const hyphenMatch = text.match(/(\d{1,2}[-]\d{3,4})/);
  if (hyphenMatch) room = hyphenMatch[1];
  else {
    const numMatch = text.match(/(?<!\d)(\d{4})(?!\s*[节点])/);
    if (numMatch) room = numMatch[1];
  }

  return { campus, building, room, day_of_week: dayOfWeek, period_slots: periodSlots };
}

// ─── 查询 ───

function queryRooms(
  data: RoomSlot[],
  campus: string | null,
  dayOfWeek: string,
  periodSlots: string[],
  building: string | null,
  room: string | null,
): RoomSlot[] {
  const bldNum = building ? building.match(/(\d+)号楼/)?.[1] : null;

  return data.filter((r) => {
    if (campus && r.campus !== campus) return false;
    if (r.day_of_week !== dayOfWeek) return false;
    if (!periodSlots.includes(r.period_slot)) return false;

    if (building) {
      const name = r.room_name;
      if (bldNum) {
        if (/^\d/.test(name)) {
          if (!name.startsWith(bldNum) && !name.startsWith(`${bldNum}-`)) return false;
        } else if (name.startsWith("实验楼") && bldNum === "6") {
          // pass
        } else return false;
      } else if (!name.includes(building)) return false;
    }

    if (room && r.room_name !== room) return false;
    return true;
  });
}

// ─── 浏览导航数据 ───

function buildHierarchy(data: RoomSlot[]) {
  const h: Record<string, Record<string, Set<string>>> = {};
  for (const r of data) {
    const name = r.room_name;
    let bld: string;
    if (/^\d/.test(name)) {
      bld = name.includes("-") ? name.split("-")[0] : name[0];
    } else if (name.startsWith("实验楼")) bld = "实验楼";
    else if (name.startsWith("操场")) bld = "操场";
    else bld = name;

    (h[r.campus] ??= {});
    (h[r.campus][bld] ??= new Set()).add(name);
  }

  const result: Record<string, Record<string, string[]>> = {};
  for (const c of Object.keys(h).sort()) {
    result[c] = {};
    for (const b of Object.keys(h[c]).sort()) {
      result[c][b] = [...h[c][b]].sort();
    }
  }
  return result;
}

// ─── 导出接口 ───

export async function localSendChatMessage(message: string) {
  const data = await loadData();
  const intent = parseIntent(message);

  const rooms = queryRooms(
    data, intent.campus, intent.day_of_week, intent.period_slots,
    intent.building, intent.room,
  );

  const params: Record<string, any> = {
    campus: intent.campus, building: intent.building, room: intent.room,
    day_of_week: intent.day_of_week, period_slots: intent.period_slots,
  };
  // 移除 null 字段
  const cleanParams: Record<string, any> = {};
  for (const [k, v] of Object.entries(params)) {
    if (v !== null) cleanParams[k] = v;
  }

  return {
    params: cleanParams,
    count: rooms.length,
    rooms: rooms.map((r) => ({
      campus: r.campus,
      room_name: r.room_name,
      day_of_week: r.day_of_week,
      period_slot: r.period_slot,
    })),
  };
}

export async function localFetchCampuses(): Promise<CampusInfo[]> {
  const data = await loadData();
  const h = buildHierarchy(data);
  return Object.entries(h).sort((a, b) => a[0].localeCompare(b[0])).map(([name, blds]) => {
    const total = Object.values(blds).reduce((s, r) => s + r.length, 0);
    return { name, building_count: Object.keys(blds).length, room_count: total };
  });
}

export async function localFetchBuildings(campus: string): Promise<BuildingInfo[]> {
  const data = await loadData();
  const h = buildHierarchy(data);
  const blds = h[campus] ?? {};
  return Object.entries(blds).sort((a, b) => a[0].localeCompare(b[0])).map(([name, rooms]) => ({
    name,
    display_name: /^\d$/.test(name) ? `${name}号楼` : name,
    room_count: rooms.length,
  }));
}

export async function localFetchRooms(campus: string, building: string): Promise<string[]> {
  const data = await loadData();
  const h = buildHierarchy(data);
  return h[campus]?.[building] ?? [];
}

// ─── Phase 2: 教室周课表 ───

export interface RoomSchedule {
  room_name: string;
  campus: string;
  days: { day: string; slots: { slot: string; free: boolean }[] }[];
}

export function fetchRoomSchedule(data: RoomSlot[], roomName: string, campus: string): RoomSchedule {
  const allSlots = ["0102", "0304", "0506", "0708", "0910"];
  const freeSet = new Set<string>();

  for (const r of data) {
    if (r.room_name === roomName && r.campus === campus) {
      freeSet.add(`${r.day_of_week}|${r.period_slot}`);
    }
  }

  const days = WEEKDAY_CN.map((day) => ({
    day,
    slots: allSlots.map((slot) => ({
      slot,
      free: freeSet.has(`${day}|${slot}`),
    })),
  }));

  return { room_name: roomName, campus, days };
}

// ─── Phase 1 & 4: DeepSeek AI ───

let _aiAvailable: boolean | null = null;

export async function isAIAvailable(): Promise<boolean> {
  if (_aiAvailable !== null) return _aiAvailable;
  try {
    const resp = await fetch("/api/deepseek", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "test", type: "parse" }),
    });
    const data = await resp.json();
    _aiAvailable = !data.fallback;
    return _aiAvailable;
  } catch {
    _aiAvailable = false;
    return false;
  }
}

export async function callDeepSeekParse(message: string): Promise<any | null> {
  try {
    const resp = await fetch("/api/deepseek", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, type: "parse" }),
    });
    const data = await resp.json();
    if (data.fallback) return null;
    return data.intent;
  } catch {
    return null;
  }
}

export async function callDeepSeekSummary(message: string, context: string): Promise<string | null> {
  try {
    const resp = await fetch("/api/deepseek", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, type: "summarize", context }),
    });
    const data = await resp.json();
    if (data.fallback || !data.summary) return null;
    return data.summary;
  } catch {
    return null;
  }
}

/** 尝试用 AI 解析，失败则回退到本地关键词 */
export async function localSendChatMessageAI(message: string) {
  const data = await loadData();

  // 先尝试 AI 解析
  let intent = await callDeepSeekParse(message);
  // 回退到本地解析
  if (!intent) {
    intent = parseIntent(message);
  }

  const rooms = queryRooms(
    data, intent.campus, intent.day_of_week, intent.period_slots,
    intent.building, intent.room,
  );

  const params: Record<string, any> = {
    campus: intent.campus, building: intent.building, room: intent.room,
    day_of_week: intent.day_of_week, period_slots: intent.period_slots,
  };
  const cleanParams: Record<string, any> = {};
  for (const [k, v] of Object.entries(params)) {
    if (v !== null) cleanParams[k] = v;
  }

  // AI 总结
  let summary: string | null = null;
  if (rooms.length > 0 && intent.campus) {
    const context = `在${intent.campus}找到${rooms.length}间空教室, 时段:${intent.period_slots?.join(",")}`;
    summary = await callDeepSeekSummary(message, context);
  }

  return {
    params: cleanParams,
    count: rooms.length,
    rooms: rooms.map((r) => ({
      campus: r.campus, room_name: r.room_name,
      day_of_week: r.day_of_week, period_slot: r.period_slot,
    })),
    summary,
  };
}
