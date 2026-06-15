import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import './Auth.css';

const ResetPasswordPage = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { resetPassword, checkAuth } = useAuth();
    const [formData, setFormData] = useState({
        newPassword: '',
        newPasswordConfirm: ''
    });
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [loading, setLoading] = useState(false);
    const [countdown, setCountdown] = useState(3); // Countdown timer
    const [showPassword, setShowPassword] = useState(false);
    const [showPasswordConfirm, setShowPasswordConfirm] = useState(false);

    const token = searchParams.get('token');

    const handleChange = (e) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value
        });
        setError('');
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        
        if (!token) {
            setError('Invalid reset link');
            return;
        }

        // Client-side validation
        const password = formData.newPassword;
        const confirmPassword = formData.newPasswordConfirm;

        // Check if passwords match
        if (password !== confirmPassword) {
            setError('The two passwords you entered do not match. Please check and try again.');
            console.error('Password mismatch:', {
                password_length: password.length,
                confirm_length: confirmPassword.length,
                are_equal: password === confirmPassword
            });
            return;
        }

        // Check password length
        if (password.length < 8) {
            setError('Password must be at least 8 characters long.');
            return;
        }

        if (password.length > 50) {
            setError('Password must be at most 50 characters long.');
            return;
        }

        // Check password strength
        if (!/[A-Z]/.test(password)) {
            setError('Password must contain at least one uppercase letter.');
            return;
        }

        if (!/[a-z]/.test(password)) {
            setError('Password must contain at least one lowercase letter.');
            return;
        }

        if (!/\d/.test(password)) {
            setError('Password must contain at least one number.');
            return;
        }

        setError('');
        setSuccess('');
        setLoading(true);

        console.log('🔧 Submitting password reset:', {
            token_length: token.length,
            password_length: password.length,
            confirm_length: confirmPassword.length,
            passwords_match: password === confirmPassword
        });

        const result = await resetPassword(
            token,
            formData.newPassword,
            formData.newPasswordConfirm
        );

        setLoading(false);

        if (result.success) {
            console.log('✅ Password reset successful');
            setSuccess(result.data.message);
            
            // ✨ Auto-login: Update auth context with new session
            await checkAuth();
            
            // ✨ Start countdown timer
            setCountdown(3);
            let timeLeft = 3;
            
            const countdownInterval = setInterval(() => {
                timeLeft -= 1;
                setCountdown(timeLeft);
                
                if (timeLeft <= 0) {
                    clearInterval(countdownInterval);
                }
            }, 1000);
            
            // Redirect to home page after 3 seconds
            setTimeout(() => {
                clearInterval(countdownInterval);
                navigate('/');
            }, 3000);
        } else {
            console.error('❌ Password reset failed:', result.error);
            setError(result.error || 'Password reset failed. Please try again.');
        }
    };

    if (!token) {
        return (
            <div className="auth-page-container">
                <div className="auth-page-card">
                    <h1 style={{ color: '#ff4444' }}>❌ Invalid Reset Link</h1>
                    <p style={{ color: '#ff6666' }}>
                        This password reset link is invalid or has expired.
                    </p>
                    <button 
                        className="auth-page-btn" 
                        onClick={() => navigate('/')}
                        style={{ marginTop: '30px' }}
                    >
                        Return to Home Page
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="auth-page-container">
            <div className="auth-page-card">
                <h1>Reset Your Password</h1>
                <p>Enter your new password below</p>

                {error && <div className="auth-error">{error}</div>}
                {success && <div className="auth-success">{success}</div>}

                {!success && (
                    <form className="auth-form" onSubmit={handleSubmit}>
                        <div className="auth-form-group">
                            <label htmlFor="newPassword">New Password</label>
                            <div className="password-input-wrapper">
                                <input
                                    type={showPassword ? "text" : "password"}
                                    id="newPassword"
                                    name="newPassword"
                                    value={formData.newPassword}
                                    onChange={handleChange}
                                    placeholder="At least 8 characters"
                                    required
                                />
                                <button
                                    type="button"
                                    className="password-toggle-btn"
                                    onClick={() => setShowPassword(!showPassword)}
                                    tabIndex="-1"
                                >
                                    {showPassword ? (
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                            <circle cx="12" cy="12" r="3"></circle>
                                        </svg>
                                    ) : (
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                                            <line x1="1" y1="1" x2="23" y2="23"></line>
                                        </svg>
                                    )}
                                </button>
                            </div>
                            <p style={{ fontSize: '12px', color: '#808080', marginTop: '5px' }}>
                                Must contain: uppercase, lowercase, and number (8-50 characters)
                            </p>
                        </div>

                        <div className="auth-form-group">
                            <label htmlFor="newPasswordConfirm">Confirm New Password</label>
                            <div className="password-input-wrapper">
                                <input
                                    type={showPasswordConfirm ? "text" : "password"}
                                    id="newPasswordConfirm"
                                    name="newPasswordConfirm"
                                    value={formData.newPasswordConfirm}
                                    onChange={handleChange}
                                    placeholder="Re-enter your new password"
                                    required
                                />
                                <button
                                    type="button"
                                    className="password-toggle-btn"
                                    onClick={() => setShowPasswordConfirm(!showPasswordConfirm)}
                                    tabIndex="-1"
                                >
                                    {showPasswordConfirm ? (
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                            <circle cx="12" cy="12" r="3"></circle>
                                        </svg>
                                    ) : (
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                                            <line x1="1" y1="1" x2="23" y2="23"></line>
                                        </svg>
                                    )}
                                </button>
                            </div>
                            {formData.newPassword && formData.newPasswordConfirm && (
                                <p style={{ 
                                    fontSize: '12px', 
                                    color: formData.newPassword === formData.newPasswordConfirm ? '#00ff41' : '#ff4444',
                                    marginTop: '5px',
                                    fontWeight: 'bold'
                                }}>
                                    {formData.newPassword === formData.newPasswordConfirm 
                                        ? '✅ Passwords match' 
                                        : '❌ Passwords do not match'}
                                </p>
                            )}
                        </div>

                        <button 
                            type="submit" 
                            className="auth-submit-btn"
                            disabled={loading}
                        >
                            {loading ? 'Resetting Password...' : 'Reset Password'}
                        </button>
                    </form>
                )}

                {success && (
                    <>
                        <p style={{ 
                            color: '#00ff41', 
                            fontSize: '15px', 
                            fontWeight: 'bold',
                            marginTop: '20px',
                            marginBottom: '10px'
                        }}>
                            🎉 You have been automatically logged in!
                        </p>
                        <p style={{ 
                            color: '#808080', 
                            fontSize: '14px',
                            marginBottom: '30px'
                        }}>
                            Redirecting to home page in {countdown} second{countdown !== 1 ? 's' : ''}...
                        </p>
                        <button 
                            className="auth-page-btn" 
                            onClick={() => navigate('/')}
                        >
                            Go to Home Page Now
                        </button>
                    </>
                )}
            </div>
        </div>
    );
};

export default ResetPasswordPage;
