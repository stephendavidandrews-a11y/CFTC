import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import CommentDashboard from './pages/CommentDashboard';
import CommentList from './pages/CommentList';
import CommentDetail from './pages/CommentDetail';
import Processing from './pages/Processing';
import NewDocket from './pages/NewDocket';
import PipelinePage from './pages/PipelinePage';
import PipelineItemPage from './pages/PipelineItemPage';

function NavLink({ to, children }) {
  const location = useLocation();
  const active = location.pathname === to || (to !== '/' && location.pathname.startsWith(to));
  return (
    <Link
      to={to}
      style={{
        padding: '6px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
        textDecoration: 'none', transition: 'all 0.15s',
        background: active ? 'rgba(255,255,255,0.12)' : 'transparent',
        color: active ? '#f1f5f9' : '#94a3b8',
      }}
      onMouseEnter={e => { if (!active) { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = '#e2e8f0'; } }}
      onMouseLeave={e => { if (!active) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#94a3b8'; } }}
    >
      {children}
    </Link>
  );
}

function Layout({ children }) {
  return (
    <div style={{ minHeight: '100vh', background: '#0a0f1a' }}>
      <nav style={{ background: '#070b14', borderBottom: '1px solid #1f2937' }}>
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 56 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ color: '#f1f5f9', fontWeight: 700, fontSize: 16, letterSpacing: '-0.01em' }}>
                CFTC Regulatory Platform
              </div>
              <span style={{
                color: '#60a5fa', fontSize: 10, background: '#172554',
                padding: '2px 8px', borderRadius: 10, fontWeight: 600,
              }}>
                BETA
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <NavLink to="/">Dashboard</NavLink>
              <NavLink to="/pipeline">Pipeline</NavLink>
              <NavLink to="/analysis">Comments</NavLink>
              <NavLink to="/new-docket">New Docket</NavLink>
              <NavLink to="/processing">AI Processing</NavLink>
            </div>
          </div>
        </div>
      </nav>
      <main style={{ maxWidth: 1280, margin: '0 auto', padding: '32px 24px' }}>
        {children}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/pipeline/:id" element={<PipelineItemPage />} />
          <Route path="/analysis" element={<CommentDashboard />} />
          <Route path="/comments" element={<CommentList />} />
          <Route path="/comments/:documentId" element={<CommentDetail />} />
          <Route path="/new-docket" element={<NewDocket />} />
          <Route path="/processing" element={<Processing />} />
        </Routes>
      </Layout>
    </Router>
  );
}
