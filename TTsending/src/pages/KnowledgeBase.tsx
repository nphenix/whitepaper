import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, FileText, Users, Database, X, Download, Eye } from 'lucide-react';
import Header from '../component/Header';

// Energy Storage Chinese PDF files
const energyStoragePDFs = [
  '"十五五"时期我国新型储能产业发展形势研判与思路建议.pdf',
  '2022储能产业研究白皮书.pdf',
  '2022全球储能发展回顾与展望暨储能产业白皮书.pdf',
  '2022年度电化学储能电站行业统计数据-中电联.pdf',
  '2023中国储能产业研究报告-创业邦.pdf',
  '2023储能产业研研究白皮书.pdf',
  '2023年中国储能产业发展研究报告.pdf',
  '2023年中国储能行业系列研究-超级电容器储能.pdf',
  '2023年中国新型储能行业发展白皮书.pdf',
  '2023年中国电化学储能行业市场前景及投资研究报告.pdf',
  '2024 第一季度储能市场经济性分析报告.pdf',
  '2024中国新型储能行业发展白皮书-储能领跑者联盟&华塑科技.pdf',
  '2024储能高质量发展：市场机制与商业模式创新（简版报告）-中关村储能产业技术联盟.pdf',
  '2024年中国储能技术研究进展.pdf',
  '2024年光伏、储能行业投资策略：新技术盈利有望见底新市场或是最强主线【行行查-hanghangcha.com】.pdf',
  '2024新型储能行业研究报告.pdf',
  '20251022-中原证券-电力设备及新能源行业专题研究：新型储能产业链之河南概况（二）.pdf',
  '20251103-招商证券-电力设备及新能源行业储能系列报告（14）：数据中心配储有望迎来大发展.pdf',
  '20251119-平安证券-电力设备及新能源行业储能系列报告（一）：从"配角"到"主角"，储能前景广阔.pdf',
  '2025年中国新型储能行业发展白皮书-机遇与挑战.pdf',
  '2025年负荷中心储能潜力及发展机制研究报告-南部区域.pdf',
  '2030光风储能源转型白皮书.pdf',
  '中关村储能产业技术联盟：2023年储能产业年度回顾及趋势展望报告.pdf',
  '中关村储能产业技术联盟：2024中国储能技术与产业最新进展与展望报告.pdf',
  '中国储能产业集群发展白皮书.pdf',
  '中国储能技术与产业最新进展与展望暨《储能产业研究白皮书2025》发布.pdf',
  '中国储能研究报告2025.pdf',
  '中国建筑金属结构协会：中国蓄热储能产业发展报告（2024）.pdf',
  '中国独立储能发展报告2025.pdf',
  '储能产业研究白皮书2024.pdf',
  '储能科普手册-中国能源研究会.pdf',
  '储能领跑者联盟：2025年核心储能供应链手册.pdf',
  '先进光伏和新型储能产业2024年发展形势展望.pdf',
  '嘉世咨询：2025年储能逆变器行业简析报告.pdf',
  '国信证券-光储行业研究专题：新能源发展势不可挡，大储引领提速在即.pdf',
  '国家能源局：中国新型储能发展报告2025.pdf',
  '国网新疆经研院：2025新疆新型储能发展概述与展望报告.pdf',
  '新型储能产业发展现状及趋势-暨CNESA DataLink2024年储能数据发布报告.pdf',
  '新型电力系统发展蓝皮书-2023-国家能源局.pdf',
  '沙利文：2024年全球移动储能电源行业研究报告.pdf',
  '电力规划总院：2025年新形势下新型储能发展趋势分析报告.pdf',
  '电力设备及新能源行业专题研究：新型储能产业链之河南概况（二）.pdf',
  '维科网：2024年储能产业抢占制高点发展蓝皮书.pdf',
  '能源新纪元系列：储能行业趋势洞察.pdf',
  '艾瑞咨询：2023年中国储能行业研究报告.pdf',
  '蓄势待发：储能机遇（英）.pdf',
  '规模化民用储能市场（英）.pdf',
];

