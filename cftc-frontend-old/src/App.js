import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import CommentList from './pages/CommentList';
import CommentDetail from './pages/CommentDetail';
import Processing from './pages/Processing';
import NewDocket from './pages/NewDocket';

function NavLink({ to, children }) {
  const location = useLocation();
  const active = location.pathname === to || (to !== '/' && location.pathname.startsWith(to));
  return (
    <Link
      to={to}
      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
        active
          ? 'bg-white text-cftc-600 shadow-sm'
          : 'text-blue-100 hover:bg-blue-700 hover:text-white'
      }`}
    >
      {children}
    </Link>
  );
}

function Layout({ children }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-cftc-800 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-2">
              <div className="text-white font-bold text-lg tracking-tight">
                CFTC Comment Analyzer
              </div>
              <span className="text-blue-300 text-xs bg-blue-900 px-2 py-0.5 rounded-full">
                BETA
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <NavLink to="/">Dashboard</NavLink>
              <NavLink to="/new-docket">New Docket</NavLink>
              <NavLink to="/processing">AI Processing</NavLink>
            </div>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
          <Route path="/comments" element={<CommentList />} />
          <Route path="/comments/:documentId" element={<CommentDetail />} />
          <Route path="/new-docket" element={<NewDocket />} />
          <Route path="/processing" element={<Processing />} />
        </Routes>
      </Layout>
    </Router>
  );
}
