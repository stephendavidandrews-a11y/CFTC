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

// -- Intake --
import SpeakerReviewListPage from "./pages/intake/SpeakerReviewListPage";
import SpeakerReviewDetailPage from "./pages/intake/SpeakerReviewDetailPage";

// -- Developer --
import DeveloperPage from "./pages/developer/DeveloperPage";
import NotFoundPage from "./pages/NotFoundPage";

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

          {/* -- Intake -- */}
          <Route path="/intake/speaker-review" element={<SpeakerReviewListPage />} />
          <Route path="/intake/speaker-review/:id" element={<SpeakerReviewDetailPage />} />

          {/* -- Developer -- */}
          <Route path="/developer" element={<DeveloperPage />} />

          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </ToastProvider>
  );
}
