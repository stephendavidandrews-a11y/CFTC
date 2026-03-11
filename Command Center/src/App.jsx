import React from "react";
import { Routes, Route } from "react-router-dom";
import { ToastProvider } from "./contexts/ToastContext";
import AppShell from "./components/layout/AppShell";
import SummaryPage from "./pages/SummaryPage";
import EOPage from "./pages/EOPage";
import TeamPage from "./pages/TeamPage";
import PipelinePage from "./pages/PipelinePage";
import RegActionsPage from "./pages/RegActionsPage";
import ItemDetailPage from "./pages/ItemDetailPage";
import IntelligencePage from "./pages/IntelligencePage";
import CommentsDashboard from "./pages/CommentsDashboard";
import CommentList from "./pages/CommentList";
import CommentDetail from "./pages/CommentDetail";
import Processing from "./pages/Processing";
import NewDocket from "./pages/NewDocket";
import InteragencyPage from "./pages/InteragencyPage";
import ResearchPage from "./pages/ResearchPage";
import ReportsPage from "./pages/ReportsPage";
import WorkPage from "./pages/WorkPage";
import ProjectDetailPage from "./pages/ProjectDetailPage";
import TasksPage from "./pages/TasksPage";
import NotFoundPage from "./pages/NotFoundPage";
import LoperDashboardPage from "./pages/loper/LoperDashboardPage";
import LoperExplorerPage from "./pages/loper/LoperExplorerPage";
import LoperRuleDetailPage from "./pages/loper/LoperRuleDetailPage";
import LoperGuidanceDetailPage from "./pages/loper/LoperGuidanceDetailPage";
import LoperAnalyticsPage from "./pages/loper/LoperAnalyticsPage";

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<SummaryPage />} />
          <Route path="/eo" element={<EOPage />} />
          <Route path="/team" element={<TeamPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/pipeline/:id" element={<ItemDetailPage />} />
          <Route path="/regulatory" element={<RegActionsPage />} />
          <Route path="/regulatory/:id" element={<ItemDetailPage />} />
          <Route path="/intelligence" element={<IntelligencePage />} />
          <Route path="/comments" element={<CommentsDashboard />} />
          <Route path="/comments/browse" element={<CommentList />} />
          <Route path="/comments/detail/:documentId" element={<CommentDetail />} />
          <Route path="/comments/processing" element={<Processing />} />
          <Route path="/comments/new-docket" element={<NewDocket />} />
          <Route path="/interagency" element={<InteragencyPage />} />
          <Route path="/research" element={<ResearchPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/work" element={<WorkPage />} />
          <Route path="/work/tasks" element={<TasksPage />} />
          <Route path="/work/:id" element={<ProjectDetailPage />} />
          <Route path="/loper" element={<LoperDashboardPage />} />
          <Route path="/loper/rules" element={<LoperExplorerPage />} />
          <Route path="/loper/guidance" element={<LoperExplorerPage />} />
          <Route path="/loper/rules/:frCitation" element={<LoperRuleDetailPage />} />
          <Route path="/loper/guidance/:docId" element={<LoperGuidanceDetailPage />} />
          <Route path="/loper/analytics" element={<LoperAnalyticsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </ToastProvider>
  );
}
