import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import StockChart from './components/StockChart';
import MatrixBackground from './components/MatrixBackground';
import UserMenu from './components/Auth/UserMenu';
import VerifyEmailPage from './components/Auth/VerifyEmailPage';
import ResetPasswordPage from './components/Auth/ResetPasswordPage';
import Sidebar from './components/Navigation/Sidebar';
import DailyIntelligence from './components/AI/DailyIntelligence';
import ChatPanel from './components/AI/ChatPanel';
import Screener from './components/AI/Screener';
import ProfilePage from './components/Auth/ProfilePage';
import './components/StockChart.css';

function App() {
    return (
        <BrowserRouter>
            <AuthProvider>
                <div className="App">
                    <MatrixBackground />
                    <UserMenu />
                    <ChatPanel />
                    <div className="app-layout">
                        <Sidebar />
                        <div className="app-main-content">
                            <Routes>
                                <Route path="/intelligence" element={<DailyIntelligence />} />
                                <Route path="/screener" element={<Screener />} />
                                <Route path="/profile" element={<ProfilePage />} />
                                <Route path="/verify-email" element={<VerifyEmailPage />} />
                                <Route path="/reset-password" element={<ResetPasswordPage />} />
                                <Route path="/:ticker?" element={
                                    <main>
                                        <StockChart />
                                    </main>
                                } />
                            </Routes>
                        </div>
                    </div>
                </div>
            </AuthProvider>
        </BrowserRouter>
    );
}

export default App;
