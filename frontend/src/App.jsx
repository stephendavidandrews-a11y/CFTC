import React from "react";
import { Routes, Route } from "react-router-dom";
import { ToastProvider } from "./contexts/ToastContext";
import AppShell from "./components/layout/AppShell";

// ── Tracker (Operations) ──
import TrackerDashboardPage from "./pages/tracker/TrackerDashboardPage";
import MattersPage from "./pages/tracker/MattersPage";
import MatterDetailPage from "./pages/tracker/MatterDetailPage";
import TrackerTasksPage from "./pages/tracker/TasksPage";
import PeoplePage from "./pages/tracker/PeoplePage";
import PersonDetailPage from "./pages/tracker/PersonDetailPage";
import OrganizationsPage from "./pages/tracker/OrganizationsPage";
import OrgDetailPage from "./pages/tracker/OrgDetailPage";
import MeetingsPage from "./pages/tracker/MeetingsPage";
import TeamWorkloadPage from "./pages/tracker/TeamWorkloadPage";
import DecisionsPage from "./pages/tracker/DecisionsPage";
import DocumentsPage from "./pages/tracker/DocumentsPage";

// ── Analysis (existing pages) ──
import SummaryPage from "./pages/SummaryPage";
import EOPage from "./pages/EOPage";
import IntelligencePage from "./pages/IntelligencePage";
import CommentsDashboard from "./pages/CommentsDashboard";
import CommentList from "./pages/CommentList";
import CommentDetail from "./pages/CommentDetail";
import Processing from "./pages/Processing";
import NewDocket from "./pages/NewDocket";
import InteragencyPage from "./pages/InteragencyPage";
import ResearchPage from "./pages/ResearchPage";
import ReportsPage from "./pages/ReportsPage";
import LoperDashboardPage from "./pages/loper/LoperDashboardPage";
import LoperExplorerPage from "./pages/loper/LoperExplorerPage";
import LoperRuleDetailPage from "./pages/loper/LoperRuleDetailPage";
import LoperGuidanceDetailPage from "./pages/loper/LoperGuidanceDetailPage";
import LoperAnalyticsPage from "./pages/loper/LoperAnalyticsPage";

// ── Legacy (kept for backward compat, redirects optional) ──
import TeamPage from "./pages/TeamPage";
import PipelinePage from "./pages/PipelinePage";
import RegActionsPage from "./pages/RegActionsPage";
import ItemDetailPage from "./pages/ItemDetailPage";
import WorkPage from "./pages/WorkPage";
import ProjectDetailPage from "./pages/ProjectDetailPage";
import TasksPage from "./pages/TasksPage";
import NotFoundPage from "./pages/NotFoundPage";

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route element={<AppShell />}>
          {/* ── Operations (Tracker) ── */}
          <Route index element={<TrackerDashboardPage />} />
          <Route path="/matters" element={<MattersPage />} />
          <Route path="/matters/:id" element={<MatterDetailPage />} />
          <Route path="/tasks" element={<TrackerTasksPage />} />
          <Route path="/people" element={<PeoplePage />} />
          <Route path="/people/:id" element={<PersonDetailPage />} />
          <Route path="/organizations" element={<OrganizationsPage />} />
          <Route path="/organizations/:id" element={<OrgDetailPage />} />
          <Route path="/meetings" element={<MeetingsPage />} />
          <Route path="/team-workload" element={<TeamWorkloadPage />} />
          <Route path="/decisions" element={<DecisionsPage />} />
          <Route path="/documents" element={<DocumentsPage />} />

          {/* ── Analysis ── */}
          <Route path="/summary" element={<SummaryPage />} />
          <Route path="/eo" element={<EOPage />} />
          <Route path="/intelligence" element={<IntelligencePage />} />
          <Route path="/comments" element={<CommentsDashboard />} />
          <Route path="/comments/browse" element={<CommentList />} />
          <Route path="/comments/detail/:documentId" element={<CommentDetail />} />
          <Route path="/comments/processing" element={<Processing />} />
          <Route path="/comments/new-docket" element={<NewDocket />} />
          <Route path="/interagency" element={<InteragencyPage />} />
          <Route path="/research" element={<ResearchPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/loper" element={<LoperDashboardPage />} />
          <Route path="/loper/rules" element={<LoperExplorerPage />} />
          <Route path="/loper/guidance" element={<LoperExplorerPage />} />
          <Route path="/loper/rules/:frCitation" element={<LoperRuleDetailPage />} />
          <Route path="/loper/guidance/:docId" element={<LoperGuidanceDetailPage />} />
          <Route path="/loper/analytics" element={<LoperAnalyticsPage />} />

          {/* ── Legacy routes (kept for bookmarks/links) ── */}
          <Route path="/team" element={<TeamPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/pipeline/:id" element={<ItemDetailPage />} />
          <Route path="/regulatory" element={<RegActionsPage />} />
          <Route path="/regulatory/:id" element={<ItemDetailPage />} />
          <Route path="/work" element={<WorkPage />} />
          <Route path="/work/tasks" element={<TasksPage />} />
          <Route path="/work/:id" element={<ProjectDetailPage />} />

          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </ToastProvider>
  );
}
