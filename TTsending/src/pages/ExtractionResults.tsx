import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Info, Download, Database, Table, Lightbulb } from 'lucide-react';
import Header from '../component/Header';

const extractionData = [
  {
    agent: '储能装机容量 (MWh)',
    cells: 24,
    consistency: 100,
    consistentCount: 24,
    progress: '已处理',
    color: 'emerald'
  },
  {
    agent: '储能系统利用率 (%)',
    cells: 18,
    consistency: 100,
    consistentCount: 18,
    progress: '已处理',
    color: 'emerald'
  },
  {
    agent: '锂电池技术占比 (%)',
    cells: 15,
    consistency: 100,
    consistentCount: 15,
    progress: '已处理',
    color: 'emerald'
  },
  {
    agent: '钠离子电池占比 (%)',
    cells: 12,
    consistency: 93,
    consistentCount: 11,
    missingCount: 1,
    progress: '已处理',
    color: 'yellow'
  },
  {
    agent: '储能系统能量损耗率 (%)',
    cells: 20,
    consistency: 100,
    consistentCount: 20,
    progress: '已处理',
    color: 'emerald'
  },
  {
    agent: '储能投资成本 (CNY/kWh)',
    cells: 35,
    consistency: 46,
    consistentCount: 16,
    missingCount: 19,
    progress: '已处理',
    color: 'orange'
  },
  {
    agent: '液流电池技术占比 (%)',
    cells: 8,
    consistency: 100,
    consistentCount: 8,
    progress: '已处理',
    color: 'emerald'
  },
  {
    agent: '压缩空气储能占比 (%)',
    cells: 5,
    consistency: 100,
    consistentCount: 5,
    progress: '已处理',
    color: 'emerald'
  },
];

export default function ExtractionResultsPage() {
  const navigate = useNavigate();
  const [filterText, setFilterText] = useState('');

  const filteredData = extractionData.filter(item =>
    item.agent.toLowerCase().includes(filterText.toLowerCase())
  );

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
          <div className="px-8 py-6 border-b border-slate-200 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-3 mb-1">
                <h1 className="text-2xl font-bold text-slate-900">调查与导出抽取结果</h1>
                <Info size={20} className="text-slate-400" />
              </div>
              <div className="flex items-center gap-2 mt-2">
                <Lightbulb size={16} className="text-amber-500" />
                <span className="text-sm text-slate-600">优化建议</span>
                <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                  1
                </span>
              </div>
            </div>
            <div className="flex gap-3">
              <button className="px-4 py-2 bg-white border border-slate-300 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 flex items-center gap-2">
                <Database size={16} />
                外部数据库
              </button>
              <button className="px-4 py-2 bg-white border border-slate-300 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 flex items-center gap-2">
                <Download size={16} />
                Excel导出
              </button>
              <button className="px-4 py-2 bg-white border border-slate-300 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 flex items-center gap-2">
                <Table size={16} />
                表格视图
              </button>
            </div>
          </div>

          <div className="px-8 py-6">
            <input
              type="text"
              placeholder="按Agent名称筛选..."
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              className="w-full max-w-md px-4 py-2.5 mb-6 bg-white border border-slate-300 rounded-lg text-sm focus:border-blue-400 focus:ring-2 focus:ring-blue-100 outline-none"
            />

            <div className="overflow-hidden rounded-xl border border-slate-200">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                      Agent指标
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                      单元格数
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider w-1/3">
                      抽取一致性
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                      进度
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-100">
                  {filteredData.map((item, index) => (
                    <tr key={index} className="hover:bg-blue-50/30 transition-colors">
                      <td className="px-6 py-4 text-sm font-medium text-slate-900">
                        {item.agent}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-700">
                        {item.cells}
                      </td>
                      <td className="px-6 py-4">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                              <div
                                className={`h-full transition-all ${
                                  item.color === 'emerald'
                                    ? 'bg-emerald-500'
                                    : item.color === 'yellow'
                                    ? 'bg-yellow-400'
                                    : 'bg-orange-400'
                                }`}
                                style={{ width: `${item.consistency}%` }}
                              />
                            </div>
                          </div>
                          <div className="text-xs">
                            <span className={`font-medium ${
                              item.color === 'emerald'
                                ? 'text-emerald-600'
                                : item.color === 'yellow'
                                ? 'text-yellow-600'
                                : 'text-orange-600'
                            }`}>
                              100% ({item.consistentCount}) 一致
                            </span>
                            {item.missingCount && (
                              <span className="text-slate-400 ml-2">
                                {Math.round((item.missingCount / item.cells) * 100)}% ({item.missingCount}) 缺失
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2 text-sm text-slate-600">
                          <div className="h-5 w-5 rounded-full border-2 border-emerald-500 flex items-center justify-center">
                            <div className="h-2 w-2 rounded-full bg-emerald-500" />
                          </div>
                          {item.progress}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-6 flex items-center justify-between text-sm text-slate-600">
              <div>已选择 0 / {filteredData.length} 行</div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <span>每页行数</span>
                  <select className="px-3 py-1 border border-slate-300 rounded-lg bg-white text-slate-700">
                    <option>100</option>
                    <option>50</option>
                    <option>25</option>
                  </select>
                </div>
                <div className="flex items-center gap-2">
                  <button className="px-3 py-1 border border-slate-300 rounded-lg hover:bg-slate-50">«</button>
                  <button className="px-3 py-1 border border-slate-300 rounded-lg hover:bg-slate-50">‹</button>
                  <span>第 1 页，共 1 页</span>
                  <button className="px-3 py-1 border border-slate-300 rounded-lg hover:bg-slate-50">›</button>
                  <button className="px-3 py-1 border border-slate-300 rounded-lg hover:bg-slate-50">»</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
