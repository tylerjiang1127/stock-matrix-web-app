import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import './Sidebar.css';

const navItems = [
    { path: '/', icon: '📊', label: 'Dashboard' },
    { path: '/intelligence', icon: '🧠', label: 'AI Macro Daily Report' },
    { path: '/screener', icon: '🔍', label: 'AI Stock Screener' },
];

function Sidebar() {
    const location = useLocation();

    return (
        <nav className="sidebar">
            <div className="sidebar-logo">SM</div>
            <div className="sidebar-nav">
                {navItems.map(item => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) =>
                            `sidebar-item ${isActive ? 'active' : ''}`
                        }
                        end={item.path === '/'}
                    >
                        <span className="sidebar-item-icon">{item.icon}</span>
                        <span className="sidebar-item-label">{item.label}</span>
                    </NavLink>
                ))}
            </div>
            <div className="sidebar-spacer" />
        </nav>
    );
}

export default Sidebar;
