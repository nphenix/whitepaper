# TTsending AI 储能白皮书生成平台

## 项目概览
本项目为 **TTsending AI储能白皮书生成平台原型**，基于 React 18 + TypeScript + Vite + Tailwind CSS 构建。界面采用科技感蓝色渐变风格，强调知识库联动与白皮书生成工作流。

## 技术栈
- **Frontend Framework**: React 18.3.1
- **Build Tool**: Vite 7.0.0
- **Language**: TypeScript 5.8.3
- **Styling**: Tailwind CSS 3.4.17
- **Icons**: Lucide React
- **Animation**: Framer Motion, GSAP
- **State Management**: Zustand
- **Internationalization**: i18next

## 项目结构
```
.
├── src/
│   ├── assets/          # 静态资源（Logo等）
│   ├── component/       # React组件
│   │   ├── Header.tsx   # 头部导航
│   │   ├── LayoutShell.tsx  # 整体布局容器
│   │   ├── Siderbar.tsx     # 左侧边栏
│   │   ├── Editor.tsx       # 右侧编辑器
│   │   └── AIChat.tsx       # AI聊天组件
│   ├── App.tsx          # 应用入口
│   ├── main.tsx         # React渲染入口
│   ├── App.css          # 应用样式
│   └── index.css        # 全局样式
├── index.html           # HTML模板
├── vite.config.ts       # Vite配置
├── tsconfig.json        # TypeScript配置
├── tailwind.config.js   # Tailwind配置
└── package.json         # 项目依赖

```

## 开发环境设置

### 本地开发
```bash
npm install           # 安装依赖
npm run dev          # 启动开发服务器 (http://localhost:5000)
npm run build        # 构建生产版本
npm run preview      # 预览生产构建
```

### Replit环境
- **开发服务器**: 已配置在端口 5000 上运行
- **工作流**: `vite-dev-server` 自动启动开发服务器
- **部署**: 配置为 autoscale 部署类型

## 配置要点

### Vite配置 (vite.config.ts)
- 开发服务器绑定到 `0.0.0.0:5000`
- HMR配置适配Replit环境
- 支持React插件和快速刷新

### TypeScript配置
- 严格模式启用
- JSX转换为React 18新格式
- 模块解析使用bundler模式

## 主要功能
1. **Header组件**: 
   - 平台标题: "TTsending AI White Paper" (可点击，导航到主页)
   - Logo、通知、帮助和用户信息
   - 应用于主页和AI检索页
2. **渐变头部与双栏布局**: 左侧约30%，右侧70%，响应式设计
3. **侧栏模块**:
   - "新建白皮书" 按钮 (导航到主页)
   - 白皮书历史记录
   - 知识库状态卡片
   - 数据抽取Agent运行状态
   - 源数据汇总可折叠预览
4. **生成流程表单**:
   - 5步进度指示器
   - 报告类型和引用格式选择
   - 知识库启用开关和多选
   - 草稿上传功能

## 设计规范
- **主色**: 渐变 `#4A90E2 → #1E5799`
- **强调色**: Cyan (`#00D9FF`)
- **卡片**: 8px~16px圆角，半透明白背景
- **字体**: Source Sans 3

## 注意事项
- 静态资源使用ES模块导入方式
- 所有UI文案为中文
- 构建输出到 `dist/` 目录

## Backend & API
- **Backend Server**: Express.js on port 3001
- **API Endpoints**:
  - POST /api/outline - Save white paper outline
  - GET /api/sources/:outlineId - Fetch recommended sources
  - POST /api/sources/:outlineId - Save selected sources
  - POST /api/upload - File upload (PDF, DOCX, PPTX, max 50MB)
  - POST /api/generate-draft/:outlineId - Generate draft content
  - GET /api/draft/:outlineId - Retrieve generated draft
  - POST /api/chat - AI chat functionality
  - GET /api/history - Get outline history
- **Proxy**: Vite dev server proxies /api requests to backend

## User Flow Pages
### Sources Data Page (/sources-data)
- Dedicated page for managing uploaded source files
- "Upload everything at once" section with drag-and-drop interface
- Real-time upload progress indicator
- Search functionality for filtering files
- File table with checkboxes for selection
- Displays file icons, names, and sizes
- Supports PDF, Excel, CSV, Images (Max 50MB)
- Accessible from Main Page sidebar by clicking "源数据汇总"

