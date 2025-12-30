import { useState, useRef, useEffect } from 'react';
import { X, Send, Search, Clock, Database, Globe } from 'lucide-react';

interface Message {
  id: string;
  type: 'user' | 'ai';
  content: string;
  timestamp: Date;
}

interface AIChatProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function AIChat({ isOpen, onClose }: AIChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      type: 'ai',
      content: '您好!我是AI智能检索助手,可以帮您搜索历史记录、本地知识库及网络实时内容。有什么可以帮您的吗?',
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!inputValue.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: inputValue,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');

    // 模拟AI回复
    setTimeout(() => {
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'ai',
        content: `根据您的问题"${inputValue}",我从知识库中找到了相关信息。储能技术是实现碳中和目标的关键支撑技术之一,近年来发展迅速。需要我为您详细展开某个方面的内容吗?`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, aiMessage]);
    }, 1000);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const insertToEditor = (content: string) => {
    // 这里可以实现插入到编辑器的逻辑
    console.log('Insert to editor:', content);
    alert('内容已插入到编辑器!');
  };

  return (
    <aside
      className={`w-[380px] bg-white border-l border-[#E0E6F0] flex flex-col transition-transform duration-300 ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      } fixed right-0 top-16 bottom-0 z-40`}
    >
      {/* 头部 */}
      <div className="p-4 border-b border-[#E0E6F0] flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-[#1A1A1A]">AI智能检索助手</h3>
          <p className="text-xs text-gray-500 mt-1">可搜索历史记录、本地知识库及网络实时内容</p>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-100 rounded transition-colors"
        >
          <X size={20} className="text-gray-600" />
        </button>
      </div>

      {/* 功能选项 */}
      <div className="p-3 border-b border-[#E0E6F0] flex items-center gap-2">
        <button className="flex-1 px-3 py-2 bg-[#F8FAFF] hover:bg-[#EEF3FF] rounded-lg transition-colors flex items-center justify-center gap-2 text-sm">
          <Clock size={16} className="text-[#0066FF]" />
          <span className="text-[#1A1A1A]">历史记录</span>
        </button>
        <button className="flex-1 px-3 py-2 bg-[#F8FAFF] hover:bg-[#EEF3FF] rounded-lg transition-colors flex items-center justify-center gap-2 text-sm">
          <Database size={16} className="text-[#0066FF]" />
          <span className="text-[#1A1A1A]">知识库</span>
        </button>
        <button className="flex-1 px-3 py-2 bg-[#F8FAFF] hover:bg-[#EEF3FF] rounded-lg transition-colors flex items-center justify-center gap-2 text-sm">
          <Globe size={16} className="text-[#0066FF]" />
          <span className="text-[#1A1A1A]">联网搜索</span>
        </button>
      </div>

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map(message => (
          <div
            key={message.id}
            className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className="max-w-[85%]">
              <div
                className={`rounded-2xl px-4 py-2 ${
                  message.type === 'user'
                    ? 'bg-gradient-to-r from-[#4DB8FF] to-[#003399] text-white'
                    : 'bg-[#F8FAFF] text-[#1A1A1A] border border-[#E0E6F0]'
                }`}
              >
                <p className="text-sm leading-relaxed">{message.content}</p>
              </div>
              {message.type === 'ai' && (
                <button
                  onClick={() => insertToEditor(message.content)}
                  className="mt-2 text-xs text-[#0066FF] hover:underline flex items-center gap-1"
                >
                  <Search size={12} />
                  插入到编辑器
                </button>
              )}
              <div className="text-xs text-gray-400 mt-1 px-1">
                {message.timestamp.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* 输入框 */}
      <div className="p-4 border-t border-[#E0E6F0]">
        <div className="flex items-end gap-2">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="输入你的问题..."
            className="flex-1 resize-none border border-[#E0E6F0] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066FF]/20 max-h-32"
            rows={2}
          />
          <button
            onClick={handleSend}
            className="p-2 bg-gradient-to-r from-[#4DB8FF] to-[#003399] text-white rounded-lg hover:opacity-90 transition-opacity flex items-center justify-center"
          >
            <Send size={20} />
          </button>
        </div>
      </div>
    </aside>
  );
}
