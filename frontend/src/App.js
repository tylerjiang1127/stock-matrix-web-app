import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import StockChart from './components/StockChart';
import MatrixBackground from './components/MatrixBackground';
import UserMenu from './components/Auth/UserMenu';
import VerifyEmailPage from './components/Auth/VerifyEmailPage';
import ResetPasswordPage from './components/Auth/ResetPasswordPage';
import './components/StockChart.css';

function App() {
    return (
        <BrowserRouter>
            <AuthProvider>
                <div className="App">
                    <MatrixBackground />
                    <UserMenu />
                    <Routes>
                        <Route path="/" element={
                            <main>
                                <StockChart />
                            </main>
                        } />
                        <Route path="/verify-email" element={<VerifyEmailPage />} />
                        <Route path="/reset-password" element={<ResetPasswordPage />} />
                    </Routes>
                </div>
            </AuthProvider>
        </BrowserRouter>
    );
}

export default App;