/**
 * Zustand 状态管理 — 聊天会话
 */
import { create } from "zustand";
import type { QueryParams, GroupedRoom } from "../api/chat";

export type MessageType = "user" | "ai" | "result";

export interface ChatMessage {
  id: string;
  type: MessageType;
  content: string;
  timestamp: Date;
  groups?: GroupedRoom[];
  params?: QueryParams;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: Date;
}

interface ChatState {
  sessions: ChatSession[];
  currentSessionId: string | null;
  isStreaming: boolean;

  newSession: () => string;
  switchSession: (id: string) => void;
  addMessage: (msg: Omit<ChatMessage, "id" | "timestamp">) => void;
  updateLastMessage: (updates: Partial<ChatMessage>) => void;
  setStreaming: (v: boolean) => void;
  deleteSession: (id: string) => void;
}

let msgCounter = 0;
function genId() {
  msgCounter++;
  return `msg-${Date.now()}-${msgCounter}`;
}

function genSessionId() {
  return `session-${Date.now()}`;
}

function defaultSession(): ChatSession {
  return {
    id: genSessionId(),
    title: "新对话",
    messages: [
      {
        id: "welcome",
        type: "ai",
        content: `# 山财自习通

用自然语言查询空教室，试试这样说：

- 「现在有空教室吗」
- 「下午舜耕有空教室吗」
- 「章丘七号楼明天三四节」
- 「燕山1号楼3楼现在能自习吗」`,
        timestamp: new Date(),
      },
    ],
    createdAt: new Date(),
  };
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [defaultSession()],
  currentSessionId: defaultSession().id,
  isStreaming: false,

  newSession: () => {
    const session = defaultSession();
    set((s) => ({
      sessions: [...s.sessions, session],
      currentSessionId: session.id,
    }));
    return session.id;
  },

  switchSession: (id: string) => {
    set({ currentSessionId: id });
  },

  addMessage: (msg) => {
    const full: ChatMessage = { ...msg, id: genId(), timestamp: new Date() };
    set((s) => ({
      sessions: s.sessions.map((ses) =>
        ses.id === s.currentSessionId
          ? { ...ses, messages: [...ses.messages, full] }
          : ses
      ),
    }));
  },

  updateLastMessage: (updates) => {
    set((s) => ({
      sessions: s.sessions.map((ses) => {
        if (ses.id !== s.currentSessionId) return ses;
        const msgs = [...ses.messages];
        if (msgs.length === 0) return ses;
        msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], ...updates };
        return { ...ses, messages: msgs };
      }),
    }));
  },

  setStreaming: (v) => set({ isStreaming: v }),

  deleteSession: (id: string) => {
    set((s) => {
      const filtered = s.sessions.filter((ses) => ses.id !== id);
      const currentId =
        s.currentSessionId === id
          ? filtered[filtered.length - 1]?.id ?? null
          : s.currentSessionId;
      return { sessions: filtered, currentSessionId: currentId };
    });
  },
}));

/** 获取当前会话 */
export function useCurrentSession() {
  return useChatStore((s) =>
    s.sessions.find((ses) => ses.id === s.currentSessionId)
  );
}
