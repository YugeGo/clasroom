/**
 * QuickActions — 快捷查询芯片
 * 输入框上方一排常用查询，一点即发
 */
import { FC } from "react";
import { Sun, Moon, Building2, Clock, Zap, type LucideIcon } from "lucide-react";

interface QuickAction {
  label: string;
  query: string;
  icon: LucideIcon;
}

const ACTIONS: QuickAction[] = [
  { label: "舜耕下午", query: "舜耕下午有空教室吗", icon: Sun },
  { label: "燕山明天", query: "燕山明天有空教室吗", icon: Moon },
  { label: "章丘晚上", query: "章丘晚上能自习吗", icon: Clock },
  { label: "现在有空", query: "现在哪里有空教室", icon: Zap },
  { label: "3号楼", query: "3号楼现在哪儿能自习", icon: Building2 },
];

interface Props {
  onSelect: (query: string) => void;
  disabled: boolean;
}

export const QuickActions: FC<Props> = ({ onSelect, disabled }) => {
  return (
    <div className="flex flex-wrap gap-2 px-4 pb-2">
      {ACTIONS.map((action) => {
        const Icon = action.icon;
        return (
          <button
            key={action.label}
            onClick={() => onSelect(action.query)}
            disabled={disabled}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-zinc-800/50 text-gray-600 dark:text-zinc-400 text-xs font-medium border border-gray-200/80 dark:border-zinc-700/50 hover:bg-gray-200 dark:hover:bg-zinc-700/50 hover:text-gray-800 dark:hover:text-zinc-200 hover:border-blue-300 dark:hover:border-zinc-600 active:scale-95 transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed touch-manipulation"
          >
            <Icon size={14} className="opacity-70" />
            {action.label}
          </button>
        );
      })}
    </div>
  );
};
