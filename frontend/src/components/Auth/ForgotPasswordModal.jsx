import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import './Auth.css';

const ForgotPasswordModal = ({ onClose, onSwitchToLogin }) => {
    const { forgotPassword } = useAuth();
    const [email, setEmail] = useState('');
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setSuccess('');
        setLoading(true);

        const result = await forgotPassword(email);

        setLoading(false);

        if (result.success) {
            setSuccess(result.data.message);
            setEmail('');
        } else {
            setError(result.error);
        }
    };

    return (
        <div className="auth-modal-overlay" onClick={onClose}>
            <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
                <button className="auth-modal-close" onClick={onClose}>&times;</button>
                
                <h2>Reset Password</h2>
                <p>Enter your email to receive a password reset link</p>

                {error && <div className="auth-error">{error}</div>}
                {success && <div className="auth-success">{success}</div>}

                {!success && (
                    <form className="auth-form" onSubmit={handleSubmit}>
                        <div className="auth-form-group">
                            <label htmlFor="email">Email Address</label>
                            <input
                                type="email"
                                id="email"
                                name="email"
                                value={email}
                                onChange={(e) => {
                                    setEmail(e.target.value);
                                    setError('');
                                }}
                                placeholder="your.email@example.com"
                                required
                            />
                        </div>

                        <button 
                            type="submit" 
                            className="auth-submit-btn"
                            disabled={loading}
                        >
                            {loading ? 'Sending...' : 'Send Reset Link'}
                        </button>
                    </form>
                )}

                <div className="auth-footer">
                    Remember your password?{' '}
                    <span className="auth-link" onClick={onSwitchToLogin}>
                        Log In
                    </span>
                </div>
            </div>
        </div>
    );
};

export default ForgotPasswordModal;
