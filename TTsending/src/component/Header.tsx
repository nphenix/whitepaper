import { Bell, HelpCircle, User } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import logoImage from '../assets/ttsending-logo.png';

export default function MainHeader() {
  const navigate = useNavigate();

  return (
    <header className="h-20 bg-gradient-to-r from-[#4A90E2] via-[#2F6BCD] to-[#1E5799] text-white flex items-center justify-between px-8 shadow-[0_20px_40px_rgba(30,87,153,0.35)]">
      <div className="flex items-center gap-4">
        <button 
          onClick={() => navigate('/')}
          className="flex items-center gap-4 hover:opacity-90 transition-opacity group"
        >
          <div className="h-12 w-12 rounded-2xl overflow-hidden border-2 border-white/70 shadow-lg shadow-blue-900/40 group-hover:border-white transition-colors">
            <img src={logoImage} alt="TTsending Logo" className="h-full w-full object-cover" />
          </div>
          <div className="text-left">
            <h1 className="text-2xl font-semibold">TTsending AI White Paper</h1>
            <p className="text-xs text-blue-50/90 mt-1">智能生成 · 多源知识库融合 · 专业引用校验</p>
          </div>
        </button>
      </div>
      <div className="flex items-center gap-4">
        <button className="p-2.5 hover:bg-white/10 rounded-xl transition-colors" title="消息中心">
          <Bell size={20} />
        </button>
        <button className="p-2.5 hover:bg-white/10 rounded-xl transition-colors" title="反馈">
          <HelpCircle size={20} />
        </button>
        <div className="flex items-center gap-3 bg-white/10 rounded-2xl px-3 py-2">
          <div className="h-10 w-10 rounded-full bg-white/20 flex items-center justify-center text-sm font-semibold">
            T
          </div>
          <div className="text-sm">
            <p className="font-medium">能源研究院</p>
            <p className="text-white/70">admin@ttsending.ai</p>
          </div>
          <button className="p-2 hover:bg-white/10 rounded-xl transition-colors" title="账号设置">
            <User size={18} />
          </button>
        </div>
      </div>
    </header>
  );
}
