import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { CheckCircle, Sparkles, ChevronLeft, ChevronRight, FileSearch, Archive, LibraryBig, Bot, Database, ChevronDown } from 'lucide-react';
import { API_URL } from '../config/api';

export default function OutlineCreation() {
  const navigate = useNavigate();
  const location = useLocation();
  const config = location.state?.config || {};
  
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [showSources, setShowSources] = useState(true);
  
  const historyRecords = [
    { id: 1, title: '国内储能政策调研', date: '2025/10/15' },
    { id: 2, title: '国外储能政策', date: '2025/10/12' },
    { id: 3, title: '储能市场规模', date: '2025/10/08' },
  ];

  const sourceData = [
    { name: '国家能源局公告2025-08', type: '政策PDF', size: '2.4MB' },
    { name: '能源企业调研问卷', type: '问卷Excel', size: '540KB' },
    { name: '市场交易数据', type: 'CSV数据集', size: '1.8MB' },
  ];

  const [outlineText, setOutlineText] = useState(`生成一份《未来五年储能产业政策与发展趋势白皮书》。
白皮书需体现以下特征：
        •       有国家战略高度（政策导向+产业落地）
        •       有数据与趋势支撑（引用公开数据或预测模型）
        •       有结构化逻辑（问题→分析→对策→展望）
        •       有前瞻性与可操作性（政策建议、风险分析、路径图）

1. 前言与战略定位
- 阐明储能产业在"双碳"与能源安全格局下的重要性
- 总结过去五年储能政策演变与成就
- 提出未来五年面临的挑战与转折点

2. 全球储能政策与市场格局
- 分析主要经济体（中国、欧盟、美国、日韩等）储能政策差异
- 对比补贴机制、市场机制、技术路线
- 提炼国际经验对本国的启示

3. 国内储能政策体系回顾与演变
- 按阶段梳理政策：示范期→规模化→市场化→智能化
- 分析政策目标、执行主体、监管模式的变化
- 识别政策空白与碎片化问题

4. 技术路径与创新趋势分析
- 电化学储能（锂电、钠电、液流电池等）
- 机械储能（压缩空气、飞轮、重力）
- 热储能与氢能耦合
- 智能调度与数字孪生技术
- 前沿趋势（固态电池、系统集成创新）

5. 储能商业模式与市场机制创新
- 电网侧、用户侧、发电侧市场分析
- "储能+"应用场景：新能源并网、工商业用电优化、虚拟电厂
- 盈利模式、交易机制与价格信号
- 投融资结构、资本进入趋势

6. 政策挑战与监管框架优化
- 标准体系不统一、审批周期长、收益不确定等问题
- 市场主体博弈：电网、发电商、储能商、地方政府
- 法规建议：容量市场、容量补偿机制、辅助服务定价

7. 未来五年政策方向与发展路径图
- 政策预测与建议（阶段性目标、激励机制、市场化深化）
- 关键领域政策重点（安全标准、梯次利用、产业链本土化）
- 发展情景推演（基准/积极/保守）

8. 结论与政策建议摘要
- 对政府、企业、研究机构的差异化建议
- 对投资者的风险提示与信号
- 对社会公众的沟通与普及策略`);

  const [isOptimizing, setIsOptimizing] = useState(false);
  const [isPolishing, setIsPolishing] = useState(false);
  const [polishError, setPolishError] = useState<string | null>(null);
  const [continueError, setContinueError] = useState<string | null>(null);

  const handlePolish = async () => {
    if (!outlineText.trim()) return;
    
    setIsPolishing(true);
    setPolishError(null);
    
    try {
      // 方案C：真正消费后端流式响应（SSE）。
      // 使用“无输出超时”(inactivity timeout)：只要服务端持续推送数据/心跳，就不会超时。
      const controller = new AbortController();
      const inactivityTimeoutMs = 180_000; // 与后端 LLM_TIMEOUT 默认一致；服务端会持续发送心跳以保持连接活跃
      let timeoutId = window.setTimeout(() => controller.abort(), inactivityTimeoutMs);
      const resetInactivityTimeout = () => {
        window.clearTimeout(timeoutId);
        timeoutId = window.setTimeout(() => controller.abort(), inactivityTimeoutMs);
      };

      const response = await fetch(`${API_URL}/polish-outline?stream=1`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({ outlineText }),
        signal: controller.signal,
      });
      resetInactivityTimeout();

      const contentType = response.headers.get('content-type') || '';

      // 兼容：如果后端未返回 SSE，则按旧 JSON 逻辑处理
      if (!contentType.includes('text/event-stream')) {
        window.clearTimeout(timeoutId);
        const data = await response.json();
        if (data.success && data.data && data.data.polishedOutline) {
          setOutlineText(data.data.polishedOutline);
        } else {
          const errorMessage = data.error || data.message || 'AI优化失败，请稍后重试';
          setPolishError(errorMessage);
          console.error('API返回错误:', data);
        }
        return;
      }

      if (!response.body) {
        throw new Error('流式响应不可用：response.body 为空');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let fullText = '';
      let lastUiUpdate = 0;

      const flushUi = () => {
        const now = Date.now();
        // 限流：避免每个 token 都触发一次 React render
        if (now - lastUiUpdate > 120) {
          lastUiUpdate = now;
          setOutlineText(fullText);
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        resetInactivityTimeout();
        buffer += decoder.decode(value, { stream: true });

        let sepIndex: number;
        while ((sepIndex = buffer.indexOf('\n\n')) >= 0) {
          const rawEvent = buffer.slice(0, sepIndex).trim();
          buffer = buffer.slice(sepIndex + 2);

          // 心跳（SSE 注释）: `: ping`
          if (!rawEvent || rawEvent.startsWith(':')) continue;

          let eventName = 'message';
          const dataLines: string[] = [];

          for (const line of rawEvent.split('\n')) {
            if (line.startsWith('event:')) {
              eventName = line.slice('event:'.length).trim();
            } else if (line.startsWith('data:')) {
              dataLines.push(line.slice('data:'.length).trim());
            }
          }

          const dataStr = dataLines.join('\n');
          const payload = dataStr ? JSON.parse(dataStr) : null;

          if (eventName === 'delta' && payload?.text) {
            fullText += payload.text as string;
            flushUi();
          } else if (eventName === 'done') {
            if (payload?.polishedOutline) {
              fullText = payload.polishedOutline as string;
            }
            setOutlineText(fullText);
          } else if (eventName === 'error') {
            const msg = payload?.message || 'AI优化失败，请稍后重试';
            throw new Error(msg);
          }
        }
      }

      window.clearTimeout(timeoutId);
      if (fullText.trim()) setOutlineText(fullText);
    } catch (error) {
      console.error('Error polishing outline:', error);
      // AbortError / DOMException：超时或用户终止
      if (error instanceof DOMException && error.name === 'AbortError') {
        setPolishError('AI优化超时，请稍后重试（建议缩短大纲内容或稍后再试）');
      } else {
        const msg = error instanceof Error ? error.message : 'AI优化失败，请检查网络连接';
        setPolishError(msg || 'AI优化失败，请检查网络连接');
      }
    } finally {
      // 注意：此处不再依赖按钮文本变化来判断完成，而是以 SSE 结束为准
      setIsPolishing(false);
    }
  };

  const handleContinue = async () => {
    setIsOptimizing(true);
    setContinueError(null);
    
    try {
      const response = await fetch(`${API_URL}/outline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ outlineText, config })
      });
      
      const data = await response.json();
      
      if (data.success && data.data && data.data.outlineId) {
        navigate(`/sources?id=${data.data.outlineId}`, { state: { outlineId: data.data.outlineId, config } });
      } else {
        // 如果API返回错误，显示错误信息
        const errorMessage = data.error || data.message || '创建大纲失败，请稍后重试';
        setContinueError(errorMessage);
        console.error('API返回错误:', data);
      }
    } catch (error) {
      console.error('Error saving outline:', error);
      // Navigate to sources page even if API fails (for demo purposes)
      const demoId = Date.now().toString();
      navigate(`/sources?id=${demoId}`, { state: { outlineId: demoId, config } });
    } finally {
      setIsOptimizing(false);
    }
  };

  const charCount = outlineText.length;

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#E8F4FF] via-white to-[#E0F2FF] flex">
      {/* Collapsible Sidebar */}
      <aside className={`transition-all duration-300 ease-in-out ${isSidebarOpen ? 'w-80' : 'w-0'} overflow-hidden bg-gradient-to-b from-blue-50/80 via-white to-blue-100/40 backdrop-blur-sm border-r border-white/60`}>
        <div className="w-80 px-6 py-6 space-y-6">
          <div className="flex items-center justify-between">
            <button
              className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-3 rounded-2xl bg-gradient-to-r from-[#4A90E2] via-[#2F6BCD] to-[#1E5799] text-white text-sm font-semibold shadow-[0_12px_30px_rgba(36,99,214,0.25)] hover:shadow-[0_16px_40px_rgba(36,99,214,0.35)] transition-all duration-300"
              onClick={() => navigate('/')}
            >
              + 新建白皮书
            </button>
          </div>

          <section>
            <h2 className="text-lg font-semibold text-slate-900 mb-3 flex items-center gap-2">
              <FileSearch size={18} className="text-blue-600" />
              储能历史记录
            </h2>
            <div className="space-y-3">
              {historyRecords.map(record => (
                <button
                  key={record.id}
                  className="group w-full text-left px-4 py-3 rounded-xl transition-all duration-300 border border-transparent flex flex-col gap-1 hover:bg-white/70 hover:shadow-md hover:shadow-blue-200/30"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-900">{record.title}</span>
                    <Archive size={16} className="text-slate-400 group-hover:text-blue-500 transition-colors" />
                  </div>
                  <span className="text-xs text-slate-500">创建于 {record.date}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="bg-white/80 rounded-2xl p-5 shadow-lg shadow-blue-200/30 border border-white/70 transition-all hover:shadow-blue-300/40">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shadow-inner">
                  <LibraryBig size={20} className="text-white" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-slate-900">知识库</h3>
                  <p className="text-xs text-slate-500 mt-0.5">已开启专业储能知识库对接</p>
                </div>
              </div>
              <span className="px-3 py-1 text-xs font-medium rounded-full bg-cyan-100 text-cyan-600 shadow-sm">3个可用</span>
            </div>
            <p className="text-xs text-slate-500 mt-3 leading-5">
              支持政策法规、标准文件、市场研究等多源知识库关联,一键调用。
            </p>
          </section>

          <section className="bg-white/80 rounded-2xl p-5 shadow-lg shadow-blue-200/30 border border-white/70 transition-all hover:shadow-blue-300/40">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-indigo-500 to-blue-700 flex items-center justify-center shadow-inner">
                  <Bot size={20} className="text-white" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-slate-900">数据抽取Agent</h3>
                  <p className="text-xs text-slate-500 mt-0.5">AI驱动字段识别与摘要提取</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.6)]" />
                <span className="text-xs font-medium text-emerald-600">运行中</span>
              </div>
            </div>
          </section>

          <section className="bg-white/75 rounded-2xl border border-white/60 shadow-md shadow-blue-200/20">
            <button
              onClick={() => setShowSources(prev => !prev)}
              className="w-full flex items-center justify-between px-5 py-4 text-sm font-semibold text-slate-800 hover:bg-blue-50/70 rounded-2xl transition-colors"
            >
              <span className="flex items-center gap-2">
                <Database size={18} className="text-blue-600" />
                源数据汇总
              </span>
              <ChevronDown
                size={18}
                className={`transition-transform duration-300 ${showSources ? 'rotate-180 text-blue-600' : 'text-slate-400'}`}
              />
            </button>
            {showSources && (
              <div className="px-5 pb-5 space-y-3">
                {sourceData.map(item => (
                  <div
                    key={item.name}
                    className="bg-blue-50/70 border border-blue-100 rounded-xl px-4 py-3 flex items-center justify-between text-sm shadow-sm"
                  >
                    <div>
                      <p className="font-medium text-slate-800">{item.name}</p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {item.type} · {item.size}
                      </p>
                    </div>
                    <span className="text-xs font-medium text-blue-500">预览</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </aside>

      {/* Toggle Button */}
      <button
        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
        className="fixed left-0 top-1/2 -translate-y-1/2 z-50 bg-white shadow-lg hover:shadow-xl transition-all duration-300 rounded-r-xl border border-l-0 border-blue-200 p-2 hover:bg-blue-50"
        style={{ left: isSidebarOpen ? '320px' : '0px' }}
      >
        {isSidebarOpen ? (
          <ChevronLeft size={20} className="text-blue-600" />
        ) : (
          <ChevronRight size={20} className="text-blue-600" />
        )}
      </button>

      {/* Main Content */}
      <div className={`flex-1 transition-all duration-300 ${isSidebarOpen ? 'ml-0' : 'ml-0'}`}>
        <div className="max-w-4xl mx-auto px-6 py-12">
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
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm font-semibold">
                2
              </div>
              <span className="text-sm font-medium text-gray-900">添加指南</span>
            </div>
            <div className="h-0.5 w-12 bg-gray-300"></div>
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-full bg-gray-200 text-gray-500 flex items-center justify-center text-sm font-semibold">
                3
              </div>
              <span className="text-sm text-gray-500">选择来源</span>
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

        <div className="bg-white rounded-2xl shadow-lg p-8">
          <h1 className="text-3xl font-bold mb-2">
            粘贴、输入或 <span className="text-blue-600 underline cursor-pointer">上传</span> 白皮书指南要求：
          </h1>
          <p className="text-gray-600 mb-6">主题、结构、关键要点等</p>

          <div className="mb-6">
            <textarea
              value={outlineText}
              onChange={(e) => setOutlineText(e.target.value)}
              className="w-full h-96 p-4 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none text-sm"
              placeholder="输入白皮书大纲..."
            />
          </div>

          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2 text-sm">
              <CheckCircle className="text-green-500" size={18} />
              <span className="text-green-600 font-medium">很好！</span>
              <span className="text-gray-600">看起来我们已经有足够的指导说明了！</span>
            </div>
            <div className="text-sm text-gray-500">
              {charCount.toLocaleString()}/10,500
            </div>
          </div>

          <div className="flex items-center justify-between gap-4">
            <button
              onClick={handlePolish}
              disabled={isPolishing || !outlineText.trim()}
              className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-500 to-purple-600 text-white rounded-xl font-semibold hover:from-purple-600 hover:to-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-all shadow-md hover:shadow-lg"
            >
              <Sparkles size={18} className={isPolishing ? 'animate-spin' : ''} />
              {isPolishing ? 'AI优化中...' : 'AI润色优化'}
            </button>
            {polishError ? (
              <div
                data-testid="polish-error"
                className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 flex-1"
              >
                {polishError}
              </div>
            ) : null}
            <button
              onClick={handleContinue}
              disabled={isOptimizing || !outlineText.trim()}
              className="px-8 py-3 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {isOptimizing ? '处理中...' : '继续'}
            </button>
          </div>
          {continueError ? (
            <div
              data-testid="continue-error"
              className="mt-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2"
            >
              {continueError}
            </div>
          ) : null}
        </div>
      </div>
      </div>
    </div>
  );
}
