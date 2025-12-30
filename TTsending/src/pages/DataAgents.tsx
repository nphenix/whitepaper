import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Sparkles, Users, Library, Info } from 'lucide-react';
import Header from '../component/Header';

export default function DataAgentsPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'prompt' | 'active' | 'library'>('prompt');
  const [promptText, setPromptText] = useState(`请帮我查找以下与储能行业相关的能量指标数据，用于不同公司在最近几年的对比分析：

- 储能装机容量（单位：MWh）
- 储能系统利用率（%）
- 各类储能技术的占比（如锂电池、钠离子电池、液流电池、压缩空气储能等）
- 储能系统能量损耗率（%）
- 储能投资成本（单位：USD/kWh 或 CNY/kWh）

我需要比较各家公司（例如：宁德时代、比亚迪、特斯拉能源、国轩高科、蜂巢能源）的储能相关指标，涵盖年度范围 2022 至 2024 年`);

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#E8F4FF] via-white to-[#E0F2FF]">
      <Header />
      
      <div className="max-w-[1400px] mx-auto py-8 px-6 lg:px-10">
        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-2 px-4 py-2 mb-6 text-sm font-medium text-slate-700 hover:text-blue-600 transition-colors"
        >
          <ArrowLeft size={18} />
          返回主页
        </button>

        <div className="bg-white rounded-3xl shadow-[0_20px_80px_rgba(79,134,255,0.15)] border border-white/60 overflow-hidden">
          <div className="px-8 py-6 border-b border-slate-200">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900">创建与配置数据抽取Agent</h1>
              <Info size={20} className="text-slate-400" />
            </div>
          </div>

          <div className="px-8 py-6">
            <div className="flex gap-3 mb-6">
              <button
                onClick={() => setActiveTab('prompt')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  activeTab === 'prompt'
                    ? 'bg-blue-50 text-blue-700 border-2 border-blue-200'
                    : 'bg-slate-100 text-slate-600 border-2 border-transparent hover:bg-slate-200'
                }`}
              >
                <span className="flex items-center gap-2">
                  <Sparkles size={16} />
                  提示词转Agent
                  <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-blue-600 text-white">BETA</span>
                </span>
              </button>
              
              <button
                onClick={() => setActiveTab('active')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  activeTab === 'active'
                    ? 'bg-blue-50 text-blue-700 border-2 border-blue-200'
                    : 'bg-slate-100 text-slate-600 border-2 border-transparent hover:bg-slate-200'
                }`}
              >
                <span className="flex items-center gap-2">
                  <Users size={16} />
                  活跃Agent数
                  <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-slate-800 text-white">3</span>
                </span>
              </button>

              <button
                onClick={() => setActiveTab('library')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  activeTab === 'library'
                    ? 'bg-blue-50 text-blue-700 border-2 border-blue-200'
                    : 'bg-slate-100 text-slate-600 border-2 border-transparent hover:bg-slate-200'
                }`}
              >
                <span className="flex items-center gap-2">
                  <Library size={16} />
                  Agent库
                  <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-slate-800 text-white">230</span>
                </span>
              </button>
            </div>

            {activeTab === 'prompt' && (
              <div className="space-y-4">
                <div className="flex gap-2 mb-4">
                  <button className="px-4 py-2 bg-slate-100 text-slate-700 text-sm font-medium rounded-lg border-b-2 border-slate-300">
                    文本
                  </button>
                  <button className="px-4 py-2 bg-white text-slate-500 text-sm font-medium rounded-lg hover:bg-slate-50">
                    图像
                  </button>
                  <button className="px-4 py-2 bg-white text-slate-500 text-sm font-medium rounded-lg hover:bg-slate-50">
                    报告
                  </button>
                </div>

                <div className="bg-slate-50 rounded-xl p-6 border border-slate-200">
                  <textarea
                    value={promptText}
                    onChange={(e) => setPromptText(e.target.value)}
                    className="w-full h-64 bg-white rounded-lg p-4 text-sm text-slate-800 border border-slate-300 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 outline-none resize-none font-normal leading-relaxed"
                    placeholder="在此输入您的提示词..."
                  />
                </div>

                <button className="w-full py-4 bg-slate-400 text-white rounded-xl font-semibold text-sm flex items-center justify-center gap-2 cursor-wait">
                  <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                  正在生成Agent...
                </button>
              </div>
            )}

            {activeTab === 'active' && (
              <div className="bg-slate-50 rounded-xl p-8 border border-slate-200 text-center">
                <Users size={48} className="mx-auto mb-4 text-slate-400" />
                <h3 className="text-lg font-semibold text-slate-800 mb-2">活跃Agent管理</h3>
                <p className="text-sm text-slate-600">当前有 3 个活跃的数据抽取Agent正在运行</p>
              </div>
            )}

            {activeTab === 'library' && (
              <div className="bg-slate-50 rounded-xl p-8 border border-slate-200 text-center">
                <Library size={48} className="mx-auto mb-4 text-slate-400" />
                <h3 className="text-lg font-semibold text-slate-800 mb-2">Agent模板库</h3>
                <p className="text-sm text-slate-600">浏览和选择预配置的230个Agent模板</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
