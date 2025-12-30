# 项目概览

本项目为 **TTsending AI储能白皮书生成平台原型**，基于 React 18 + TypeScript + Vite + Tailwind CSS 构建。界面采用科技感蓝色渐变风格，强调知识库联动与白皮书生成工作流。

## 关键命令
- 安装依赖：`npm install`
- 产线构建：`npm run build`

## 代码结构
- `src/App.tsx`：应用入口，加载头部与双栏布局。
- `src/components/Header.tsx`：顶部渐变头部，包含 TTsending Logo、导航交互。
- `src/components/LayoutShell.tsx`：整体容器，控制左侧栏 + 右侧主内容布局。
- `src/components/Sidebar.tsx`：左侧面板，含高亮“新建白皮书”入口、历史记录、AI 问答检索、知识库、数据抽取 Agent、源数据汇总折叠卡片。
- `src/components/Editor.tsx`：右侧生成流程表单，内含步骤指示（当前停留在 Step 1）、报告配置、知识库选择、引用数量与草稿上传。
- `src/assets/ttsending-logo.jpg`：TTsending 品牌 Logo。
- 样式基于 Tailwind CSS，字体使用 Source Sans 3 (`src/index.css`)。

## 主要功能特性
1. **渐变头部与双栏布局**：左侧约 30%，右侧 70%，保持响应式布局（移动端堆叠显示）。
2. **侧栏模块**：
   - 储能历史记录列表（带 hover、高亮状态）。
   - 知识库状态卡片，展示可用资源数。
   - 数据抽取 Agent 运行状态指示。
   - 源数据汇总可折叠预览上传的数据文件。
3. **生成流程表单**：
   - 顶部 5 步进度指示器（Start → Get Draft）。
   - 报告类型、引用格式、篇幅、引用数量调节按钮。
   - **核心**：知识库启用开关 + 多选复选框 + 已选徽标。
   - 草稿上传开关及拖拽上传占位。
4. **交互细节**：蓝-青渐变强调色、圆角卡片、阴影与悬浮反馈、滑动切换动画。

## 设计与样式约定
- 主色：渐变 `#4A90E2 → #1E5799`，强调色使用 cyan (`#00D9FF` 对应 Tailwind `cyan-400`).
- 卡片统一 8px~16px 圆角，使用半透明白背景与蓝色阴影。
- Tailwind utility 辅以自定义渐变、阴影与 backdrop-blur。

## 注意事项
- 静态资源引用需使用 `/src/assets` 导入方式（Vite 将处理打包路径）。
- 所有中文 UI 文案已根据需求定制，保持中文输出。
- 构建完成后会生成 `dist/` 目录，包含打包后的静态资源。
