import React from "react";
import { Routes, Route } from "react-router-dom";
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
import TeamWorkloadPage from "./pages/tracker/TeamWorkloadPage";
import DecisionsPage from "./pages/tracker/DecisionsPage";
import DocumentsPage from "./pages/tracker/DocumentsPage";

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

// -- Intelligence / Settings stubs --
const AIPlaceholder = ({ title }) => (
  <div style={{ padding: 40, color: "#94a3b8" }}>
    <h2>{title}</h2>
    <p>This page will be implemented in a later phase.</p>
  </div>
);

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route element={<AppShell />}>
          {/* -- Operations (Tracker) -- */}
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
          <Route path="/intelligence/digests" element={<AIPlaceholder title="Intelligence Digests" />} />
          <Route path="/intelligence/briefs" element={<AIPlaceholder title="Intelligence Briefs" />} />

          {/* -- AI Settings (Phase 8) -- */}
          <Route path="/settings/ai" element={<AISettingsPage />} />

          {/* -- Developer -- */}
          <Route path="/developer" element={<DeveloperPage />} />

          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </ToastProvider>
  );
}
