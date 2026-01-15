import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRightLeft,
  BadgeCheck,
  Brain,
  ChevronRight,
  Database,
  FileUp,
  Fingerprint,
  Sparkles,
  Upload,
  Zap,
} from 'lucide-react';
import { API_URL } from '../config/api';

const steps = ['开始', '添加指南', '选择来源', '获取草稿'];

const documentTypes = [
  '行业与宏观发展报告',
  '政策分析报告',
  '技术路线发展白皮书',
  '应用场景解决方案',
  '安全标准与合规报告',
  '商业模式分析',
  '产业链与竞争格局',
];

const knowledgeBases = [
  { id: 'policy', label: '储能政策法规库' },
  { id: 'market', label: '储能行业市场分析' },
  { id: 'safety', label: '储能安全与标准' },
  { id: 'operation', label: '储能行业运行数据' },
];

export default function Editor() {
  const navigate = useNavigate();
  const [activeStep] = useState(0);
  const [selectedDocType, setSelectedDocType] = useState('行业与宏观发展报告');
  const [useKnowledgeBase, setUseKnowledgeBase] = useState(true);
  const [selectedKB, setSelectedKB] = useState<string[]>(['policy', 'market']);
  const [uploadOwnDraft, setUploadOwnDraft] = useState(false);
  const [isGeneratingVector, setIsGeneratingVector] = useState(false);
  const [isPreprocessing, setIsPreprocessing] = useState(false);
  const [vectorDataStatus, setVectorDataStatus] = useState<any>(null);
  const [preprocessingProgress, setPreprocessingProgress] = useState<any>(null);
  const [showPreprocessingProgress, setShowPreprocessingProgress] = useState(false);

  const toggleKnowledgeBase = (id: string) => {
    setSelectedKB(prev =>
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
    );
  };

  const fetchVectorDataStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/vector-data-generation/status`);
      const data = await response.json();
      if (data.success) {
        setVectorDataStatus(data.data);
      }
    } catch (error) {
      console.error('获取向量数据状态失败:', error);
    }
  };

  const handleGenerateVectorData = async () => {
    if (!confirm('确定要执行向量数据生成吗？这将执行完整的预处理流程。')) {
      return;
    }

    setIsGeneratingVector(true);

    try {
      const response = await fetch(`${API_URL}/vector-data-generation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_dir: 'data/source/uploads',
          output_dir: 'data/cleaned/documents',
          skip_pdf_parsing: false,
          skip_cleaning: false,
          skip_chart_conversion: false,
          skip_vector_index: false,
          skip_bm25_index: false,
        })
      });

      const data = await response.json();
      if (data.success) {
        alert(`向量数据生成完成：${data.message}`);
        await fetchVectorDataStatus();
      } else {
        alert(`生成失败：${data.message}`);
      }
    } catch (error) {
      console.error('向量数据生成失败:', error);
      alert(`生成失败：${error}`);
    } finally {
      setIsGeneratingVector(false);
    }
  };

  const handleDataPreprocessing = async () => {
    if (!confirm('确定要执行数据预处理吗？这将执行：OCR识别（MinerU）→ 内容清洗（LLM）→ 图转JSON')) {
      return;
    }

    setIsPreprocessing(true);
    setShowPreprocessingProgress(true);
    setPreprocessingProgress(null);

    try {
      const response = await fetch(`${API_URL}/data-preprocessing`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      const data = await response.json();
      setPreprocessingProgress(data);

      if (data.success) {
        await fetchVectorDataStatus();
      }
    } catch (error) {
      console.error('数据预处理失败:', error);
      setPreprocessingProgress({
        success: false,
        message: `预处理失败: ${error}`,
        error_details: String(error)
      });
    } finally {
      setIsPreprocessing(false);
    }
  };

  // 页面加载时获取向量数据状态
  useEffect(() => {
    fetchVectorDataStatus();
  }, []);

  const progressItems = useMemo(
    () =>
      steps.map((step, index) => {
        const isActive = index === activeStep;
        const isCompleted = index < activeStep;
        return (
          <div key={step} className="flex items-center">
            <div
              className={`h-10 w-10 rounded-full flex items-center justify-center text-sm font-semibold transition-all duration-300 ${
                isActive
                  ? 'bg-gradient-to-br from-blue-500 to-blue-700 text-white shadow-lg shadow-blue-500/30'
                  : isCompleted
                  ? 'bg-blue-100 text-blue-600 border border-blue-300'
                  : 'bg-white text-slate-400 border border-slate-200'
              }`}
            >
              {index + 1}
            </div>
            <span
              className={`ml-3 text-sm font-medium transition-colors ${
                isActive ? 'text-blue-700' : isCompleted ? 'text-blue-500' : 'text-slate-400'
              }`}
            >
              {step}
            </span>
            {index < steps.length - 1 && (
              <ChevronRight className="mx-3 text-slate-300" size={16} />
            )}
          </div>
        );
      }),
    [activeStep]
  );

  return (
    <main className="w-full max-w-5xl mx-auto px-4 py-6">
      <div className="bg-white/80 rounded-3xl border border-white/70 shadow-[0_20px_60px_rgba(59,130,246,0.15)] backdrop-blur-md p-6 md:p-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-slate-900">白皮书生成流程</h2>
            <p className="text-sm text-slate-500 mt-1">按照步骤配置储能白皮书生成参数,智能输出专业文档。</p>
          </div>
          <button className="inline-flex items-center gap-2 text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors">
            <Brain size={16} />智能策略推荐
          </button>
        </div>

        <div className="flex flex-wrap gap-5 items-center">{progressItems}

          {/* 数据预处理按钮 */}
          <div className="relative">
            <button
              onClick={handleDataPreprocessing}
              disabled={isPreprocessing}
              className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-xl shadow-lg transition-all ${
                isPreprocessing
                  ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                  : 'bg-gradient-to-r from-[#4A90E2] via-[#2F6BCD] to-[#1E5799] text-white hover:shadow-[0_16px_40px_rgba(36,99,214,0.35)]'
              }`}
            >
              {isPreprocessing ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  处理中...
                </>
              ) : (
                <>
                  <Database size={16} />
                  数据预处理
                </>
              )}
            </button>

            {/* 预处理进度显示 */}
            {showPreprocessingProgress && preprocessingProgress && (
              <div className="absolute right-0 top-full mt-2 w-80 bg-white rounded-xl shadow-2xl border border-slate-200 p-4 z-50">
                <h4 className="text-sm font-semibold text-slate-900 mb-3">预处理进度</h4>
                <div className={`mb-3 p-3 rounded-lg ${
                  preprocessingProgress.success
                    ? 'bg-green-100 border border-green-300'
                    : 'bg-red-100 border border-red-300'
                }`}>
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{preprocessingProgress.success ? '✅' : '❌'}</span>
                    <span className="text-sm font-medium">{preprocessingProgress.message}</span>
                  </div>
                </div>
                <div className="space-y-2">
                  {preprocessingProgress.steps?.map((step: any, index: number) => (
                    <div key={index} className="flex items-center gap-2">
                      <div className={`w-5 h-5 rounded-full flex items-center justify-center text-xs ${
                        step.status === 'completed'
                          ? 'bg-green-500 text-white'
                          : step.status === 'failed'
                          ? 'bg-red-500 text-white'
                          : step.status === 'running'
                          ? 'bg-blue-500 text-white animate-pulse'
                          : 'bg-slate-200 text-slate-500'
                      }`}>
                        {step.status === 'completed' ? '✓' : step.status === 'failed' ? '✗' : step.status === 'running' ? '⟳' : '○'}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-slate-700">
                            {step.step_name === 'pdf_parsing' && '1. OCR识别（MinerU）'}
                            {step.step_name === 'data_cleaning' && '2. 内容清洗'}
                            {step.step_name === 'chart_conversion' && '3. 图转JSON'}
                          </span>
                          <span className="text-xs text-slate-500">{step.progress}%</span>
                        </div>
                        <div className="w-full bg-slate-200 rounded-full h-1.5 mt-1">
                          <div
                            className={`h-1.5 rounded-full transition-all ${
                              step.status === 'completed'
                                ? 'bg-green-500'
                                : step.status === 'failed'
                                ? 'bg-red-500'
                                : 'bg-blue-500'
                            }`}
                            style={{ width: `${step.progress}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                {preprocessingProgress.error_details && (
                  <div className="mt-3 p-2 bg-red-50 rounded-lg border border-red-200">
                    <p className="text-xs font-medium text-red-700">错误详情：</p>
                    <p className="text-xs text-red-600">{preprocessingProgress.error_details}</p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 向量数据生成按钮 */}
          <button
            onClick={handleGenerateVectorData}
            disabled={isGeneratingVector}
            className={`ml-auto inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-xl shadow-lg transition-all ${
              isGeneratingVector
                ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                : 'bg-gradient-to-r from-[#4A90E2] via-[#2F6BCD] to-[#1E5799] text-white hover:shadow-[0_16px_40px_rgba(36,99,214,0.35)]'
            }`}
          >
            {isGeneratingVector ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                生成中...
              </>
            ) : (
              <>
                <Zap size={16} />
                向量数据生成
              </>
            )}
          </button>
        </div>

        <div className="space-y-6">
          {/* Report Type Section */}
          <section className="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 space-y-4">
            <div className="flex items-center gap-2">
              <BadgeCheck size={18} className="text-blue-600" />
              <h3 className="text-lg font-semibold text-slate-900">报告类型</h3>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {documentTypes.map(type => (
                <button
                  key={type}
                  onClick={() => setSelectedDocType(type)}
                  className={`px-4 py-3 rounded-xl border transition-all text-sm font-medium flex items-center justify-between group ${
                    selectedDocType === type
                      ? 'border-blue-500 bg-blue-50 text-blue-700 shadow-sm shadow-blue-200/40'
                      : 'border-slate-200 hover:border-blue-300 hover:bg-blue-50/60 text-slate-600'
                  }`}
                >
                  <span>{type}</span>
                  {selectedDocType === type && (
                    <Sparkles size={16} className="text-blue-500" />
                  )}
                </button>
              ))}
            </div>
          </section>

          {/* Two-column grid for remaining sections */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <section className="bg-white rounded-2xl border border-cyan-200 shadow-[0_16px_40px_rgba(34,211,238,0.2)] p-6 space-y-4 transition-all">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-cyan-400 to-blue-500 flex items-center justify-center shadow-inner">
                    <Fingerprint size={20} className="text-white" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900">使用知识库</h3>
                    <p className="text-xs text-slate-500 mt-0.5">选择关联的储能领域知识库资源</p>
                  </div>
                </div>
                <label className="inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={useKnowledgeBase}
                    onChange={(e) => setUseKnowledgeBase(e.target.checked)}
                  />
                  <span className="w-12 h-6 bg-slate-200 rounded-full peer-checked:bg-cyan-400 transition-colors relative">
                    <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-transform ${useKnowledgeBase ? 'translate-x-6' : ''}`} />
                  </span>
                </label>
              </div>

              {useKnowledgeBase && (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    {selectedKB.map(id => {
                      const item = knowledgeBases.find(kb => kb.id === id);
                      if (!item) return null;
                      return (
                        <span
                          key={id}
                          className="px-3 py-1.5 text-xs font-medium bg-cyan-100 text-cyan-700 rounded-full border border-cyan-200 shadow-sm"
                        >
                          {item.label}
                        </span>
                      );
                    })}
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {knowledgeBases.map(item => (
                      <label
                        key={item.id}
                        className={`flex items-center justify-between px-4 py-3 rounded-xl border text-sm transition-all cursor-pointer ${
                          selectedKB.includes(item.id)
                            ? 'border-cyan-500 bg-cyan-50 text-cyan-600 shadow-sm shadow-cyan-200/50'
                            : 'border-cyan-200 hover:border-cyan-400 bg-white text-slate-600'
                        }`}
                      >
                        <span>{item.label}</span>
                        <input
                          type="checkbox"
                          checked={selectedKB.includes(item.id)}
                          onChange={() => toggleKnowledgeBase(item.id)}
                          className="h-4 w-4 accent-cyan-500"
                        />
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </section>

            <section className="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 space-y-4">
              <div className="flex items-center gap-2">
                <ArrowRightLeft size={18} className="text-blue-600" />
                <h3 className="text-lg font-semibold text-slate-900">自有草稿上传</h3>
              </div>
              <label className="flex items-center justify-between px-4 py-3 bg-slate-50 rounded-xl cursor-pointer border border-slate-200">
                <span className="text-sm text-slate-600">我已有草稿并希望继续完善</span>
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={uploadOwnDraft}
                  onChange={(e) => setUploadOwnDraft(e.target.checked)}
                />
                <span className="w-12 h-6 bg-slate-200 rounded-full flex items-center px-1">
                  <span
                    className={`h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${uploadOwnDraft ? 'translate-x-6 bg-blue-500' : ''}`}
                  />
                </span>
              </label>

              {uploadOwnDraft && (
                <div className="border-2 border-dashed border-blue-200 rounded-2xl bg-blue-50/50 p-6 text-center space-y-3">
                  <div className="mx-auto h-12 w-12 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center">
                    <Upload size={20} className="text-white" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-700">拖拽或点击上传现有白皮书草稿</p>
                    <p className="text-xs text-slate-500 mt-1">支持 DOCX / PDF / Markdown / TXT / PPTX</p>
                  </div>
                  <button className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500 text-white text-sm font-medium rounded-full shadow-sm hover:bg-blue-600 transition-colors">
                    <FileUp size={16} /> 选择文件
                  </button>
                </div>
              )}
            </section>
          </div>
        </div>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pt-4 border-t border-slate-100">
          <div className="flex items-center gap-3 text-sm text-slate-500">
            <Sparkles size={18} className="text-blue-500" />
            <span>AI将根据已选参数生成储能白皮书初稿,可随时调整。</span>
          </div>
          <div className="flex items-center gap-3">
            <button className="px-5 py-2.5 rounded-full border border-slate-200 text-sm font-medium text-slate-600 hover:border-blue-300 hover:text-blue-600 transition-colors">
              保存草稿
            </button>
            <button 
              onClick={() => navigate('/outline', { 
                state: { 
                  config: { 
                    docType: selectedDocType, 
                    useKnowledgeBase,
                    selectedKB 
                  } 
                } 
              })}
              className="px-6 py-2.5 rounded-full bg-gradient-to-r from-blue-500 via-blue-600 to-blue-700 text-white text-sm font-semibold shadow-lg shadow-blue-500/30 hover:shadow-blue-500/40 transition-all"
            >
              生成初稿
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