const knowledgeBases = [
  {
    id: 'energy-storage-chinese',
    title: '储能行业市场分析',
    subtitle: '中国储能行业研究资料库',
    description: '汇集国内储能行业最新研究报告、白皮书、市场分析等专业文献，涵盖政策解读、技术趋势、产业发展等核心内容...',
    image: 'linear-gradient(135deg, #1a365d 0%, #2563eb 50%, #3b82f6 100%)',
    icon: '📚',
    sources: 47,
    seeds: energyStoragePDFs.length,
    users: 156,
    creator: '王静',
    date: '2025年12月08日',
    price: '免费',
    language: '中文',
    isClickable: true,
    pdfs: energyStoragePDFs
  },
  {
    id: 1,
    title: '储能政策法规库',
    subtitle: '中国储能行业政策与法规全景汇编',
    description: '汇集国家及地方储能产业政策、法规文件，涵盖补贴政策、并网标准、安全规范等核心内容...',
    image: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    icon: '📜',
    sources: 128,
    seeds: 456,
    users: 89,
    creator: '能源研究院',
    price: '免费',
    language: '中文',
    isClickable: false
  },
  {
    id: 2,
    title: '锂电池技术标准库',
    subtitle: '锂离子电池储能系统技术规范与标准',
    description: '包含GB/T、IEC等国内外锂电池技术标准，覆盖电芯设计、BMS系统、热管理等关键技术领域...',
    image: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
    icon: '🔋',
    sources: 85,
    seeds: 312,
    users: 124,
    creator: '宁德时代研发中心',
    price: '¥4.99',
    language: '中文',
    isClickable: false
  },
  {
    id: 3,
    title: '储能市场数据仓库',
    subtitle: '全球储能装机容量与市场趋势数据',
    description: '提供2020-2024年全球及中国储能市场数据，包括装机规模、投资趋势、成本分析等专业报告...',
    image: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
    icon: '📊',
    sources: 156,
    seeds: 589,
    users: 203,
    creator: 'CNESA数据中心',
    price: '¥12.99',
    language: '中文',
    isClickable: false
  },
  {
    id: 4,
    title: '钠离子电池前沿研究',
    subtitle: '钠离子储能技术最新研究成果',
    description: '聚焦钠离子电池在储能领域的应用，包含材料科学、电化学性能、产业化进展等前沿研究论文...',
    image: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
    icon: '⚡',
    sources: 72,
    seeds: 245,
    users: 67,
    creator: '中科院物理所',
    price: '¥6.99',
    language: '中文',
    isClickable: false
  },
  {
    id: 5,
    title: '液流电池技术文献',
    subtitle: '全钒液流电池系统设计与应用',
    description: '收录液流电池技术专利、学术论文及工程案例，涵盖电堆设计、电解液优化、系统集成等内容...',
    image: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
    icon: '💧',
    sources: 64,
    seeds: 198,
    users: 45,
    creator: '大连化物所',
    price: '¥5.99',
    language: '中文',
    isClickable: false
  },
  {
    id: 6,
    title: '储能安全规范指南',
    subtitle: '电化学储能电站安全技术要求',
    description: '涵盖消防安全、电气安全、运维规范等储能电站安全管理体系，包含事故案例分析与防范措施...',
    image: 'linear-gradient(135deg, #ff9a56 0%, #ff6a00 100%)',
    icon: '🛡️',
    sources: 94,
    seeds: 367,
    users: 156,
    creator: '应急管理部',
    price: '免费',
    language: '中文',
    isClickable: false
  },
  {
    id: 7,
    title: '压缩空气储能技术',
    subtitle: 'CAES系统原理与工程实践',
    description: '压缩空气储能系统技术文献库，包括绝热压缩、等温压缩等技术路线及示范工程案例分析...',
    image: 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
    icon: '🌪️',
    sources: 48,
    seeds: 156,
    users: 34,
    creator: '中国科学院',
    price: '¥7.99',
    language: '中文',
    isClickable: false
  },
  {
    id: 8,
    title: '储能经济性分析',
    subtitle: '储能项目投资回报与商业模式',
    description: '储能系统全生命周期成本分析，包含LCOE计算、峰谷套利、辅助服务等多种盈利模式研究...',
    image: 'linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)',
    icon: '💰',
    sources: 112,
    seeds: 423,
    users: 187,
    creator: '清华大学能源互联网研究院',
    price: '¥9.99',
    language: '中文',
    isClickable: false
  },
];

