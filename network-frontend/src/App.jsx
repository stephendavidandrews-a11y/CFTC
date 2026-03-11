import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './components/Dashboard';
import ContactList from './components/ContactList';
import ContactDetail from './components/ContactDetail';
import ContactForm from './components/ContactForm';
import OpenLoops from './components/OpenLoops';
import VenueList from './components/VenueList';
import VenueForm from './components/VenueForm';
import HappyHourList from './components/HappyHourList';
import HappyHourDetail from './components/HappyHourDetail';
import HappyHourForm from './components/HappyHourForm';
import IntroList from './components/IntroList';
import IntroForm from './components/IntroForm';
import ProfessionalPulse from './components/ProfessionalPulse';
import LinkedInEvents from './components/LinkedInEvents';
import ApprovalQueue from './components/ApprovalQueue';

export default function App() {
  return (
    <Routes>
      {/* Mobile-first approval queue — full-screen, no sidebar */}
      <Route path="/queue" element={<ApprovalQueue />} />

      {/* Main app with sidebar layout */}
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/contacts" element={<ContactList />} />
        <Route path="/contacts/new" element={<ContactForm />} />
        <Route path="/contacts/:id" element={<ContactDetail />} />
        <Route path="/contacts/:id/edit" element={<ContactForm />} />
        <Route path="/professional" element={<ProfessionalPulse />} />
        <Route path="/open-loops" element={<OpenLoops />} />
        <Route path="/linkedin" element={<LinkedInEvents />} />
        <Route path="/venues" element={<VenueList />} />
        <Route path="/venues/new" element={<VenueForm />} />
        <Route path="/venues/:id/edit" element={<VenueForm />} />
        <Route path="/happy-hours" element={<HappyHourList />} />
        <Route path="/happy-hours/new" element={<HappyHourForm />} />
        <Route path="/happy-hours/:id" element={<HappyHourDetail />} />
        <Route path="/happy-hours/:id/edit" element={<HappyHourForm />} />
        <Route path="/intros" element={<IntroList />} />
        <Route path="/intros/new" element={<IntroForm />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
