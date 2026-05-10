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

// 当前时间 → 节次映射
function getCurrentPeriodSlots(): string[] {
  const h = new Date().getHours();
  const m = new Date().getMinutes();
  const total = h * 60 + m;
  if (total >= 8 * 60 + 0 && total < 9 * 60 + 35) return ["0102"];
  if (total >= 9 * 60 + 35 && total < 9 * 60 + 50) return ["0102", "0304"]; // 课间
  if (total >= 9 * 60 + 50 && total < 11 * 60 + 25) return ["0304"];
  if (total >= 11 * 60 + 25 && total < 13 * 60 + 30) return []; // 午休
  if (total >= 13 * 60 + 30 && total < 15 * 60 + 5) return ["0506"];
  if (total >= 15 * 60 + 5 && total < 15 * 60 + 20) return ["0506", "0708"]; // 课间
  if (total >= 15 * 60 + 20 && total < 16 * 60 + 55) return ["0708"];
  if (total >= 16 * 60 + 55 && total < 18 * 60 + 30) return []; // 晚饭
  if (total >= 18 * 60 + 30) return ["0910"];
  return []; // 清晨/深夜
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
  let periodSlots: string[];

  // 如果包含"现在"，自动检测当前时段
  if (text.includes("现在")) {
    periodSlots = getCurrentPeriodSlots();
  } else {
    periodSlots = ["0102", "0304", "0506", "0708", "0910"];
  }

  // ① 口语时段（上午/下午/晚上）
  for (const [kw, slots] of Object.entries(TIME_KEYWORDS)) {
    if (text.includes(kw)) { periodSlots = slots; break; }
  }

  // ② "第3-4节" 标准范围
  const rangeMatch = text.match(/第?(\d+)\s*[-–到至]\s*(\d+)\s*节/);
  if (rangeMatch) {
    const slots = new Set<string>();
    for (let n = +rangeMatch[1]; n <= +rangeMatch[2]; n++) {
      if (PERIOD_NUMS[String(n)]) slots.add(PERIOD_NUMS[String(n)]);
    }
    if (slots.size) periodSlots = [...slots].sort();
  }

  // ③ 中文数字节次（三四节、五到七节）
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

  // ④ "12节" = 第1-2节（相邻数字口语句式）
  const adjacentMatch = text.match(/(?:第)?(\d)(\d)\s*节/);
  if (adjacentMatch) {
    const slots = new Set<string>();
    // 个别数字如 "12节" → [1,2]，分别映射
    for (let i = +adjacentMatch[1]; i <= +adjacentMatch[2]; i++) {
      if (PERIOD_NUMS[String(i)]) slots.add(PERIOD_NUMS[String(i)]);
    }
    if (slots.size) periodSlots = [...slots].sort();
  }

  // ⑤ 阿拉伯数字节次 "3节" "4节"（单个数字）
  const singleMatch = text.match(/(\d)\s*节/);
  if (singleMatch && !adjacentMatch) {
    const slot = PERIOD_NUMS[singleMatch[1]];
    if (slot) periodSlots = [slot];
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

  // 楼层（"三楼" "3楼"）
  let floor: number | null = null;
  const floorCN = text.match(/([一二三四五六七八九])楼/);
  if (floorCN) floor = +CN_DIGITS[floorCN[1]];
  else {
    const floorNum = text.match(/(\d)\s*楼/);
    if (floorNum) floor = +floorNum[1];
  }

  // 检测是否有任何有效查询意图
  const hasIntent = campus || building || room || floor !== null ||
    text.match(/[上中下晚]午|晚上|全天|节|点|星期|周[一二三四五六日]|今天|明天|后天|现在/) !== null;

  if (!hasIntent) {
    return null; // 纯闲聊，不是查询
  }

  return { campus, building, room, floor, day_of_week: dayOfWeek, period_slots: periodSlots };
}

// ─── 查询 ───

function queryRooms(
  data: RoomSlot[],
  campus: string | null,
  dayOfWeek: string,
  periodSlots: string[],
  building: string | null,
  room: string | null,
  floor: number | null = null,
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

    // 楼层筛选
    if (floor !== null) {
      const name = r.room_name;
      let roomFloor: number | null = null;
      if (name.includes("-")) {
        // 章丘格式 "7-116" → 第2位数字是楼层
        const afterHyphen = name.split("-")[1];
        if (afterHyphen) roomFloor = +afterHyphen[0];
      } else if (/^\d{4}$/.test(name)) {
        // 舜耕/燕山格式 "3103" → 第2位数字是楼层
        roomFloor = +name[1];
      }
      if (roomFloor !== null && roomFloor !== floor) return false;
    }

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

  if (!intent) {
    return { params: {}, count: 0, rooms: [], summary: null };
  }

  const rooms = queryRooms(
    data, intent.campus, intent.day_of_week, intent.period_slots,
    intent.building, intent.room, intent.floor,
  );

  const params: Record<string, any> = {
    campus: intent.campus, building: intent.building, room: intent.room,
    floor: intent.floor,
    day_of_week: intent.day_of_week, period_slots: intent.period_slots,
  };
  // 移除 null 字段
  const cleanParams: Record<string, any> = {};
  for (const [k, v] of Object.entries(params)) {
    if (v !== null) cleanParams[k] = v;
  }

  const uniqueCount = new Set(rooms.map((r) => r.room_name)).size;

  return {
    params: cleanParams,
    count: uniqueCount,
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

// ─── Phase 1 & 4: DeepSeek AI（通过 Netlify Function 代理） ───

const AI_ENABLED = true; // 代理始终可用，没 Key 会返回 fallback

const AI_SYSTEM_PROMPT = () => {
  const now = new Date();
  const wd = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
  const ts = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDay()}日 ${wd[now.getDay()]}`;
  const slots = Object.entries({
    "0102": "第1-2节 (08:00-09:35)", "0304": "第3-4节 (09:50-11:25)",
    "0506": "第5-6节 (13:30-15:05)", "0708": "第7-8节 (15:20-16:55)",
    "0910": "第9-10节 (18:30-20:05)",
  }).map(([k, v]) => `'${k}'=${v}`).join("、");

  return `你是一个山财空教室意图解析器。当前系统时间：${ts}。将用户的自然语言转化为 JSON。必须映射为山财的黑话：
* campus (string|null): 仅限 ['舜耕', '燕山', '章丘']，未提则为 null。若用户说「圣井」，自动映射为「章丘」。
* day_of_week (string): 格式 '星期一'~'星期日'。如用户说「明天」，根据当前时间推算。
* period_slots (array): 可选值：${slots}。'上午'=['0102','0304']，'下午'=['0506','0708']，'晚上'=['0910']。
请只输出 JSON。`;
};

export function isAIAvailable(): boolean {
  return AI_ENABLED;
}

async function callDeepSeekProxy(messages: { role: string; content: string }[], jsonMode: boolean): Promise<string | null> {
  try {
    const resp = await fetch("/api/deepseek", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages,
        response_format: jsonMode ? { type: "json_object" } : undefined,
        temperature: jsonMode ? 0.1 : 0.7,
      }),
    });
    const data = await resp.json();
    if (data.fallback) return null;
    return data.choices?.[0]?.message?.content ?? null;
  } catch {
    return null;
  }
}

export async function callDeepSeekParse(message: string): Promise<any | null> {
  const content = await callDeepSeekProxy(
    [
      { role: "system", content: AI_SYSTEM_PROMPT() },
      { role: "user", content: message },
    ],
    true,
  );
  if (!content) return null;
  try {
    return JSON.parse(content);
  } catch {
    return null;
  }
}

export async function callDeepSeekSummary(message: string, context: string): Promise<string | null> {
  return callDeepSeekProxy(
    [
      { role: "system", content: "你是一个山财空教室助手。用一段自然语言总结查询结果，要友好简洁有温度。" },
      { role: "user", content: `用户问题：${message}\n\n查询结果：${context}` },
    ],
    false,
  );
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

  if (!intent) {
    return { params: {}, count: 0, rooms: [], summary: null };
  }

  const rooms = queryRooms(
    data, intent.campus, intent.day_of_week, intent.period_slots,
    intent.building, intent.room, intent.floor,
  );

  const params: Record<string, any> = {
    campus: intent.campus, building: intent.building, room: intent.room,
    floor: intent.floor,
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

  const uniqueCount = new Set(rooms.map((r) => r.room_name)).size;

  return {
    params: cleanParams,
    count: uniqueCount,
    rooms: rooms.map((r) => ({
      campus: r.campus, room_name: r.room_name,
      day_of_week: r.day_of_week, period_slot: r.period_slot,
    })),
    summary,
  };
}
