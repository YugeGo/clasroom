/**
 * UsageGuide — 使用说明弹窗
 */
import { FC } from "react";
import { X, MessageSquare, Building2, Clock, HelpCircle } from "lucide-react";

interface Props {
  onClose: () => void;
}

export const UsageGuide: FC<Props> = ({ onClose }) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-white dark:bg-zinc-900 rounded-2xl shadow-2xl w-full max-w-md max-h-[80vh] overflow-y-auto animate-fade-in border border-gray-200 dark:border-zinc-800"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-zinc-800">
          <div className="flex items-center gap-2">
            <HelpCircle size={18} className="text-blue-500" />
            <span className="font-semibold text-gray-900 dark:text-zinc-100">使用说明</span>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-zinc-800 text-gray-400">
            <X size={18} />
          </button>
        </div>

        {/* 内容 */}
        <div className="px-5 py-4 space-y-5 text-sm text-gray-700 dark:text-zinc-300 leading-relaxed">

          <div>
            <p className="font-medium text-gray-900 dark:text-zinc-100 mb-1">🤷 这是干啥的</p>
            <p>查空教室的。输入一句话，告诉你山财哪个教室现在没课。</p>
          </div>

          <div className="border-t border-gray-100 dark:border-zinc-800 pt-4">
            <p className="font-medium text-gray-900 dark:text-zinc-100 mb-2">💬 直接聊天搜</p>
            <div className="space-y-2 text-xs">
              <p className="flex items-start gap-1.5"><MessageSquare size={12} className="mt-0.5 text-blue-500 shrink-0" />「下午舜耕有空教室吗」</p>
              <p className="flex items-start gap-1.5"><MessageSquare size={12} className="mt-0.5 text-blue-500 shrink-0" />「章丘七号楼明天三四节」</p>
              <p className="flex items-start gap-1.5"><MessageSquare size={12} className="mt-0.5 text-blue-500 shrink-0" />「燕山1号楼现在哪儿能自习」</p>
              <p className="flex items-start gap-1.5"><MessageSquare size={12} className="mt-0.5 text-blue-500 shrink-0" />「现在有空教室吗」</p>
            </div>
          </div>

          <div className="border-t border-gray-100 dark:border-zinc-800 pt-4">
            <p className="font-medium text-gray-900 dark:text-zinc-100 mb-2">🏢 点着选</p>
            <p className="flex items-start gap-1.5"><Building2 size={12} className="mt-0.5 text-blue-500 shrink-0" />点下面的「现在有空教室吗」按钮 → 选校区 → 选楼栋 → 看哪些教室空着。不用打字。</p>
          </div>

          <div className="border-t border-gray-100 dark:border-zinc-800 pt-4">
            <p className="font-medium text-gray-900 dark:text-zinc-100 mb-1">🕐 时间怎么看</p>
            <p className="flex items-start gap-1.5"><Clock size={12} className="mt-0.5 text-blue-500 shrink-0" />不同日期的时间：
              1-2节（08:30-10:00）<br />
              3-4节（10:20-11:50）<br />
              5-6节（14:00-15:30）<br />
              7-8节（15:50-17:20）<br />
              9-10节（18:40-20:10）</p>
          </div>

          <div className="border-t border-gray-100 dark:border-zinc-800 pt-4">
            <p className="font-medium text-gray-900 dark:text-zinc-100 mb-1">⚠️ 免责声明</p>
            <p className="text-gray-500 dark:text-zinc-400 text-xs">本工具根据教务系统排课数据生成空闲时间表，仅供参考，可能有延迟或误差。如果你要去找教室自习，建议到了再确认一下实际情况，免得白跑一趟。</p>
          </div>
        </div>
      </div>
    </div>
  );
};
