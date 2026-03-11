import React from 'react';
import { NavLink } from 'react-router-dom';

const navItems = [
  { to: '/', icon: '\u2302', label: 'Dashboard' },
  { to: '/contacts', icon: '\u{1F465}', label: 'Contacts' },
  { to: '/professional', icon: '\u{1F4BC}', label: 'Professional' },
  { to: '/linkedin', icon: '\u{1F517}', label: 'LinkedIn' },
  { to: '/venues', icon: '\u{1F4CD}', label: 'Venues' },
  { to: '/happy-hours', icon: '\u{1F37B}', label: 'Happy Hours' },
];

export default function Sidebar({ isOpen, onClose }) {
  return (
    <>
      <div
        className={`sidebar-overlay${isOpen ? ' open' : ''}`}
        onClick={onClose}
      />
      <aside className={`sidebar${isOpen ? ' open' : ''}`}>
        <div className="sidebar-header">
          <span className="logo">{'\u{1F310}'}</span>
          <h1>Network</h1>
        </div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => isActive ? 'active' : ''}
              onClick={onClose}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          Network v2.0 — Phase 2
        </div>
      </aside>
    </>
  );
}