### Phase 1: Outline Creation (/outline)
- Textarea for inputting white paper guidelines and structure
- Character count indicator
- Continue button to proceed to source selection

### Phase 2: Source Selection (/sources)
- Displays AI-recommended academic sources
- Checkbox selection for sources
- File upload for custom sources (PDF, DOCX, PPTX)
- URL input for web articles and YouTube
- "Generate draft" button to proceed

### Phase 3: Final View (/final)
- **Header with Process Indicator**: Shows 4-step clickable workflow progress (1开始, 2添加指南, 3选择来源, 4获取草稿)
- **Platform Title**: "TTsending AI 白皮书平台"
- **Mock Data**: Displays demo white paper content when accessed without ID parameter
  - Title: "未来五年储能产业政策与发展趋势白皮书"
  - Complete white paper content with 6 sections
  - 3 demo sources with metadata
- **Three-panel layout**:
  - Left sidebar: List of selected sources with metadata
  - Center panel: Generated white paper content with rich text editor
  - Right sidebar: AI chat assistant with Search/Assistant modes
- Real-time chat functionality for Q&A about content
- AI polish and summary generation buttons

## Configuration
- **API Base URL**: Configurable via src/config/api.ts
- **URL Params**: State persistence using query parameters (e.g., /sources?id=123)
- **Environment-aware**: Uses proxy in development, relative URLs in production

## Recent Changes

### November 11, 2025 - New Source Data Management Page
**Created Dedicated Sources Data Page:**
- 📁 New route `/sources-data` for managing all uploaded source files
- 📤 Julius-style upload interface with "Upload everything at once" heading
- 📊 File table displaying uploaded documents with icons, names, and sizes
- 🔍 Search functionality to filter through uploaded files
- ✅ Checkbox selection for bulk operations
- 📈 Real-time upload progress indicator
- 🎨 Consistent header design matching other pages
- 🔗 Navigation: Click "源数据汇总" in Main Page sidebar to access
- 🗂️ Mock data includes 7 sample files (PDF, Excel, CSV, Images)

**Technical Implementation:**
- Created `SourcesDataPage.tsx` component with full upload and file management UI
- Updated routing in `App.tsx` to include `/sources-data` route
- Modified sidebar to make "源数据汇总" a clickable navigation button
- Removed collapsible file preview from sidebar (now shows on dedicated page)
- File type icons dynamically rendered based on file extension

### November 11, 2025 - Unified Header Across All Pages
**Consistent Header Design:**
- 🎯 Standardized header across Main Page, AI Search Page, and Page 4 (FinalView)
- 🏷️ Clickable "TTsending AI White Paper" logo + title that navigates to main page (/)
- 👤 Right-side icons: Notification, Help, User profile (能源研究院)
- 📊 Page 4 includes 4-step clickable process indicator below main header:
  - Step 1 (开始) → Clickable, navigates to main page (/)
  - Step 2 (添加指南) → Clickable, navigates to outline page (/outline)
  - Step 3 (选择来源) → Clickable, navigates to sources page (/sources)
  - Step 4 (获取草稿) → Current page, non-clickable, visually distinct
- ✨ Interactive hover effects on clickable elements (opacity transitions)
- 🎨 Clean two-row layout on Page 4: main header + process indicator

**Technical Implementation:**
- Steps 1-3 implemented as button elements with onClick navigation
- Step 4 styled with `cursor-default` and `aria-current="page"` for accessibility
- Group hover effects for better UX feedback
- Responsive flexbox layout with max-width constraint
- Title uses `whitespace-nowrap` to prevent wrapping

### November 11, 2025 - Main Page Sidebar Simplification & Dedicated AI Search Page
**Sidebar Reorganization:**
- 📋 Simplified sidebar to show only ONE history record example: "未来五年储能产业政策与发展趋势白皮书"
- 🗂️ Reorganized all sections into clean, collapsible accordions:
  - 白皮书历史记录 (White Paper History) - Single example record that navigates to /final
  - 知识库 (Knowledge Base) - Status indicator showing "3个可用"
  - 数据抽取Agent (Data Extraction Agent) - Live running status with green dot
  - 源数据汇总 (Source Data) - Collapsible list of source files
