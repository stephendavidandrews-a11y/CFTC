import ErrorBoundary from "./components/shared/ErrorBoundary";
import React from "react";
import { Routes, Route, useLocation } from "react-router-dom";
import { ToastProvider } from "./contexts/ToastContext";
import AppShell from "./components/layout/AppShell";

// -- Tracker (Operations) --
import TrackerDashboardPage from "./pages/tracker/TrackerDashboardPage";
import MattersPage from "./pages/tracker/MattersPage";
import MatterDetailPage from "./pages/tracker/MatterDetailPage";
import TrackerTasksPage from "./pages/tracker/TasksPage";
import PeoplePage from "./pages/tracker/PeoplePage";
import PersonDetailPage from "./pages/tracker/PersonDetailPage";
import OrganizationsPage from "./pages/tracker/OrganizationsPage";
import OrgDetailPage from "./pages/tracker/OrgDetailPage";
import MeetingsPage from "./pages/tracker/MeetingsPage";
import MeetingDetailPage from "./pages/tracker/MeetingDetailPage";
import TeamWorkloadPage from "./pages/tracker/TeamWorkloadPage";
import DecisionsPage from "./pages/tracker/DecisionsPage";
import DocumentsPage from "./pages/tracker/DocumentsPage";
import ContextNotesPage from "./pages/tracker/ContextNotesPage";

// -- AI Review (Phase 3 + Phase 6) --
import SpeakerReviewQueuePage from "./pages/review/SpeakerReviewQueuePage";
import SpeakerReviewDetailPage from "./pages/review/SpeakerReviewDetailPage";
import EntityReviewQueuePage from "./pages/review/EntityReviewQueuePage";
import EntityReviewDetailPage from "./pages/review/EntityReviewDetailPage";
import BundleReviewQueuePage from "./pages/review/BundleReviewQueuePage";
import BundleReviewDetailPage from "./pages/review/BundleReviewDetailPage";
import CommitQueuePage from "./pages/review/CommitQueuePage";
import CommunicationsArchivePage from "./pages/review/CommunicationsArchivePage";

// -- Developer --
import DeveloperPage from "./pages/developer/DeveloperPage";
import NotFoundPage from "./pages/NotFoundPage";

// -- Settings (Phase 8) --
import AISettingsPage from "./pages/settings/AISettingsPage";

// -- Intelligence --
import DailyBriefPage from "./pages/intelligence/DailyBriefPage";
import WeeklyBriefPage from "./pages/intelligence/WeeklyBriefPage";
import DirectivesPage from "./pages/tracker/DirectivesPage";
import DirectiveDetailPage from "./pages/tracker/DirectiveDetailPage";

// -- Intelligence / Settings stubs --
const AIPlaceholder = ({ title }) => (
  <div style={{ padding: 40, color: "#94a3b8" }}>
    <h2>{title}</h2>
    <p>This page will be implemented in a later phase.</p>
  </div>
);

export default function App() {
  return (
    <ErrorBoundary>
    <ToastProvider>
      <Routes>
        <Route element={<AppShell />}>
          {/* -- Operations (Tracker) -- */}
          <Route index element={<TrackerDashboardPage />} />
          <Route path="/matters" element={<MattersPage />} />
          <Route path="/matters/:id" element={<MatterDetailPage />} />
            <Route path="/directives" element={<DirectivesPage />} />
            <Route path="/directives/:id" element={<DirectiveDetailPage />} />
          <Route path="/tasks" element={<TrackerTasksPage />} />
          <Route path="/people" element={<PeoplePage />} />
          <Route path="/people/:id" element={<PersonDetailPage />} />
          <Route path="/organizations" element={<OrganizationsPage />} />
          <Route path="/organizations/:id" element={<OrgDetailPage />} />
          <Route path="/meetings" element={<MeetingsPage />} />
          <Route path="/meetings/:id" element={<MeetingDetailPage />} />
          <Route path="/team-workload" element={<TeamWorkloadPage />} />
          <Route path="/decisions" element={<DecisionsPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/context-notes" element={<ContextNotesPage />} />

          {/* -- AI Review (Phase 3 + Phase 6) -- */}
          <Route path="/review/speakers" element={<SpeakerReviewQueuePage />} />
          <Route path="/review/speakers/:id" element={<SpeakerReviewDetailPage />} />
          <Route path="/review/entities" element={<EntityReviewQueuePage />} />
          <Route path="/review/entities/:id" element={<EntityReviewDetailPage />} />
          <Route path="/review/bundles" element={<BundleReviewQueuePage />} />
          <Route path="/review/bundles/:id" element={<BundleReviewDetailPage />} />
          <Route path="/review/commit" element={<CommitQueuePage />} />
          <Route path="/review/communications" element={<CommunicationsArchivePage />} />

          {/* -- Intelligence (Phase 9+ — stubs) -- */}
          <Route path="/intelligence/daily" element={<DailyBriefPage />} />
          <Route path="/intelligence/weekly" element={<WeeklyBriefPage />} />
          <Route path="/intelligence/briefs" element={<DailyBriefPage />} />

          {/* -- AI Settings (Phase 8) -- */}
          <Route path="/settings/ai" element={<AISettingsPage />} />

          {/* -- Developer -- */}
          <Route path="/developer" element={<DeveloperPage />} />

          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </ToastProvider>
    </ErrorBoundary>
  );
}
