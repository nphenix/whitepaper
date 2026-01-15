import { useState, useEffect, useRef } from 'react';
import { useLocation, useSearchParams, useNavigate } from 'react-router-dom';
import { Send, Globe, LibraryBig, FileSearch, ChevronLeft, ChevronRight, ExternalLink, Sparkles, Languages, CheckCircle2, Bot, Search, MessageSquare, History, BookOpen, Lightbulb, ChevronDown, Bell, HelpCircle, User } from 'lucide-react';
import { API_URL } from '../config/api';
import RichTextEditor from '../component/RichTextEditor';
import logoImage from '../assets/ttsending-logo.png';

type AssistantMode = 'search' | 'assistant';

export default function FinalView() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const outlineId = searchParams.get('id') || location.state?.outlineId;
  
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [draftContent, setDraftContent] = useState('');
  const [sources, setSources] = useState<any[]>([]);
  const [selectedSources, setSelectedSources] = useState<number[]>([]);
  const [chatMessages, setChatMessages] = useState<Array<{role: string, content: string}>>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [assistantMode, setAssistantMode] = useState<AssistantMode>('assistant');
  const [showModeDropdown, setShowModeDropdown] = useState(false);
  
  const [showAIPopup, setShowAIPopup] = useState(false);
  const [popupPosition, setPopupPosition] = useState({ x: 0, y: 0 });
  const [selectedText, setSelectedText] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const sseRef = useRef<EventSource | null>(null);

  const quickActionsConfig = {
    search: [
      { icon: History, label: '搜索历史记录', action: '帮我搜索之前的历史记录' },
      { icon: BookOpen, label: '浏览知识库', action: '在知识库中查找相关内容' },
      { icon: Globe, label: '联网搜索', action: '帮我进行联网搜索' }
    ],
    assistant: [
      { icon: MessageSquare, label: '提问咨询', action: '我有一个关于白皮书的问题' },
      { icon: Languages, label: '翻译内容', action: '帮我翻译这段内容' },
      { icon: Sparkles, label: '润色文本', action: '帮我润色这段文字' },
      { icon: Lightbulb, label: '分析洞察', action: '帮我分析这篇白皮书的核心观点' }
    ]
  };

  const currentPlaceholder = assistantMode === 'search' 
    ? '搜索历史、知识库或联网资源...' 
    : '提问、咨询、翻译或润色...';

  useEffect(() => {
    fetchDraft();
    return () => {
      // 组件卸载时关闭 SSE
      if (sseRef.current) {
        sseRef.current.close();
        sseRef.current = null;
      }
    };
  }, [outlineId]);

  const loadMockData = () => {
    setDraftContent(`<h1>未来五年储能产业政策与发展趋势白皮书</h1>

<h2>一、执行摘要</h2>
<p>本白皮书深入分析了2025-2030年间全球及中国储能产业的政策环境、市场趋势和技术发展方向。随着全球能源转型加速，储能作为新型电力系统的关键支撑技术，正迎来前所未有的发展机遇。</p>

<h2>二、政策环境分析</h2>
<h3>2.1 国际政策趋势</h3>
<p>美国《通胀削减法案》(IRA)提供了约3690亿美元的清洁能源投资，其中储能项目可获得30%的投资税收抵免。欧盟"Fit for 55"计划要求到2030年可再生能源占比达到40%，极大促进了储能需求。</p>

<h3>2.2 中国政策框架</h3>
<p>国家能源局发布的《新型储能发展实施方案(2024-2027)》明确提出，到2027年新型储能装机规模达到9700万千瓦以上。各省市也相继出台了补贴政策，如山东省对储能项目给予0.3-0.5元/kWh的放电补贴。</p>

<h2>三、市场规模预测</h2>
<p>根据彭博新能源财经(BNEF)预测，全球储能市场规模将从2024年的890亿美元增长至2030年的4200亿美元，复合年增长率达29.6%。中国市场占比预计将超过40%。</p>

<h2>四、技术发展方向</h2>
<ul>
<li><strong>锂离子电池</strong>：成本持续下降，预计2027年降至100美元/kWh以下</li>
<li><strong>钠离子电池</strong>：宁德时代、中科海钠等企业已实现商业化应用</li>
<li><strong>液流电池</strong>：适合长时储能场景，正在示范项目中验证</li>
<li><strong>压缩空气储能</strong>：大规模、低成本储能的重要选择</li>
</ul>

<h2>五、投资机会与风险</h2>
<h3>5.1 主要机会</h3>
<p>工商业储能、户用储能、电网侧储能三大应用场景均呈现快速增长态势。特别是工商业储能，在峰谷价差套利模式下，投资回收期已缩短至5-6年。</p>

<h3>5.2 潜在风险</h3>
<p>需要关注政策变动风险、技术迭代风险、市场竞争加剧等因素。建议投资者密切关注各地电价政策、安全标准更新等。</p>

<h2>六、结论与建议</h2>
<p>未来五年是储能产业发展的黄金期。建议企业把握政策窗口期，加大技术研发投入，拓展多元化应用场景，构建完善的产业生态链。</p>`);
    
    setSources([
      {
        id: 1,
        title: '中国储能产业发展白皮书(2024)',
        authors: '中国能源研究会',
        year: '2024',
        domain: '能源政策',
        excerpt: '系统分析了中国储能产业现状、政策环境、技术路线和市场前景...',
        cited: 156
      },
      {
        id: 2,
        title: 'Global Energy Storage Market Outlook 2024-2030',
        authors: 'Bloomberg NEF',
        year: '2024',
        domain: '市场研究',
        excerpt: 'Comprehensive analysis of global energy storage deployment trends, cost projections...',
        cited: 289
      },
      {
        id: 3,
        title: '新型储能发展实施方案(2024-2027)',
        authors: '国家能源局',
        year: '2024',
        domain: '政策文件',
        excerpt: '明确了新型储能发展目标、重点任务和保障措施...',
        cited: 423
      }
    ]);
    setSelectedSources([1, 2, 3]);
  };

  const fetchDraft = async () => {
    if (!outlineId) {
      // Load mock data for demo
      loadMockData();
      setIsLoading(false);
      return;
    }
    try {
      setDraftError(null);
      const fetchWithTimeout = async (input: RequestInfo | URL, init?: RequestInit, timeoutMs: number = 15000) => {
        const controller = new AbortController();
        const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
        try {
          return await fetch(input, { ...init, signal: controller.signal });
        } finally {
          window.clearTimeout(timeoutId);
        }
      };

      // 关键：不允许“API失败就降级到 mock”，否则 e2e 会直接失败（mock_detector）
      // 改为 SSE：订阅后端推送的生成状态，避免前端高频轮询。

      // 尝试触发一次生成：如果后端返回明确错误，直接展示（避免一直轮询到超时）
      try {
        const genResp = await fetchWithTimeout(`${API_URL}/generate-draft/${outlineId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        }, 15000);
        const genRaw: any = await genResp.json().catch(() => null);
        if (genRaw && genRaw.success === false) {
          const msg = genRaw.error || genRaw.message || '草稿生成启动失败';
          setDraftError(msg);
          return;
        }
      } catch (e) {
        // 网络错误：继续走轮询（sources 页面也可能已触发过生成）
        console.warn('触发草稿生成失败(将继续轮询draft):', e);
      }

      // 关闭旧 SSE（如果有）
      if (sseRef.current) {
        sseRef.current.close();
        sseRef.current = null;
      }

      // 关键：草稿生成可能很久（按章节生成），不要用 5 分钟硬超时误判失败。
      // 改为：
      // - 无输出超时：长时间收不到 status/done/error 事件时才提示（通常是网络/代理问题）
      // - 总等待上限：防止无限等待
      const inactivityTimeoutMs = 3 * 60 * 1000; // 3min 无任何事件输出
      const maxWaitMs = 2 * 60 * 60 * 1000; // 2h 总等待兜底
      let inactivityTimerId: number | null = null;
      const resetInactivityTimeout = () => {
        if (inactivityTimerId) window.clearTimeout(inactivityTimerId);
        inactivityTimerId = window.setTimeout(() => {
          setDraftError('等待草稿生成中（长时间无进度回传），请检查网络/代理配置，或稍后刷新重试');
          // 不强制终止：EventSource 会自动重连；用户也可刷新
        }, inactivityTimeoutMs);
      };
      resetInactivityTimeout();

      const hardTimeoutId = window.setTimeout(() => {
        if (sseRef.current) {
          sseRef.current.close();
          sseRef.current = null;
        }
        setDraftError('等待草稿生成超时（已超过最长等待时间）');
        setIsLoading(false);
      }, maxWaitMs);

      // 使用相对 URL（走 Vite proxy）订阅 SSE
      const es = new EventSource(`${API_URL}/draft/${outlineId}/events`);
      sseRef.current = es;

      es.addEventListener('status', (evt: MessageEvent) => {
        resetInactivityTimeout();
        try {
          const data = JSON.parse(evt.data || '{}');
          // 这里可选：你可以把 data.progress 显示为进度条
          // console.debug('draft status:', data);
          // 注意：timeout 在后端可能代表 SSE 连接周期结束/重连，不应当直接判为失败
          if (data?.state === 'failed' || data?.state === 'cancelled') {
            const msg = data?.message || '草稿生成失败';
            setDraftError(msg);
            if (inactivityTimerId) window.clearTimeout(inactivityTimerId);
            window.clearTimeout(hardTimeoutId);
            es.close();
            sseRef.current = null;
            setIsLoading(false);
          } else {
            // 收到状态更新后清掉旧错误提示（比如之前有“无进度回传”提示）
            setDraftError(null);
          }
        } catch {
          // ignore
        }
      });

      es.addEventListener('done', async (evt: MessageEvent) => {
        try {
          const data = JSON.parse(evt.data || '{}');
          const draftText = data?.draft;
          if (typeof draftText === 'string' && draftText.trim().length > 0) {
            setDraftContent(draftText);
          }
        } finally {
          if (inactivityTimerId) window.clearTimeout(inactivityTimerId);
          window.clearTimeout(hardTimeoutId);
          es.close();
          sseRef.current = null;
        }

        // 获取来源信息（可选）
        try {
          const sourcesResponse = await fetchWithTimeout(`${API_URL}/sources/${outlineId}`, undefined, 15000);
          const sourcesRaw = await sourcesResponse.json();
          const sourcesPayload = sourcesRaw?.data ?? sourcesRaw;
          const sourcesList = sourcesPayload?.sources ?? sourcesRaw?.sources;
          if (sourcesRaw?.success && Array.isArray(sourcesList)) {
            setSources(sourcesList);
          }
        } catch {
          // ignore
        } finally {
          setIsLoading(false);
        }
      });

      es.addEventListener('error', (evt: any) => {
        // 两类 error：
        // 1) 浏览器连接错误（无 evt.data）：EventSource 会自动重连，不应立刻判失败
        // 2) 服务端推送 event: error（有 evt.data）：包含失败信息，应展示给用户
        try {
          const raw = typeof evt?.data === 'string' ? evt.data : '';
          if (raw && raw.trim()) {
            const data = JSON.parse(raw);
            const state = data?.state;
            // timeout 多半是连接周期结束/重连，忽略即可；failed/cancelled 才算真正失败
            if (state === 'failed' || state === 'cancelled') {
              const msg = data?.message || '草稿生成失败';
              setDraftError(msg);
              if (inactivityTimerId) window.clearTimeout(inactivityTimerId);
              window.clearTimeout(hardTimeoutId);
              es.close();
              sseRef.current = null;
              setIsLoading(false);
              return;
            }
            // 非致命错误：提示但继续等待（让浏览器自动重连）
            console.warn('SSE server error event:', data);
          } else {
            console.warn('SSE connection error:', evt);
          }
        } catch (e) {
          console.warn('SSE error parse failed:', e);
        }
      });
    } catch (error) {
      console.error('Error fetching draft:', error);
    } finally {
      // 由 SSE done/timeout 控制 isLoading；这里不要强制置 false
    }
  };

  const handleQuickAction = (actionText: string) => {
    setInputMessage(actionText);
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim()) return;
    
    const userMessage = inputMessage;
    setInputMessage('');
    setChatMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsSending(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage, outlineId, mode: assistantMode })
      });
      
      const data = await response.json();
      
      if (data.success) {
        setChatMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
      }
    } catch (error) {
      console.error('Error sending message:', error);
    } finally {
      setIsSending(false);
    }
  };

  const toggleSource = (id: number) => {
    setSelectedSources(prev =>
      prev.includes(id) ? prev.filter(sid => sid !== id) : [...prev, id]
    );
  };

  const handleTextSelection = () => {
    const selection = window.getSelection();
    const text = selection?.toString().trim();
    
    if (text && text.length > 0) {
      setSelectedText(text);
      const range = selection?.getRangeAt(0);
      const rect = range?.getBoundingClientRect();
      
      if (rect) {
        setPopupPosition({
          x: rect.left + rect.width / 2,
          y: rect.top - 10
        });
        setShowAIPopup(true);
      }
    } else {
      setShowAIPopup(false);
    }
  };

  const handleAIAction = async (action: string) => {
    console.log(`AI Action: ${action} for text: ${selectedText}`);
    setShowAIPopup(false);
    // TODO: Implement AI actions
  };

  const handleAIAnalysis = async () => {
    if (!draftContent.trim()) return;
    
    setIsAnalyzing(true);
    
    try {
      const response = await fetch(`${API_URL}/analyze-whitepaper`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: draftContent })
      });
      
      const data = await response.json();
      
      if (data.success && data.analysis) {
        setChatMessages(prev => [...prev, { 
          role: 'assistant', 
          content: `📊 AI分析报告：\n\n${data.analysis}` 
        }]);
      } else {
        alert(data.error || 'AI分析失败，请稍后重试');
      }
    } catch (error) {
      console.error('Error analyzing whitepaper:', error);
      alert('AI分析失败，请检查网络连接');
    } finally {
      setIsAnalyzing(false);
    }
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      setShowAIPopup(false);
      
      const target = event.target as HTMLElement;
      if (!target.closest('.mode-dropdown-container')) {
        setShowModeDropdown(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#E8F4FF] via-white to-[#E0F2FF] flex items-center justify-center">
        <div className="text-xl text-gray-600">生成中...</div>
      </div>
    );
  }

  return (
    <div className="h-screen bg-gradient-to-br from-[#E8F4FF] via-white to-[#E0F2FF] flex flex-col">
      <header className="bg-gradient-to-r from-[#4A90E2] via-[#2F6BCD] to-[#1E5799] text-white shadow-lg">
        {/* Main Header Row - Same as Main Page */}
        <div className="px-6 py-4 border-b border-white/10">
          <div className="flex items-center justify-between">
            {/* Logo and Title - Clickable */}
            <button 
              onClick={() => navigate('/')}
              className="flex items-center gap-3 hover:opacity-90 transition-opacity"
            >
              <div className="w-10 h-10 rounded-xl bg-white/10 backdrop-blur-sm flex items-center justify-center border border-white/20 overflow-hidden">
                <img src={logoImage} alt="TTsending Logo" className="w-full h-full object-cover" />
              </div>
              <div className="flex flex-col items-start">
                <h1 className="text-xl font-semibold tracking-wide">TTsending AI White Paper</h1>
                <p className="text-xs text-white/70">智能生成 · 多源知识融合 · 专业引用较验</p>
              </div>
            </button>
            
            {/* Right Side Icons */}
            <div className="flex items-center gap-4">
              <button className="p-2 rounded-lg hover:bg-white/10 transition-colors" title="通知">
                <Bell size={20} />
              </button>
              <button className="p-2 rounded-lg hover:bg-white/10 transition-colors" title="帮助">
                <HelpCircle size={20} />
              </button>
              <div className="flex items-center gap-3 pl-4 border-l border-white/20">
                <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center">
                  <User size={18} />
                </div>
                <div className="flex flex-col items-start">
                  <span className="text-sm font-medium">能源研究院</span>
                  <span className="text-xs text-white/70">admin@ttsending.ai</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Process Indicator Row */}
        <div className="px-6 py-3">
          <div className="flex items-center justify-center max-w-3xl mx-auto">
            <button 
              onClick={() => navigate('/')}
              className="flex items-center gap-2 hover:opacity-80 transition-opacity group"
            >
              <div className="flex items-center justify-center w-7 h-7 rounded-full bg-white/20 group-hover:bg-white/30 text-white text-xs font-semibold transition-colors">
                1
              </div>
              <span className="text-sm text-white/70 group-hover:text-white transition-colors">开始</span>
            </button>
            <div className="flex-1 h-0.5 bg-white/20 mx-3"></div>
            
            <button 
              onClick={() => navigate('/outline')}
              className="flex items-center gap-2 hover:opacity-80 transition-opacity group"
            >
              <div className="flex items-center justify-center w-7 h-7 rounded-full bg-white/20 group-hover:bg-white/30 text-white text-xs font-semibold transition-colors">
                2
              </div>
              <span className="text-sm text-white/70 group-hover:text-white transition-colors">添加指南</span>
            </button>
            <div className="flex-1 h-0.5 bg-white/20 mx-3"></div>
            
            <button 
              onClick={() => navigate('/sources')}
              className="flex items-center gap-2 hover:opacity-80 transition-opacity group"
            >
              <div className="flex items-center justify-center w-7 h-7 rounded-full bg-white/20 group-hover:bg-white/30 text-white text-xs font-semibold transition-colors">
                3
              </div>
              <span className="text-sm text-white/70 group-hover:text-white transition-colors">选择来源</span>
            </button>
            <div className="flex-1 h-0.5 bg-white/20 mx-3"></div>
            
            <div className="flex items-center gap-2 cursor-default" aria-current="page">
              <div className="flex items-center justify-center w-7 h-7 rounded-full bg-white text-blue-600 text-xs font-semibold shadow-lg">
                4
              </div>
              <span className="text-sm text-white font-semibold">获取草稿</span>
            </div>
          </div>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden relative">
        {/* Managing Source Sidebar */}
        <aside className={`transition-all duration-300 ease-in-out ${isSidebarOpen ? 'w-96' : 'w-0'} overflow-hidden bg-gradient-to-br from-white to-slate-50 border-r border-slate-200`}>
          <div className="w-96 h-full flex flex-col">
            {/* Header */}
            <div className="px-6 py-5 border-b border-slate-200 bg-white">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-gradient-to-br from-blue-500 to-cyan-600 rounded-lg shadow-md">
                  <LibraryBig size={18} className="text-white" />
                </div>
                <h2 className="text-lg font-semibold bg-gradient-to-r from-blue-600 to-cyan-600 bg-clip-text text-transparent">管理信息源</h2>
              </div>
              
              {/* Search Box */}
              <div className="relative">
                <input
                  type="text"
                  placeholder="搜索储能政策、技术趋势、市场数据..."
                  className="w-full pl-10 pr-4 py-2.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-500 transition-all"
                />
                <FileSearch size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              </div>
            </div>

            {/* Tabs */}
            <div className="flex items-center gap-1 px-6 py-3 border-b border-slate-200 bg-gradient-to-r from-white to-slate-50">
              <button className="px-3 py-1.5 text-sm font-medium text-blue-600 border-b-2 border-blue-600 bg-blue-50 rounded-t-lg transition-all">
                已使用
              </button>
              <button className="px-3 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-t-lg transition-all">
                查找新源
              </button>
              <button className="px-3 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-t-lg transition-all">
                推荐
              </button>
            </div>

            {/* Sources List */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
              {sources.map(source => (
                <div
                  key={source.id}
                  className={`pb-4 border-b border-slate-200 last:border-0 ${
                    selectedSources.includes(source.id) ? 'bg-blue-50/30 -mx-2 px-2 rounded-lg' : ''
                  }`}
                >
                  <div className="flex items-start gap-3 mb-2">
                    <input
                      type="checkbox"
                      checked={selectedSources.includes(source.id)}
                      onChange={() => toggleSource(source.id)}
                      className="mt-1 h-4 w-4 text-blue-600 rounded cursor-pointer accent-blue-600"
                    />
                    <div className="flex-1">
                      <h3 className="text-sm font-semibold text-slate-900 mb-1 line-clamp-2">
                        {source.title}
                      </h3>
                      <p className="text-xs text-slate-600 mb-2">
                        {source.authors} - {source.year} - {source.domain}
                      </p>
                      <p className="text-xs text-slate-600 line-clamp-2 mb-3">
                        ... {source.excerpt} ...
                      </p>
                      
                      <div className="flex items-center gap-2">
                        <button className="px-3 py-1 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-700 transition-colors">
                          引用此源
                        </button>
                        <button className="text-xs text-slate-600 hover:text-slate-900 flex items-center gap-1">
                          <ExternalLink size={12} />
                          打开
                        </button>
                        <span className="ml-auto text-xs text-slate-500">被引 {source.cited}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* Toggle Button */}
        <button
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className="absolute left-0 top-1/2 -translate-y-1/2 z-50 bg-white shadow-lg hover:shadow-xl transition-all duration-300 rounded-r-xl border border-l-0 border-blue-200 p-2 hover:bg-blue-50"
          style={{ left: isSidebarOpen ? '384px' : '0px' }}
        >
          {isSidebarOpen ? (
            <ChevronLeft size={20} className="text-blue-600" />
          ) : (
            <ChevronRight size={20} className="text-blue-600" />
          )}
        </button>

        <main className="flex-1 bg-gradient-to-br from-slate-50 via-white to-blue-50 overflow-y-auto relative" onMouseUp={handleTextSelection}>
          <div className="max-w-4xl mx-auto p-8">
            {draftError && (
              <div
                className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
                data-testid="draft-error"
              >
                {draftError}
              </div>
            )}
            {/* AI Analysis Button */}
            <div className="mb-6 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg shadow-lg">
                  <Bot size={20} className="text-white" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                    AI 智能分析
                  </h2>
                  <p className="text-xs text-slate-500">让AI深度分析您的白皮书内容质量、逻辑结构和改进建议</p>
                </div>
              </div>
              <button
                onClick={handleAIAnalysis}
                disabled={isAnalyzing || !draftContent.trim()}
                className="px-5 py-2.5 bg-gradient-to-r from-blue-500 via-blue-600 to-purple-600 text-white font-medium rounded-lg shadow-lg hover:shadow-xl transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 group"
              >
                {isAnalyzing ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                    <span>分析中...</span>
                  </>
                ) : (
                  <>
                    <Sparkles size={18} className="group-hover:rotate-12 transition-transform" />
                    <span>开始分析</span>
                  </>
                )}
              </button>
            </div>

            {/* Draft Editor */}
            <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-8">
              <RichTextEditor 
                content={draftContent} 
                onChange={(html) => setDraftContent(html)}
                editable={true}
              />
            </div>
          </div>

          {/* Notion-style AI Popup for text selection */}
          {showAIPopup && (
            <div
              className="fixed z-50 animate-in fade-in slide-in-from-bottom-2 duration-200"
              style={{
                left: `${popupPosition.x}px`,
                top: `${popupPosition.y}px`,
                transform: 'translate(-50%, -100%)'
              }}
              onMouseDown={(e) => e.stopPropagation()}
            >
              <div className="bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden min-w-[240px]">
                <div className="p-2">
                  <div className="text-xs text-slate-500 px-3 py-2 font-medium">编辑或审阅所选内容</div>
                  
                  <button
                    onClick={() => handleAIAction('polish')}
                    className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-gradient-to-r hover:from-blue-50 hover:to-blue-100 rounded-lg transition-all group"
                  >
                    <Sparkles size={16} className="text-blue-600 group-hover:text-blue-700" />
                    <span className="text-sm text-slate-700 group-hover:text-slate-900 font-medium">AI润色</span>
                  </button>
                  
                  <button
                    onClick={() => handleAIAction('grammar')}
                    className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-gradient-to-r hover:from-green-50 hover:to-emerald-100 rounded-lg transition-all group"
                  >
                    <CheckCircle2 size={16} className="text-green-600 group-hover:text-green-700" />
                    <span className="text-sm text-slate-700 group-hover:text-slate-900 font-medium">修复语法错误</span>
                  </button>
                  
                  <button
                    onClick={() => handleAIAction('translate')}
                    className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-gradient-to-r hover:from-purple-50 hover:to-purple-100 rounded-lg transition-all group"
                  >
                    <Languages size={16} className="text-purple-600 group-hover:text-purple-700" />
                    <span className="text-sm text-slate-700 group-hover:text-slate-900 font-medium">AI翻译</span>
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>

        <aside className="w-96 bg-gradient-to-br from-slate-50 via-white to-slate-50 border-l border-slate-200 flex flex-col">
          {chatMessages.length === 0 ? (
            <div className="flex-1 flex flex-col">
              <div className="flex-1 flex flex-col items-center justify-center px-8 py-12">
                <div className="w-20 h-20 mb-6 bg-gradient-to-br from-purple-500 via-blue-600 to-cyan-500 rounded-3xl shadow-xl flex items-center justify-center transform hover:scale-105 transition-transform">
                  <Bot size={36} className="text-white" />
                </div>
                
                <h2 className="text-2xl font-semibold text-slate-800 mb-2 text-center">
                  今天需要什么帮助？
                </h2>
                <p className="text-sm text-slate-500 mb-10 text-center">
                  {assistantMode === 'search' ? '搜索历史、知识库和在线资源' : '提问、咨询、翻译和润色您的内容'}
                </p>

                <div className="w-full space-y-3 mb-8">
                  {quickActionsConfig[assistantMode].map((action, index) => {
                    const Icon = action.icon;
                    return (
                      <button
                        key={index}
                        onClick={() => handleQuickAction(action.action)}
                        className="w-full flex items-center gap-4 px-5 py-4 bg-white hover:bg-gradient-to-r hover:from-blue-50 hover:to-purple-50 rounded-xl border border-slate-200 hover:border-blue-300 shadow-sm hover:shadow-md transition-all group"
                      >
                        <div className="p-2 bg-gradient-to-br from-slate-100 to-slate-200 group-hover:from-blue-100 group-hover:to-purple-100 rounded-lg transition-all">
                          <Icon size={18} className="text-slate-600 group-hover:text-blue-600 transition-colors" />
                        </div>
                        <span className="text-sm font-medium text-slate-700 group-hover:text-slate-900">
                          {action.label}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto p-6">
              <div className="space-y-4">
                {chatMessages.map((msg, index) => (
                  <div
                    key={index}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[85%] px-4 py-3 rounded-2xl shadow-sm ${
                        msg.role === 'user'
                          ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white'
                          : 'bg-white border border-slate-200 text-slate-900'
                      }`}
                    >
                      <p className="text-sm whitespace-pre-line leading-relaxed">{msg.content}</p>
                    </div>
                  </div>
                ))}
                {isSending && (
                  <div className="flex justify-start">
                    <div className="bg-white border border-slate-200 px-4 py-3 rounded-2xl shadow-sm">
                      <div className="flex gap-1">
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
                        <div className="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                        <div className="w-2 h-2 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="p-4 bg-white border-t border-slate-200">
            <div className="relative mb-3 mode-dropdown-container">
              <button
                onClick={() => setShowModeDropdown(!showModeDropdown)}
                className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-lg transition-all"
              >
                {assistantMode === 'search' ? (
                  <>
                    <Search size={16} />
                    <span className="font-medium">Search</span>
                  </>
                ) : (
                  <>
                    <Bot size={16} />
                    <span className="font-medium">Assistant</span>
                  </>
                )}
                <ChevronDown size={14} className={`ml-1 transition-transform ${showModeDropdown ? 'rotate-180' : ''}`} />
              </button>

              {showModeDropdown && (
                <div className="absolute bottom-full mb-2 left-0 w-64 bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden z-50 animate-in fade-in slide-in-from-bottom-2 duration-200">
                  <div className="p-2">
                    <div className="text-xs text-slate-500 px-3 py-2 font-semibold uppercase tracking-wide">切换模式</div>
                    
                    <button
                      onClick={() => {
                        setAssistantMode('search');
                        setShowModeDropdown(false);
                      }}
                      className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg transition-all ${
                        assistantMode === 'search'
                          ? 'bg-gradient-to-r from-blue-50 to-blue-100 text-blue-700'
                          : 'hover:bg-slate-50 text-slate-700'
                      }`}
                    >
                      <Search size={18} className={assistantMode === 'search' ? 'text-blue-600' : 'text-slate-500'} />
                      <div className="flex-1 text-left">
                        <div className="text-sm font-semibold">Search</div>
                        <div className="text-xs text-slate-500">搜索历史、知识库和在线资源</div>
                      </div>
                      {assistantMode === 'search' && (
                        <div className="w-1.5 h-1.5 bg-blue-600 rounded-full"></div>
                      )}
                    </button>
                    
                    <button
                      onClick={() => {
                        setAssistantMode('assistant');
                        setShowModeDropdown(false);
                      }}
                      className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg transition-all ${
                        assistantMode === 'assistant'
                          ? 'bg-gradient-to-r from-purple-50 to-purple-100 text-purple-700'
                          : 'hover:bg-slate-50 text-slate-700'
                      }`}
                    >
                      <Bot size={18} className={assistantMode === 'assistant' ? 'text-purple-600' : 'text-slate-500'} />
                      <div className="flex-1 text-left">
                        <div className="text-sm font-semibold">Assistant</div>
                        <div className="text-xs text-slate-500">提问、咨询、翻译和润色</div>
                      </div>
                      {assistantMode === 'assistant' && (
                        <div className="w-1.5 h-1.5 bg-purple-600 rounded-full"></div>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
                placeholder={currentPlaceholder}
                className="flex-1 px-4 py-3 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all placeholder:text-slate-400"
              />
              <button
                onClick={handleSendMessage}
                disabled={!inputMessage.trim() || isSending}
                className="px-4 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all hover:scale-105 active:scale-95"
              >
                <Send size={18} />
              </button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
