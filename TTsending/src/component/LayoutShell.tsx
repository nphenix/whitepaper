import Sidebar from './Siderbar';
import Editor from './Editor';

export default function LayoutShell() {
  return (
    <div className="max-w-[1400px] mx-auto py-10 px-6 lg:px-10">
      <div className="flex flex-col lg:flex-row bg-white/50 rounded-[36px] border border-white/60 shadow-[0_20px_80px_rgba(79,134,255,0.18)] backdrop-blur-lg overflow-hidden">
        <Sidebar />
        <Editor />
      </div>
    </div>
  );
}
