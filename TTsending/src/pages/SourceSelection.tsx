import { useState, useEffect } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { Upload, Link as LinkIcon, CheckCircle, File, ExternalLink } from 'lucide-react';
import { API_URL } from '../config/api';

interface Source {
  id: number;
  title: string;
  authors: string;
  year: string;
  domain: string;
  cited: number;
  recommended: boolean;
  excerpt: string;
}

export default function SourceSelection() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const outlineId = searchParams.get('id') || location.state?.outlineId;
  const config = location.state?.config || {};
  
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSources, setSelectedSources] = useState<number[]>([]);
  const [customUrl, setCustomUrl] = useState('');
  const [customUrls, setCustomUrls] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  useEffect(() => {
    fetchSources();
  }, [outlineId]);

  const fetchSources = async () => {
    // Use mock energy storage data
    const mockEnergyStorageSources: Source[] = [
      {
        id: 1,
        title: 'Global Energy Storage Policy Landscape 2024—Comparative Review',
        authors: 'J. Han, R. Patel',
        year: '2024',
        domain: 'IEA.org',
        cited: 82,
        recommended: true,
        excerpt: 'analyzes recent energy storage policies in over 20 economies, comparing market incentives, grid regulations, and subsidy schemes shaping future deployment trends.'
      },
      {
        id: 2,
        title: 'The Role of Energy Storage in Carbon Neutrality Strategies',
        authors: 'S. Meier, A. Gupta',
        year: '2022',
        domain: 'Nature Energy',
        cited: 692,
        recommended: true,
        excerpt: 'evaluates the contribution of grid-scale and distributed storage to emission reduction pathways, emphasizing the synergy between renewable integration and flexible capacity.'
      },
      {
        id: 3,
        title: '"新型储能"政策体系建设与市场化机制研究',
        authors: '王志强, 李静',
        year: '2023',
        domain: '《中国电力》期刊',
        cited: 136,
        recommended: true,
        excerpt: '分析我国新型储能政策体系中的监管模式、激励机制与市场准入障碍，探讨市场化改革对产业投资的促进作用。'
      },
      {
        id: 4,
        title: '全球储能技术创新与政策比较研究报告（2025版）',
        authors: '国家能源局能源政策研究中心',
        year: '2025',
        domain: 'chinanengyuan.gov.cn',
        cited: 59,
        recommended: true,
        excerpt: '对比美欧日韩储能政策演进与技术创新路径，评估中国储能在全球竞争中的政策优势与短板。'
      },
      {
        id: 5,
        title: '中国储能产业发展蓝皮书（2024）',
        authors: '中国能源研究会储能专委会',
        year: '2024',
        domain: 'energy.org.cn',
        cited: 482,
        recommended: true,
        excerpt: '系统梳理我国储能产业政策演变、市场格局与技术进展，提出"十四五"后期储能发展的重点任务与路径建议。'
      }
    ];

    setSources(mockEnergyStorageSources);
    const recommended = mockEnergyStorageSources.filter(s => s.recommended).map(s => s.id);
    setSelectedSources(recommended);
    setIsLoading(false);
  };

  const toggleSource = (id: number) => {
    setSelectedSources(prev =>
      prev.includes(id) ? prev.filter(sid => sid !== id) : [...prev, id]
    );
  };

  const handleAddUrl = () => {
    if (customUrl.trim()) {
      setCustomUrls([...customUrls, customUrl]);
      setCustomUrl('');
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    setIsUploading(true);
    setUploadError(null);

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const formData = new FormData();
      formData.append('file', file);

      try {
        const response = await fetch(`${API_URL}/upload`, {
          method: 'POST',
          body: formData
        });
        
        const data = await response.json();
        if (response.ok && data?.success) {
          console.log('File uploaded:', data?.data?.file);
        } else {
          const msg = data?.error || data?.message || `上传失败: ${file.name}`;
          setUploadError(msg);
          console.error('Upload failed:', msg, data);
          break;
        }
      } catch (error) {
        console.error('Error uploading file:', error);
        setUploadError(`上传失败: ${file.name}`);
        break;
      }
    }

    setIsUploading(false);
    // 允许用户重复选择同一个文件触发 onChange
    e.target.value = '';
  };

  const handleGenerateDraft = async () => {
    const currentOutlineId = outlineId || Date.now().toString();
    // 关键：先导航到 final 页面，再异步触发生成，避免等待 LLM 生成导致 e2e 超时
    navigate(`/final?id=${currentOutlineId}`, { state: { outlineId: currentOutlineId, config } });

    // 后台保存来源选择（失败不阻断）
    void fetch(`${API_URL}/sources/${currentOutlineId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ selectedSources, customUrls })
    }).catch((error) => {
      console.warn('保存来源选择失败:', error);
    });

    // 后台触发草稿生成（由 FinalView 轮询 /draft 获取结果）
    void fetch(`${API_URL}/generate-draft/${currentOutlineId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
      .then(async (resp) => {
        try {
          const data = await resp.json();
          if (!data?.success) {
            console.error('生成草稿失败:', data?.error || data?.message);
          }
        } catch {
          // ignore JSON parse errors
        }
      })
      .catch((error) => {
        console.error('触发草稿生成失败:', error);
      });
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#E8F4FF] via-white to-[#E0F2FF] flex items-center justify-center">
        <div className="text-xl text-gray-600">加载中...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#E8F4FF] via-white to-[#E0F2FF]">
      <div className="max-w-5xl mx-auto px-6 py-12">
        <div className="mb-8">
          <div className="flex items-center gap-4 mb-6">
            <button 
              onClick={() => navigate('/')}
              className="flex items-center gap-2 group cursor-pointer"
            >
              <div className="h-8 w-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm font-semibold group-hover:bg-blue-700 transition-colors">
                <CheckCircle size={18} />
              </div>
              <span className="text-sm text-gray-600 group-hover:text-blue-700 transition-colors">开始</span>
            </button>
            <div className="h-0.5 w-12 bg-blue-600"></div>
            <button 
              onClick={() => navigate('/outline', { state: { config } })}
              className="flex items-center gap-2 group cursor-pointer"
            >
              <div className="h-8 w-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm font-semibold group-hover:bg-blue-700 transition-colors">
                <CheckCircle size={18} />
              </div>
              <span className="text-sm text-gray-600 group-hover:text-blue-700 transition-colors">添加指南</span>
            </button>
            <div className="h-0.5 w-12 bg-blue-600"></div>
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm font-semibold">
                3
              </div>
              <span className="text-sm font-medium text-gray-900">选择来源</span>
            </div>
            <div className="h-0.5 w-12 bg-gray-300"></div>
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-full bg-gray-200 text-gray-500 flex items-center justify-center text-sm font-semibold">
                4
              </div>
              <span className="text-sm text-gray-500">获取草稿</span>
            </div>
          </div>
        </div>

        <div className="bg-white/90 rounded-2xl shadow-lg border border-white/70 p-8 mb-6">
          <h1 className="text-3xl font-bold mb-2 text-slate-900">选择推荐来源 或 添加自己的来源</h1>
          <p className="text-sm text-slate-500 mb-8">上传文件、添加链接或从下方推荐文献中选择</p>

          {isUploading && (
            <div
              className="mb-4 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800"
              data-testid="uploading-indicator"
            >
              正在上传并处理文件（包含 PDF 解析/图表识别），请稍候…
            </div>
          )}
          {uploadError && (
            <div
              className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
              data-testid="upload-error"
            >
              {uploadError}
            </div>
          )}

          <div className="grid grid-cols-2 gap-6 mb-8">
            <div className="border-2 border-dashed border-blue-200 bg-blue-50/30 rounded-2xl p-8 text-center hover:border-blue-400 hover:bg-blue-50/50 transition-all cursor-pointer">
              <input
                type="file"
                multiple
                accept=".pdf,.doc,.docx,.pptx"
                onChange={handleFileUpload}
                disabled={isUploading}
                className="hidden"
                id="file-upload"
              />
              <label htmlFor="file-upload" className="cursor-pointer">
                <Upload className="mx-auto mb-3 text-blue-600" size={36} />
                <p className="text-blue-700 font-semibold mb-1">点击上传</p>
                <p className="text-sm text-slate-600">或拖拽文件到此处</p>
                <p className="text-xs text-slate-500 mt-3">支持 .pdf, .docx, .pptx 格式，单个文件最大50MB</p>
              </label>
            </div>

            <div className="border-2 border-blue-200 bg-white rounded-2xl p-6 hover:border-blue-400 transition-colors">
              <div className="flex items-center gap-2 mb-4">
                <LinkIcon className="text-blue-600" size={24} />
                <h3 className="font-semibold text-slate-900">添加文献链接</h3>
              </div>
              <p className="text-xs text-slate-500 mb-3">添加学术文章、网站或视频链接</p>
              <div className="flex gap-2">
                <input
                  type="url"
                  value={customUrl}
                  onChange={(e) => setCustomUrl(e.target.value)}
                  placeholder="例如: https://www.nature.com/articles/..."
                  className="flex-1 px-4 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-400 focus:border-blue-500 text-sm"
                />
                <button
                  onClick={handleAddUrl}
                  className="px-5 py-2 bg-blue-600 text-white font-medium rounded-xl hover:bg-blue-700 transition-colors text-sm"
                >
                  添加
                </button>
              </div>
            </div>
          </div>

          <div>
            <h2 className="text-xl font-semibold mb-1 text-slate-900">
              AI为您推荐的储能领域文献
            </h2>
            <p className="text-sm text-slate-500 mb-5">选择您希望引用的来源文献</p>

            <div className="space-y-4">
              {sources.map(source => (
                <div
                  key={source.id}
                  className={`border-2 rounded-2xl p-6 transition-all ${
                    selectedSources.includes(source.id)
                      ? 'border-blue-500 bg-blue-50/50 shadow-md shadow-blue-200/30'
                      : 'border-slate-200 hover:border-blue-300 hover:bg-blue-50/20'
                  }`}
                >
                  <div className="flex items-start gap-4">
                    <label className="flex items-start cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedSources.includes(source.id)}
                        onChange={(e) => {
                          e.stopPropagation();
                          toggleSource(source.id);
                        }}
                        className="mt-1 h-5 w-5 text-blue-600 rounded cursor-pointer accent-blue-600"
                      />
                    </label>
                    <div className="flex-1">
                      <div className="flex items-start gap-3 mb-3">
                        <h3 className="font-semibold text-slate-900 flex-1 text-lg">{source.title}</h3>
                        {source.recommended && (
                          <span className="px-3 py-1 bg-gradient-to-r from-green-100 to-emerald-100 text-green-700 text-xs rounded-full font-semibold shadow-sm">
                            推荐
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-600 mb-3">
                        {source.authors} – {source.year} – {source.domain}
                      </p>
                      <p className="text-sm text-slate-700 leading-relaxed mb-3">… {source.excerpt} …</p>
                      <div className="flex items-center gap-4">
                        <span className="text-xs text-slate-500 flex items-center gap-1">
                          <span className="font-medium text-blue-600">被引 {source.cited}</span>
                        </span>
                        <button 
                          onClick={(e) => {
                            e.stopPropagation();
                          }}
                          className="ml-auto inline-flex items-center gap-1 text-blue-600 text-sm font-medium hover:text-blue-700 hover:underline"
                        >
                          <ExternalLink size={14} />
                          打开链接
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="bg-white/90 rounded-2xl shadow-lg border border-white/70 px-8 py-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <File size={22} className="text-blue-600" />
            <span className="font-semibold text-slate-900">已选择引用来源：<span className="text-blue-600">{selectedSources.length}</span> 个</span>
          </div>
          <button
            onClick={handleGenerateDraft}
            disabled={selectedSources.length === 0 || isUploading}
            className="px-8 py-3 bg-gradient-to-r from-blue-500 via-blue-600 to-blue-700 text-white text-sm font-semibold rounded-xl shadow-lg shadow-blue-500/30 hover:shadow-blue-500/40 disabled:bg-gray-300 disabled:shadow-none disabled:cursor-not-allowed transition-all"
          >
            生成草稿
          </button>
        </div>
      </div>
    </div>
  );
}
