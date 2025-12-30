import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Header from './component/Header';
import LayoutShell from './component/LayoutShell';
import OutlineCreation from './pages/OutlineCreation';
import SourceSelection from './pages/SourceSelection';
import FinalView from './pages/FinalView';
import AISearchPage from './pages/AISearchPage';
import DataAgentsPage from './pages/DataAgents';
import ExtractionResultsPage from './pages/ExtractionResults';
import SourcesData from './pages/SourcesData';
import KnowledgeBasePage from './pages/KnowledgeBase';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            <div className="min-h-screen bg-gradient-to-br from-[#E8F4FF] via-white to-[#E0F2FF] text-[#0F172A]">
              <Header />
              <LayoutShell />
            </div>
          }
        />
        <Route path="/ai-search" element={<AISearchPage />} />
        <Route path="/outline" element={<OutlineCreation />} />
        <Route path="/sources" element={<SourceSelection />} />
        <Route path="/final" element={<FinalView />} />
        <Route path="/sources-data" element={<SourcesData />} />
        <Route path="/data-agents" element={<DataAgentsPage />} />
        <Route path="/extraction-results" element={<ExtractionResultsPage />} />
        <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