interface KnowledgeBase {
  id: string | number;
  title: string;
  subtitle: string;
  description: string;
  image: string;
  icon: string;
  sources: number;
  seeds: number;
  users: number;
  creator: string;
  date?: string;
  price: string;
  language: string;
  isClickable: boolean;
  pdfs?: string[];
}

export default function KnowledgeBasePage() {
  const navigate = useNavigate();
  const [selectedKB, setSelectedKB] = useState<KnowledgeBase | null>(null);
  const [selectedPdf, setSelectedPdf] = useState<string | null>(null);

  const handleCardClick = (kb: KnowledgeBase) => {
    if (kb.isClickable) {
      setSelectedKB(kb);
    }
  };

  const closePdfList = () => {
    setSelectedKB(null);
    setSelectedPdf(null);
  };

  const openPdf = (pdfName: string) => {
    setSelectedPdf(pdfName);
  };

  const closePdfViewer = () => {
    setSelectedPdf(null);
  };

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

        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">精选知识库</h1>
          <p className="text-slate-600">热门与趋势储能知识库</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {knowledgeBases.map((kb) => (
            <div
              key={kb.id}
              onClick={() => handleCardClick(kb as KnowledgeBase)}
              className={`bg-white rounded-2xl shadow-md hover:shadow-xl transition-all duration-300 overflow-hidden border border-slate-100 hover:border-blue-200 hover:-translate-y-1 group ${
                kb.isClickable ? 'cursor-pointer ring-2 ring-blue-500 ring-offset-2' : 'cursor-default'
              }`}
            >
              {/* Cover Image */}
              <div 
                className="h-40 relative overflow-hidden"
                style={{ background: kb.image }}
              >
                <div className="absolute inset-0 bg-black/5 group-hover:bg-black/10 transition-colors" />
                <div className="absolute top-3 right-3">
                  <span className="px-2 py-1 text-[10px] font-bold rounded bg-slate-800/80 text-white backdrop-blur-sm">
                    {kb.language}
                  </span>
                </div>
                {kb.isClickable && (
                  <div className="absolute top-3 left-3">
                    <span className="px-2 py-1 text-[10px] font-bold rounded bg-green-500 text-white backdrop-blur-sm animate-pulse">
                      可查看
                    </span>
                  </div>
                )}
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-6xl opacity-90">{kb.icon}</span>
                </div>
                <div className="absolute bottom-0 left-0 right-0 px-4 py-3 bg-gradient-to-t from-black/60 to-transparent">
                  <div className="flex items-center gap-2 text-white text-xs">
                    <FileText size={14} />
                    <span className="font-medium">{kb.title}</span>
                  </div>
                </div>
              </div>

              {/* Content */}
              <div className="p-4">
                <h3 className="font-semibold text-sm text-slate-900 mb-2 line-clamp-2 min-h-[2.5rem]">
                  {kb.subtitle}
                </h3>
                <p className="text-xs text-slate-600 mb-4 line-clamp-2 leading-relaxed">
                  {kb.description}
                </p>

                {/* Date for Energy Storage Chinese */}
                {kb.date && (
                  <div className="text-xs text-blue-600 mb-3 font-medium">
                    📅 {kb.date}
                  </div>
                )}

                {/* Stats */}
                <div className="flex items-center justify-between mb-4 pb-4 border-b border-slate-100">
                  <div className="text-center">
                    <div className="text-base font-bold text-slate-900">{kb.sources}</div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wide">来源</div>
                  </div>
                  <div className="text-center">
                    <div className="text-base font-bold text-slate-900">{kb.seeds}</div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wide">文档</div>
                  </div>
                  <div className="text-center">
                    <div className="text-base font-bold text-slate-900">{kb.users}</div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wide">用户</div>
                  </div>
                </div>

                {/* Creator & Price */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="h-6 w-6 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center">
                      <Users size={12} className="text-white" />
                    </div>
                    <span className="text-xs text-slate-700 font-medium line-clamp-1">{kb.creator}</span>
                  </div>
                  <span className={`text-sm font-bold ${kb.price === '免费' ? 'text-emerald-600' : 'text-blue-600'}`}>
                    {kb.price}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Summary Stats */}
        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-2xl p-6 shadow-md border border-slate-100">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-xl bg-blue-100 flex items-center justify-center">
                <Database size={24} className="text-blue-600" />
              </div>
              <div>
                <div className="text-2xl font-bold text-slate-900">9</div>
                <div className="text-sm text-slate-600">专业知识库</div>
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-2xl p-6 shadow-md border border-slate-100">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-xl bg-emerald-100 flex items-center justify-center">
                <FileText size={24} className="text-emerald-600" />
              </div>
              <div>
                <div className="text-2xl font-bold text-slate-900">2,793</div>
                <div className="text-sm text-slate-600">文档总数</div>
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-2xl p-6 shadow-md border border-slate-100">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-xl bg-purple-100 flex items-center justify-center">
                <Users size={24} className="text-purple-600" />
              </div>
              <div>
                <div className="text-2xl font-bold text-slate-900">1,061</div>
                <div className="text-sm text-slate-600">活跃用户</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* PDF List Modal */}
      {selectedKB && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[85vh] overflow-hidden">
            {/* Modal Header */}
            <div 
              className="p-6 text-white relative"
              style={{ background: selectedKB.image }}
            >
              <button
                onClick={closePdfList}
                className="absolute top-4 right-4 p-2 rounded-full bg-white/20 hover:bg-white/30 transition-colors"
              >
                <X size={20} className="text-white" />
              </button>
              <div className="flex items-center gap-4">
                <span className="text-5xl">{selectedKB.icon}</span>
                <div>
                  <h2 className="text-2xl font-bold">{selectedKB.title}</h2>
                  <p className="text-white/80 text-sm mt-1">{selectedKB.subtitle}</p>
                  <div className="flex items-center gap-4 mt-2 text-xs text-white/70">
                    <span>📅 {selectedKB.date}</span>
                    <span>👤 {selectedKB.creator}</span>
                    <span>📄 {selectedKB.pdfs?.length || 0} 份文档</span>
                  </div>
                </div>
              </div>
            </div>

            {/* PDF List */}
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              <div className="grid gap-3">
                {selectedKB.pdfs?.map((pdf, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between p-4 bg-slate-50 rounded-xl hover:bg-blue-50 transition-colors border border-slate-200 hover:border-blue-300 group"
                  >
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <div className="h-10 w-10 rounded-lg bg-red-100 flex items-center justify-center flex-shrink-0">
                        <FileText size={20} className="text-red-600" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-slate-800 truncate">{pdf}</p>
                        <p className="text-xs text-slate-500 mt-0.5">PDF 文档</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={() => openPdf(pdf)}
                        className="flex items-center gap-1 px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-xs font-medium"
                      >
                        <Eye size={14} />
                        查看
                      </button>
                      <a
                        href={`http://localhost:3001/pdfs/${encodeURIComponent(pdf)}`}
                        download
                        className="flex items-center gap-1 px-3 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors text-xs font-medium"
                      >
                        <Download size={14} />
                        下载
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* PDF Viewer Modal */}
      {selectedPdf && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[60] flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full h-[90vh] max-w-6xl overflow-hidden flex flex-col">
            {/* Viewer Header */}
            <div className="flex items-center justify-between p-4 bg-slate-100 border-b">
              <div className="flex items-center gap-3">
                <FileText size={24} className="text-red-600" />
                <span className="font-medium text-slate-800 truncate max-w-[500px]">{selectedPdf}</span>
              </div>
              <div className="flex items-center gap-2">
                <a
                  href={`http://localhost:3001/pdfs/${encodeURIComponent(selectedPdf)}`}
                  download
                  className="flex items-center gap-1 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors text-sm font-medium"
                >
                  <Download size={16} />
                  下载
                </a>
                <button
                  onClick={closePdfViewer}
                  className="p-2 rounded-lg bg-slate-200 hover:bg-slate-300 transition-colors"
                >
                  <X size={20} className="text-slate-700" />
                </button>
              </div>
            </div>
            
            {/* PDF Embed */}
            <div className="flex-1 bg-slate-200">
              <iframe
                src={`http://localhost:3001/pdfs/${encodeURIComponent(selectedPdf)}`}
                className="w-full h-full"
                title={selectedPdf}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
