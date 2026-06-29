import React, { createContext, useState, useContext, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [loading, setLoading] = useState(true);
    const [credits, setCredits] = useState(null);
    const [entitlements, setEntitlements] = useState(null);

    const API_BASE_URL = 'http://localhost:8000';

    // Fetch the caller's credit balances + tier limits (header chip, monitor cap, etc.).
    const refreshCredits = async () => {
        try {
            const resp = await axios.get(`${API_BASE_URL}/api/me/entitlements`, {
                withCredentials: true
            });
            setCredits(resp.data.credits || null);
            setEntitlements(resp.data.entitlements || null);
        } catch (error) {
            setCredits(null);
            setEntitlements(null);
        }
    };

    // Check if user is logged in on mount
    useEffect(() => {
        checkAuth();
    }, []);

    // Capture a referral code from the URL (?ref=CODE) and remember it for signup.
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const ref = params.get('ref');
        if (ref) {
            localStorage.setItem('referral_code', ref.trim().toUpperCase());
            // Strip ?ref= from the URL (keep the path) so it doesn't linger.
            params.delete('ref');
            const qs = params.toString();
            const newUrl = window.location.pathname + (qs ? `?${qs}` : '') + window.location.hash;
            window.history.replaceState({}, '', newUrl);
        }
    }, []);

    const checkAuth = async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/api/auth/me`, {
                withCredentials: true
            });
            
            if (response.data.success && response.data.user) {
                setUser(response.data.user);
                setIsAuthenticated(true);
                refreshCredits();
            }
        } catch (error) {
            // Not authenticated or session expired
            setUser(null);
            setIsAuthenticated(false);
            setCredits(null);
            setEntitlements(null);
        } finally {
            setLoading(false);
        }
    };

    const register = async (email, username, password, passwordConfirm) => {
        try {
            const referralCode = localStorage.getItem('referral_code') || undefined;
            const response = await axios.post(
                `${API_BASE_URL}/api/auth/register`,
                {
                    email,
                    username,
                    password,
                    password_confirm: passwordConfirm,
                    referral_code: referralCode
                }
            );

            // The pending referral is recorded at registration; clear the stored code.
            localStorage.removeItem('referral_code');

            return { success: true, data: response.data };
        } catch (error) {
            return {
                success: false,
                error: error.response?.data?.detail || 'Registration failed'
            };
        }
    };

    const login = async (email, password) => {
        try {
            const response = await axios.post(
                `${API_BASE_URL}/api/auth/login`,
                { email, password },
                { withCredentials: true }
            );
            
            if (response.data.success && response.data.user) {
                setUser(response.data.user);
                setIsAuthenticated(true);
                refreshCredits();
                return { success: true, data: response.data };
            }

            return { success: false, error: 'Login failed' };
        } catch (error) {
            return {
                success: false,
                error: error.response?.data?.detail || 'Login failed'
            };
        }
    };

    const logout = async () => {
        try {
            await axios.post(
                `${API_BASE_URL}/api/auth/logout`,
                {},
                { withCredentials: true }
            );
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            setUser(null);
            setIsAuthenticated(false);
            setCredits(null);
            setEntitlements(null);
        }
    };

    const forgotPassword = async (email) => {
        try {
            const response = await axios.post(
                `${API_BASE_URL}/api/auth/forgot-password`,
                { email }
            );
            
            return { success: true, data: response.data };
        } catch (error) {
            return {
                success: false,
                error: error.response?.data?.detail || 'Failed to send reset email'
            };
        }
    };

    const resetPassword = async (token, newPassword, newPasswordConfirm) => {
        try {
            const response = await axios.post(
                `${API_BASE_URL}/api/auth/reset-password`,
                {
                    token,
                    new_password: newPassword,
                    new_password_confirm: newPasswordConfirm
                },
                { withCredentials: true }  // ✅ Allow cookies for auto-login
            );
            
            return { success: true, data: response.data };
        } catch (error) {
            return {
                success: false,
                error: error.response?.data?.detail || 'Password reset failed'
            };
        }
    };

    const verifyEmail = async (token) => {
        try {
            const response = await axios.get(
                `${API_BASE_URL}/api/auth/verify-email?token=${token}`,
                { withCredentials: true }  // ✅ FIX: Allow cookies from backend
            );
            
            return { success: true, data: response.data };
        } catch (error) {
            return {
                success: false,
                error: error.response?.data?.detail || 'Email verification failed'
            };
        }
    };

    const resendVerification = async (email) => {
        try {
            const response = await axios.post(
                `${API_BASE_URL}/api/auth/resend-verification`,
                { email }
            );
            
            return { success: true, data: response.data };
        } catch (error) {
            return {
                success: false,
                error: error.response?.data?.detail || 'Failed to resend verification email'
            };
        }
    };

    const value = {
        user,
        isAuthenticated,
        loading,
        credits,
        entitlements,
        refreshCredits,
        register,
        login,
        logout,
        forgotPassword,
        resetPassword,
        verifyEmail,
        resendVerification,
        checkAuth
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};
