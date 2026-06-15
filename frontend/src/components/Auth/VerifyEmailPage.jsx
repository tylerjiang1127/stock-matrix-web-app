import React, { useEffect, useState, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import './Auth.css';

const VerifyEmailPage = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { verifyEmail, checkAuth } = useAuth();
    const [status, setStatus] = useState('verifying'); // 'verifying', 'success', 'error'
    const [message, setMessage] = useState('');
    const [countdown, setCountdown] = useState(3); // Countdown timer
    
    // 🔧 FIX: Use ref to prevent duplicate API calls in React 18 Strict Mode
    const hasVerified = useRef(false);
    const redirectTimerRef = useRef(null);

    useEffect(() => {
        const token = searchParams.get('token');
        
        if (!token) {
            setStatus('error');
            setMessage('Invalid verification link');
            return;
        }

        // 🔧 FIX: Prevent duplicate verification attempts
        if (hasVerified.current) {
            return;
        }
        
        hasVerified.current = true;

        const verify = async () => {
            const result = await verifyEmail(token);
            
            if (result.success) {
                setStatus('success');
                setMessage(result.data.message);
                
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
                
                // ✨ Redirect to home page after 3 seconds
                redirectTimerRef.current = setTimeout(() => {
                    clearInterval(countdownInterval);
                    navigate('/');
                }, 3000);
            } else {
                setStatus('error');
                setMessage(result.error);
            }
        };

        verify();
        
        // Cleanup function
        return () => {
            if (redirectTimerRef.current) {
                clearTimeout(redirectTimerRef.current);
            }
        };
    }, [searchParams, verifyEmail, checkAuth, navigate]);
    
    // ✨ Manual redirect handler
    const handleGoHome = () => {
        if (redirectTimerRef.current) {
            clearTimeout(redirectTimerRef.current);
        }
        navigate('/');
    };

    return (
        <div className="auth-page-container">
            <div className="auth-page-card">
                {status === 'verifying' && (
                    <>
                        <h1>Verifying Email...</h1>
                        <div className="auth-page-spinner"></div>
                        <p>Please wait while we verify your email address.</p>
                    </>
                )}

                {status === 'success' && (
                    <>
                        <h1>✅ Email Verified!</h1>
                        <p style={{ fontSize: '16px', marginBottom: '10px' }}>{message}</p>
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
                            onClick={handleGoHome}
                        >
                            Go to Home Page Now
                        </button>
                    </>
                )}

                {status === 'error' && (
                    <>
                        <h1 style={{ color: '#ff4444' }}>❌ Verification Failed</h1>
                        <p style={{ color: '#ff6666' }}>{message}</p>
                        <button 
                            className="auth-page-btn" 
                            onClick={handleGoHome}
                            style={{ marginTop: '30px' }}
                        >
                            Return to Home Page
                        </button>
                    </>
                )}
            </div>
        </div>
    );
};

export default VerifyEmailPage;