- 🔍 Added "AI 智能检索" button for navigating to dedicated AI Search page
- ❌ Removed AI Q&A search section from sidebar (relocated to dedicated page)

**New AI Search Page (/ai-search):**
- ✨ Created dedicated route and component for AI Q&A functionality
- 🎨 Hero-style centered layout with large gradient Search icon
- 📑 Three source mode tabs: 知识库 (Knowledge Base), 历史记录 (History), 网络实时 (Web)
- 🔍 Large search input with placeholder and "检索" button
- 💡 Recommended questions section with gradient hover effects
- 🧭 Uses same Header component for consistent navigation

**Technical Implementation:**
- State management: `sections` object with boolean flags for each collapsible section
- Navigation: `useNavigate` hook for programmatic routing
- Component structure: AISearchPage as standalone page outside LayoutShell
- Routing: Updated App.tsx with new /ai-search route

### November 11, 2025 - Notion AI-Style Assistant Transformation
**Right Sidebar AI Assistant Redesign:**
- 🎨 Transformed AI assistant to Notion AI-style interface
  - Clean greeting screen: "今天需要什么帮助？" with large gradient AI avatar
  - Removed tab-based navigation in favor of cleaner mode-based approach
  - Two distinct modes: "Search" and "Assistant"
  
**Mode Switcher (Replit-style):**
- Dropdown mode selector integrated into input area
- Search mode: Access to history records, knowledge base, and online search
- Assistant mode: Q&A, consulting, translation, and polishing functions
- Dynamic placeholder text changes based on selected mode
- Click-outside handler for proper dropdown dismissal

**Quick Action Buttons:**
- Mode-aware quick actions displayed when chat is empty
- Search mode actions: Search History, Browse Knowledge Base, Web Search
- Assistant mode actions: Ask Question, Translation, Polish Text, Analysis Insights
- Clean card-based layout with gradient hover effects

**Technical Implementation:**
- State management: Replaced `activeTab` with `assistantMode: 'search' | 'assistant'`
- Config-driven quick actions with `quickActionsConfig` object
- Mode parameter sent to backend API for context-aware responses
- Outside-click handling for dropdown UX

### November 11, 2025 - AI Analysis & Modern UI Refinements
**Page 4 (FinalView) Enhancements:**
- ✨ Added AI White Paper Analysis button at top of draft area
  - Gradient icon background (blue-purple) with Bot icon
  - "开始分析" button with loading states and Sparkles icon
  - Backend API endpoint: POST /api/analyze-whitepaper (OpenAI GPT-4)
  - Analysis results displayed in AI chat sidebar

**Modern AI-Style UI Updates:**
- 🎨 Updated color scheme throughout Page 4 to match main page
- Left sidebar: Gradient icons (blue-cyan), modernized tabs
- Right sidebar: Gradient Bot icon (purple-blue), color-coded tabs
- Chat messages: Gradient backgrounds (blue-purple for user, slate for AI)
- Send button: Gradient styling with hover effects
- Suggestion buttons: Gradient hover transitions
- Main draft area: Gradient background with rounded card styling

**Technical Improvements:**
- Tiptap rich text editor with Word-style rendering
- Notion-style slash commands (/, headings, tables, quotes)
- Text selection popup with AI functions (polish, grammar, translate)
- All imports cleaned up, no LSP errors
- Consistent gradient design patterns across all UI elements

### October 30, 2025 - Initial Setup
- 项目从GitHub导入到Replit环境
- 创建缺失的配置文件 (vite.config.ts, tsconfig.json)
- 修复项目结构和导入路径
- 配置开发工作流和部署设置
- 应用成功运行在端口5000

### Backend & Multi-Page Flow Implementation
- 添加Express后端服务器 (端口3001)
- 实现完整的API端点用于大纲、源选择、草稿生成和聊天
- 创建三个页面组件：大纲创建、源选择、最终视图
- 集成React Router进行页面导航
- 添加Vite代理配置用于API请求
- 使用URL参数实现状态持久化
- 配置环境感知API基础URL
