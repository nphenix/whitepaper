import {
  Bot,
  ChevronDown,
  ChevronRight,
  Database,
  FileText,
  LibraryBig,
  Search,
  Plus,
  FileCheck,
} from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function Sidebar() {
  const navigate = useNavigate();
  const [sections, setSections] = useState({
    history: true,
    knowledge: true,
    agent: true,
    extraction: true,
    sources: true
  });

  const toggleSection = (section: keyof typeof sections) => {
    setSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  return (
    <aside className="w-full lg:w-1/3 xl:w-[32%] px-6 py-6 bg-gradient-to-b from-blue-50/80 via-white to-blue-100/40 backdrop-blur-sm border-r border-white/60">
      <div className="space-y-4">
        <button
          onClick={() => navigate('/')}
          className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-2xl bg-gradient-to-r from-[#4A90E2] via-[#2F6BCD] to-[#1E5799] text-white text-sm font-semibold shadow-[0_12px_30px_rgba(36,99,214,0.25)] hover:shadow-[0_16px_40px_rgba(36,99,214,0.35)] transition-all duration-300"
        >
          <Plus size={18} />
          新建白皮书
        </button>

        <button
          onClick={() => navigate('/ai-search')}
          className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-white border border-blue-200 text-blue-600 text-sm font-medium hover:bg-blue-50 transition-all duration-200"
        >
          <Search size={16} />
          AI 智能检索
        </button>

        <section className="bg-white/80 rounded-2xl border border-white/70 shadow-md overflow-hidden">
          <button
            onClick={() => toggleSection('history')}
            className="w-full flex items-center justify-between px-5 py-4 text-sm font-semibold text-slate-800 hover:bg-blue-50/50 transition-colors"
          >
            <span className="flex items-center gap-2">
              <FileText size={18} className="text-blue-600" />
              白皮书历史记录
            </span>
            {sections.history ? (
              <ChevronDown size={18} className="text-blue-600" />
            ) : (
              <ChevronRight size={18} className="text-slate-400" />
            )}
          </button>
          {sections.history && (
            <div className="px-4 pb-4">
              <button
                onClick={() => navigate('/final')}
                className="w-full text-left px-4 py-3 rounded-xl bg-white hover:bg-blue-50 border border-slate-200 hover:border-blue-300 transition-all shadow-sm hover:shadow-md group"
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-slate-900 group-hover:text-blue-600 transition-colors">
                      未来五年储能产业政策与发展趋势白皮书
                    </p>
                    <p className="text-xs text-slate-500 mt-1">创建于 2025/11/10</p>
                  </div>
                  <ChevronRight size={16} className="text-slate-400 group-hover:text-blue-500 transition-colors" />
                </div>
              </button>
            </div>
          )}
        </section>

        <section className="bg-white/80 rounded-2xl border border-white/70 shadow-md overflow-hidden">
          <button
            onClick={() => navigate('/knowledge-base')}
            className="w-full flex items-center justify-between px-5 py-4 text-sm font-semibold text-slate-800 hover:bg-blue-50/50 transition-colors group"
          >
            <span className="flex items-center gap-2">
              <LibraryBig size={18} className="text-blue-600 group-hover:text-blue-700 transition-colors" />
              知识库
            </span>
            <div className="flex items-center gap-2">
              <span className="text-xs text-blue-600 font-medium">8个专业库</span>
              <ChevronRight size={18} className="text-slate-400 group-hover:text-blue-600 transition-colors" />
            </div>
          </button>
        </section>

        <section className="bg-white/80 rounded-2xl border border-white/70 shadow-md overflow-hidden">
          <button
            onClick={() => navigate('/data-agents')}
            className="w-full flex items-center justify-between px-5 py-4 text-sm font-semibold text-slate-800 hover:bg-blue-50/50 transition-colors group"
          >
            <span className="flex items-center gap-2">
              <Bot size={18} className="text-indigo-600 group-hover:text-indigo-700 transition-colors" />
              数据抽取Agent
            </span>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-slate-800 text-white">3</span>
              <ChevronRight size={18} className="text-slate-400 group-hover:text-blue-600 transition-colors" />
            </div>
          </button>
        </section>

        <section className="bg-white/80 rounded-2xl border border-white/70 shadow-md overflow-hidden">
          <button
            onClick={() => navigate('/extraction-results')}
            className="w-full flex items-center justify-between px-5 py-4 text-sm font-semibold text-slate-800 hover:bg-blue-50/50 transition-colors group"
          >
            <span className="flex items-center gap-2">
              <FileCheck size={18} className="text-emerald-600 group-hover:text-emerald-700 transition-colors" />
              抽取结果
            </span>
            <div className="flex items-center gap-2">
              <span className="text-xs text-emerald-600 font-medium">8项已处理</span>
              <ChevronRight size={18} className="text-slate-400 group-hover:text-blue-600 transition-colors" />
            </div>
          </button>
        </section>

        <section className="bg-white/80 rounded-2xl border border-white/70 shadow-md overflow-hidden">
          <button
            onClick={() => navigate('/sources-data')}
            className="w-full flex items-center justify-between px-5 py-4 text-sm font-semibold text-slate-800 hover:bg-blue-50/50 transition-colors group"
          >
            <span className="flex items-center gap-2">
              <Database size={18} className="text-blue-600 group-hover:text-blue-700 transition-colors" />
              源数据汇总
            </span>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-600 font-medium">9个文档</span>
              <ChevronRight size={18} className="text-slate-400 group-hover:text-blue-600 transition-colors" />
            </div>
          </button>
        </section>
      </div>
    </aside>
  );
}
