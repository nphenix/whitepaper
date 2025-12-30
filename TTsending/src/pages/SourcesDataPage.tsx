import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, HelpCircle, User, Upload, Search, FileText, Image, FileSpreadsheet, File, X } from 'lucide-react';
import logoImage from '../assets/ttsending-logo.png';

interface UploadedFile {
  id: string;
  name: string;
  size: string;
  type: 'pdf' | 'excel' | 'csv' | 'image' | 'other';
  selected: boolean;
}

const mockFiles: UploadedFile[] = [
  { id: '1', name: '国家能源局公告2025-08.pdf', size: '2.4 MB', type: 'pdf', selected: false },
  { id: '2', name: '能源企业调研问卷.xlsx', size: '540 KB', type: 'excel', selected: false },
  { id: '3', name: '市场交易数据.csv', size: '1.44 MB', type: 'csv', selected: false },
  { id: '4', name: 'hero-pattern-swirl.svg', size: '57.43 KB', type: 'image', selected: false },
  { id: '5', name: 'league_rows.csv', size: '1.44 MB', type: 'csv', selected: false },
  { id: '6', name: 'Seasonally Adjusted.xlsx', size: '45.66 KB', type: 'excel', selected: false },
  { id: '7', name: 'image.png', size: '45.66 KB', type: 'image', selected: false },
];

export default function SourcesDataPage() {
  const navigate = useNavigate();
  const [files, setFiles] = useState<UploadedFile[]>(mockFiles);
  const [searchQuery, setSearchQuery] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectAll, setSelectAll] = useState(false);

  const getFileIcon = (type: string) => {
    switch (type) {
      case 'pdf':
        return <FileText className="text-blue-500" size={20} />;
      case 'excel':
        return <FileSpreadsheet className="text-green-500" size={20} />;
      case 'csv':
        return <FileSpreadsheet className="text-green-600" size={20} />;
      case 'image':
        return <Image className="text-yellow-500" size={20} />;
      default:
        return <File className="text-gray-500" size={20} />;
    }
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const uploadedFiles = event.target.files;
    if (!uploadedFiles) return;

    setIsUploading(true);
    setUploadProgress(0);

    const interval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setIsUploading(false);
          return 100;
        }
        return prev + 10;
      });
    }, 200);
  };

  const toggleFile = (id: string) => {
    setFiles(files.map(f => f.id === id ? { ...f, selected: !f.selected } : f));
  };

  const toggleSelectAll = () => {
    const newSelectAll = !selectAll;
    setSelectAll(newSelectAll);
    setFiles(files.map(f => ({ ...f, selected: newSelectAll })));
  };

  const filteredFiles = files.filter(file =>
    file.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#E8F4FF] via-white to-[#E0F2FF] flex flex-col">
      {/* Header - Same as other pages */}
      <header className="bg-gradient-to-r from-[#4A90E2] via-[#2F6BCD] to-[#1E5799] text-white shadow-lg">
        <div className="px-6 py-4">
          <div className="flex items-center justify-between">
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
      </header>

      {/* Main Content */}
      <div className="flex-1 max-w-5xl mx-auto w-full px-8 py-12">
        {/* Upload Section */}
        <div className="bg-white rounded-3xl shadow-xl p-10 mb-8">
          <div className="flex items-start gap-4 mb-8">
            <div className="p-3 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl">
              <Upload className="text-white" size={28} />
            </div>
            <div className="flex-1">
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Upload everything at once</h2>
              <p className="text-gray-600">No batching, no limits, no waiting. Julius supports larger files compared to others</p>
            </div>
          </div>

          {/* Upload Progress */}
          {isUploading && (
            <div className="mb-6 p-5 bg-gray-50 rounded-xl border border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">Uploading File</span>
                <button className="text-gray-400 hover:text-gray-600">
                  <X size={18} />
                </button>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-gradient-to-r from-purple-500 to-blue-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Upload Button */}
          <label className="block cursor-pointer">
            <input 
              type="file" 
              multiple 
              className="hidden" 
              onChange={handleFileUpload}
              accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.png,.jpg,.jpeg,.svg"
            />
            <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-blue-400 hover:bg-blue-50/30 transition-all">
              <Upload className="mx-auto mb-3 text-gray-400" size={32} />
              <p className="text-gray-600 font-medium">Click to upload or drag and drop</p>
              <p className="text-sm text-gray-500 mt-1">PDF, Excel, CSV, Images (Max 50MB)</p>
            </div>
          </label>
        </div>

        {/* Files Table */}
        <div className="bg-white rounded-3xl shadow-xl overflow-hidden">
          {/* Search Bar */}
          <div className="p-6 border-b border-gray-200">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
              <input
                type="text"
                placeholder="Search files..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-12 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-all"
              />
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="px-6 py-4 text-left w-12">
                    <input 
                      type="checkbox" 
                      checked={selectAll}
                      onChange={toggleSelectAll}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Name</th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Size</th>
                </tr>
              </thead>
              <tbody>
                {filteredFiles.map((file) => (
                  <tr 
                    key={file.id}
                    className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-6 py-4">
                      <input 
                        type="checkbox" 
                        checked={file.selected}
                        onChange={() => toggleFile(file.id)}
                        className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                      />
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        {getFileIcon(file.type)}
                        <span className="text-sm font-medium text-gray-900">{file.name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm text-gray-600">{file.size}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {filteredFiles.length === 0 && (
              <div className="text-center py-12">
                <p className="text-gray-500">No files found</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
