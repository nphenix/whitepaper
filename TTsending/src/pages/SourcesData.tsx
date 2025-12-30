import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Upload, MoreVertical, CheckCircle, ArrowUpDown } from 'lucide-react';
import Header from '../component/Header';

const sourceDocuments = [
  {
    name: '2025.07 - 宁德时代储能系统数据报告.xlsx',
    summary: '本文档为Excel电子表格，包含宁德时代2022-2024年储能装机容量、系统利用率等核心指标',
    pages: 1,
    extracted: '28天前',
    uploaded: '28天前',
    status: '已处理'
  },
  {
    name: '2025.07 - 比亚迪储能技术白皮书.pdf',
    summary: '比亚迪储能技术演示文档，详细介绍刀片电池在储能领域的应用及性能数据',
    pages: 42,
    extracted: '29天前',
    uploaded: '29天前',
    status: '已处理'
  },
  {
    name: '2025.07.02 - 2024年Q3储能产业数据.xlsx',
    summary: '本文档标题为"2024年第三季度储能产业数据汇总"，涵盖多家企业季度报告',
    pages: 1,
    extracted: '29天前',
    uploaded: '29天前',
    status: '已处理'
  },
  {
    name: '2025.07.02 - 特斯拉能源-储能投资成本分析.xlsx',
    summary: '本文档为财务模型电子表格，分析特斯拉储能系统投资成本及ROI预测',
    pages: 1,
    extracted: '28天前',
    uploaded: '28天前',
    status: '已处理'
  },
  {
    name: '2025.07.02 - 国轩高科-磷酸铁锂储能技术指标.xlsx',
    summary: '本文档为财务模型电子表格，包含国轩高科磷酸铁锂电池核心技术参数',
    pages: 1,
    extracted: '28天前',
    uploaded: '28天前',
    status: '已处理'
  },
  {
    name: '液流电池技术发展报告 - 2024年7月.png',
    summary: '本文档展示了液流电池技术在储能系统中的应用及市场占比分析图表',
    pages: 1,
    extracted: '28天前',
    uploaded: '28天前',
    status: '已处理'
  },
  {
    name: '钠离子电池储能系统对比分析 - 2024年7月.png',
    summary: '本文档呈现钠离子电池储能收益率对比分析，包含多家企业数据可视化图表',
    pages: 1,
    extracted: '28天前',
    uploaded: '28天前',
    status: '已处理'
  },
  {
    name: '蜂巢能源产品路线图 - 2025年7月.pdf',
    summary: '本文档为蜂巢能源投资者演示文稿，展示其储能产品发展路线图及市场策略',
    pages: 15,
    extracted: '29天前',
    uploaded: '29天前',
    status: '已处理'
  },
  {
    name: '中国储能产业政策汇编 - 2024.pdf',
    summary: '本文档汇总了2022-2024年中国储能产业相关政策文件及解读分析',
    pages: 68,
    extracted: '30天前',
    uploaded: '30天前',
    status: '已处理'
  },
];

export default function SourcesDataPage() {
  const navigate = useNavigate();
  const [filterText, setFilterText] = useState('');

  const filteredDocs = sourceDocuments.filter(doc =>
    doc.name.toLowerCase().includes(filterText.toLowerCase())
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
              <h1 className="text-2xl font-bold text-slate-900">管理文档</h1>
              <p className="text-sm text-slate-600 mt-1">查看和管理已上传的源数据文档</p>
            </div>
            <div className="flex gap-3">
              <button className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 flex items-center gap-2 shadow-md">
                <Upload size={16} />
                上传文件
              </button>
              <button className="px-4 py-2 bg-white border border-slate-300 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50">
                字段
              </button>
            </div>
          </div>

          <div className="px-8 py-6">
            <input
              type="text"
              placeholder="按文档名称筛选..."
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              className="w-full max-w-md px-4 py-2.5 mb-6 bg-white border border-slate-300 rounded-lg text-sm focus:border-blue-400 focus:ring-2 focus:ring-blue-100 outline-none"
            />

            <div className="overflow-hidden rounded-xl border border-slate-200">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                      <button className="flex items-center gap-1 hover:text-slate-900">
                        文档名称
                        <ArrowUpDown size={14} />
                      </button>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                      摘要
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                      <button className="flex items-center gap-1 hover:text-slate-900">
                        页数
                        <ArrowUpDown size={14} />
                      </button>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                      <button className="flex items-center gap-1 hover:text-slate-900">
                        已抽取
                        <ArrowUpDown size={14} />
                      </button>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                      <button className="flex items-center gap-1 hover:text-slate-900">
                        已上传
                        <ArrowUpDown size={14} />
                      </button>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                      <button className="flex items-center gap-1 hover:text-slate-900">
                        状态
                        <ArrowUpDown size={14} />
                      </button>
                    </th>
                    <th className="px-6 py-3"></th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-100">
                  {filteredDocs.map((doc, index) => (
                    <tr key={index} className="hover:bg-blue-50/30 transition-colors">
                      <td className="px-6 py-4 text-sm font-medium text-slate-900 max-w-xs">
                        {doc.name}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-600 max-w-md">
                        <div className="line-clamp-2">{doc.summary}</div>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-700">
                        {doc.pages}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-600">
                        {doc.extracted}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-600">
                        {doc.uploaded}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2 text-sm text-emerald-600">
                          <CheckCircle size={16} />
                          {doc.status}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <button className="p-1 hover:bg-slate-100 rounded transition-colors">
                          <MoreVertical size={18} className="text-slate-400" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-6 flex items-center justify-between text-sm text-slate-600">
              <div>已选择 0 / {filteredDocs.length} 行</div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <span>每页行数</span>
                  <select className="px-3 py-1 border border-slate-300 rounded-lg bg-white text-slate-700">
                    <option>50</option>
                    <option>25</option>
                    <option>10</option>
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
