import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import RegisterModal from './RegisterModal';
import LoginModal from './LoginModal';
import ForgotPasswordModal from './ForgotPasswordModal';
import './Auth.css';

const UserMenu = () => {
    const { user, isAuthenticated, logout, loading } = useAuth();
    const [showRegister, setShowRegister] = useState(false);
    const [showLogin, setShowLogin] = useState(false);
    const [showForgotPassword, setShowForgotPassword] = useState(false);
    const [showDropdown, setShowDropdown] = useState(false);
    const dropdownRef = useRef(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setShowDropdown(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleLogout = async () => {
        await logout();
        setShowDropdown(false);
    };

    if (loading) {
        return null; // Don't show anything while checking auth status
    }

    return (
        <>
            <div className="user-menu-container" ref={dropdownRef}>
                {!isAuthenticated ? (
                    <div className="auth-links">
                        <span onClick={() => setShowRegister(true)}>Register</span>
                        <span onClick={() => setShowLogin(true)}>Login</span>
                    </div>
                ) : (
                    <div className="user-menu-trigger">
                        <div 
                            className="user-avatar"
                            onClick={() => setShowDropdown(!showDropdown)}
                        >
                            {user?.username?.charAt(0).toUpperCase() || 'U'}
                        </div>

                        {showDropdown && (
                            <div className="user-dropdown">
                                <div className="user-dropdown-header">
                                    <div className="user-dropdown-username">
                                        {user?.username || 'User'}
                                    </div>
                                    <div className="user-dropdown-email">
                                        {user?.email || ''}
                                    </div>
                                </div>

                                <ul className="user-dropdown-menu">
                                    <li className="user-dropdown-item">
                                        👤 Profile
                                    </li>
                                    <li className="user-dropdown-item">
                                        ⚙️ Settings
                                    </li>
                                    <li 
                                        className="user-dropdown-item logout"
                                        onClick={handleLogout}
                                    >
                                        🚪 Logout
                                    </li>
                                </ul>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Modals */}
            {showRegister && (
                <RegisterModal
                    onClose={() => setShowRegister(false)}
                    onSwitchToLogin={() => {
                        setShowRegister(false);
                        setShowLogin(true);
                    }}
                />
            )}

            {showLogin && (
                <LoginModal
                    onClose={() => setShowLogin(false)}
                    onSwitchToRegister={() => {
                        setShowLogin(false);
                        setShowRegister(true);
                    }}
                    onSwitchToForgotPassword={() => {
                        setShowLogin(false);
                        setShowForgotPassword(true);
                    }}
                />
            )}

            {showForgotPassword && (
                <ForgotPasswordModal
                    onClose={() => setShowForgotPassword(false)}
                    onSwitchToLogin={() => {
                        setShowForgotPassword(false);
                        setShowLogin(true);
                    }}
                />
            )}
        </>
    );
};

export default UserMenu;
