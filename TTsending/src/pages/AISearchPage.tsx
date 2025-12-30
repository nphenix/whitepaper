import { useState } from 'react';
import { Search, LibraryBig, Archive, Globe, Sparkles, Loader2, Clock } from 'lucide-react';
import Header from '../component/Header';
import { useSearchHistory } from '../lib/supabase/useSupabase';

export default function AISearchPage() {
  const [activeSource, setActiveSource] = useState<'knowledge' | 'history' | 'web'>('knowledge');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [searchResult, setSearchResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Search history hook (stores locally if Supabase not configured)
  const { history, saveSearch } = useSearchHistory();

  const recommendedQuestions = [
    '✅ 对比国内外储能政策变化',
    '📊 获取 2025 Q3 储能市场预测数据',
    '🧠 查找钠离子储能技术最新突破'
  ];

  // Handle search
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    setLoading(true);
    setError(null);
    setSearchResult(null);
    
    try {
      // TODO: Implement search with new AI framework (Agno)
      // For now, show a placeholder message
      await new Promise(resolve => setTimeout(resolve, 1000));
      setSearchResult('AI 搜索功能正在重构中，即将支持 Agno 框架。请稍后再试。');
    } catch (err) {
      setError(err instanceof Error ? err.message : '搜索出错');
    } finally {
      setLoading(false);
    }
  };

  // Save to history when we get a response
  const handleSaveToHistory = async () => {
    if (searchResult && searchQuery) {
      await saveSearch(searchQuery, searchResult, activeSource);
    }
  };

  // Handle clicking a recommended question
  const handleRecommendedClick = (question: string) => {
    // Remove emoji prefix
    const cleanQuestion = question.replace(/^[^\w\u4e00-\u9fa5]+/, '').trim();
    setSearchQuery(cleanQuestion);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#E8F4FF] via-white to-[#E0F2FF]">
      <Header />
      
      <div className="max-w-4xl mx-auto px-6 py-16">
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-gradient-to-br from-sky-500 to-blue-600 shadow-2xl mb-6 transform hover:scale-105 transition-transform">
            <Search size={36} className="text-white" />
          </div>
          <h1 className="text-4xl font-bold text-slate-900 mb-3">AI 智能检索</h1>
          <p className="text-lg text-slate-600">同步检索知识库、历史记录与实时网络</p>
        </div>

        <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 p-8 mb-8">
          <div className="flex items-center justify-between mb-6">
            <div className="flex gap-2">
              <button
                onClick={() => setActiveSource('knowledge')}
                className={`px-4 py-2.5 text-sm font-medium rounded-xl transition-all ${
                  activeSource === 'knowledge'
                    ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                <div className="flex items-center gap-2">
                  <LibraryBig size={16} />
                  <span>知识库</span>
                </div>
              </button>
              <button
                onClick={() => setActiveSource('history')}
                className={`px-4 py-2.5 text-sm font-medium rounded-xl transition-all ${
                  activeSource === 'history'
                    ? 'bg-gradient-to-r from-cyan-500 to-cyan-600 text-white shadow-lg'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Archive size={16} />
                  <span>历史记录</span>
                </div>
              </button>
              <button
                onClick={() => setActiveSource('web')}
                className={`px-4 py-2.5 text-sm font-medium rounded-xl transition-all ${
                  activeSource === 'web'
                    ? 'bg-gradient-to-r from-slate-500 to-slate-600 text-white shadow-lg'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                <div className="flex items-center gap-2">
                  <Globe size={16} />
                  <span>网络实时</span>
                </div>
              </button>
            </div>
            <span className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-blue-50 text-blue-600 text-sm font-medium">
              <Sparkles size={16} /> 智能增强
            </span>
          </div>

          <div className="relative mb-6">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="输入问题，如: 2025 储能补贴政策"
              className="w-full rounded-2xl border-2 border-slate-200 bg-slate-50/70 px-6 py-4 pr-32 text-base text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-500 transition-all"
            />
            <button
              type="button"
              onClick={handleSearch}
              disabled={loading || !searchQuery.trim()}
              className="absolute right-3 top-1/2 -translate-y-1/2 h-11 px-6 rounded-xl bg-gradient-to-r from-blue-500 to-blue-700 text-white text-sm font-semibold shadow-lg hover:shadow-xl transition-all hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? <Loader2 className="animate-spin" size={18} /> : '检索'}
            </button>
          </div>

          {/* Search Results */}
          {error && (
            <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
              搜索出错: {error}
            </div>
          )}
          
          {searchResult && (
            <div className="mb-6 p-6 rounded-2xl bg-gradient-to-br from-green-50 to-emerald-50 border border-green-200">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-green-800 flex items-center gap-2">
                  <Sparkles size={18} />
                  AI 回答
                </h3>
                <button
                  onClick={handleSaveToHistory}
                  className="text-xs px-3 py-1.5 rounded-lg bg-green-100 hover:bg-green-200 text-green-700 transition-colors flex items-center gap-1"
                >
                  <Clock size={12} />
                  保存到历史
                </button>
              </div>
              <div className="text-slate-700 whitespace-pre-wrap leading-relaxed">
                {searchResult}
              </div>
            </div>
          )}

          {/* Show search history when history tab is active */}
          {activeSource === 'history' && history.length > 0 && (
            <div className="mb-6 space-y-3">
              <h3 className="font-semibold text-slate-700 flex items-center gap-2 mb-4">
                <Clock size={18} />
                搜索历史
              </h3>
              {history.slice(0, 10).map((item) => (
                <div
                  key={item.id}
                  className="p-4 rounded-xl bg-slate-50 border border-slate-200 hover:border-cyan-300 transition-colors cursor-pointer"
                  onClick={() => setSearchQuery(item.query)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <p className="font-medium text-slate-800 mb-1">{item.query}</p>
                      <p className="text-sm text-slate-500 line-clamp-2">{item.response}</p>
                    </div>
                    <span className="text-xs text-slate-400 whitespace-nowrap">
                      {item.created_at ? new Date(item.created_at).toLocaleDateString('zh-CN') : ''}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeSource === 'history' && history.length === 0 && (
            <div className="mb-6 p-8 rounded-2xl bg-slate-50 border border-slate-200 text-center">
              <Clock size={32} className="mx-auto text-slate-300 mb-3" />
              <p className="text-slate-500">暂无搜索历史</p>
              <p className="text-sm text-slate-400 mt-1">你的搜索记录将显示在这里</p>
            </div>
          )}

          {/* Recommended questions */}
          <div className="rounded-2xl bg-gradient-to-br from-slate-50 to-blue-50/30 border border-slate-200 p-6">
            <p className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
              <Sparkles size={16} className="text-blue-500" />
              推荐提问
            </p>
            <div className="space-y-3">
              {recommendedQuestions.map((question, index) => (
                <button
                  key={index}
                  type="button"
                  onClick={() => handleRecommendedClick(question)}
                  className="w-full text-left px-5 py-3.5 rounded-xl bg-white hover:bg-gradient-to-r hover:from-blue-50 hover:to-purple-50 transition-all border border-slate-200 hover:border-blue-300 shadow-sm hover:shadow-md text-sm text-slate-700 font-medium"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="text-center">
          <p className="text-sm text-slate-500">
            正在搜索: <span className="font-semibold text-blue-600">{
              activeSource === 'knowledge' ? '知识库' :
              activeSource === 'history' ? '历史记录' :
              '网络实时数据'
            }</span>
          </p>
        </div>
      </div>
    </div>
  );
}
