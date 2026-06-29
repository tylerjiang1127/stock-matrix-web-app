import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { openAuthModal } from '../../utils/quota';
import './ProfilePage.css';

const API_BASE = 'http://localhost:8000';

const ACTION_LABELS = {
    chat: 'AI Chat',
    screener: 'AI Screener',
    monthly_refresh: 'Monthly refresh',
    referral_bonus: 'Referral bonus',
    welcome_bonus: 'Welcome bonus',
    chat_refund: 'Chat refund',
    screener_refund: 'Screener refund',
    tier_upgrade: 'Upgrade bonus',
    admin_adjust: 'Adjustment',
    purchase: 'Purchase',
};

function formatDate(iso) {
    if (!iso) return '—';
    try {
        // Date-only strings (YYYY-MM-DD, e.g. resets_on) must be parsed as LOCAL,
        // otherwise new Date() treats them as UTC midnight and a negative-offset
        // timezone displays the previous day.
        const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
        const d = m ? new Date(+m[1], +m[2] - 1, +m[3]) : new Date(iso);
        return d.toLocaleDateString(undefined, {
            year: 'numeric', month: 'short', day: 'numeric',
        });
    } catch {
        return '—';
    }
}

function ProfilePage() {
    const { isAuthenticated, loading: authLoading, refreshCredits } = useAuth();
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [copied, setCopied] = useState(false);
    const [switching, setSwitching] = useState(false);

    const loadProfile = async () => {
        try {
            const resp = await fetch(`${API_BASE}/api/me/profile`, { credentials: 'include' });
            if (resp.ok) setData(await resp.json());
        } catch {
            /* leave data null → error state */
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (authLoading) return;
        if (!isAuthenticated) {
            setLoading(false);
            return;
        }
        loadProfile();
    }, [isAuthenticated, authLoading]);

    const switchTier = async (target) => {
        if (!data?.user?.user_id || switching) return;
        setSwitching(true);
        try {
            await fetch(`${API_BASE}/api/admin/users/${data.user.user_id}/tier`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tier: target }),
            });
            await loadProfile();
            refreshCredits();
        } finally {
            setSwitching(false);
        }
    };

    const copyLink = async () => {
        if (!data?.referral?.referral_link) return;
        try {
            await navigator.clipboard.writeText(data.referral.referral_link);
            setCopied(true);
            setTimeout(() => setCopied(false), 1800);
        } catch {
            /* clipboard blocked — ignore */
        }
    };

    if (authLoading || loading) {
        return <div className="profile-page"><div className="profile-spinner" /></div>;
    }

    if (!isAuthenticated) {
        return (
            <div className="profile-page">
                <div className="profile-gate">
                    <div className="profile-gate-icon">🔒</div>
                    <p>Log in to view your profile, credits, and referrals.</p>
                    <button className="profile-btn" onClick={() => openAuthModal('login')}>Log In</button>
                </div>
            </div>
        );
    }

    if (!data) {
        return <div className="profile-page"><div className="profile-gate"><p>Couldn't load your profile. Please try again.</p></div></div>;
    }

    const { user, credits, referral, history } = data;
    const tierLabel = (user.tier || 'base').toUpperCase();

    return (
        <div className="profile-page">
            {/* Account header */}
            <div className="profile-header">
                <div className="profile-avatar">{user.username?.charAt(0).toUpperCase() || 'U'}</div>
                <div className="profile-identity">
                    <div className="profile-name-row">
                        <h1 className="profile-username">{user.username}</h1>
                        <span className={`profile-tier-badge tier-${user.tier}`}>{tierLabel}</span>
                    </div>
                    <div className="profile-email">
                        {user.email}
                        {user.is_email_verified
                            ? <span className="profile-verified" title="Email verified"> ✓ verified</span>
                            : <span className="profile-unverified" title="Email not verified"> • unverified</span>}
                    </div>
                    <div className="profile-meta">
                        Member since {formatDate(user.created_at)} · Last login {formatDate(user.last_login_at)}
                    </div>
                </div>
            </div>

            <div className="profile-grid">
                {/* Credits dashboard */}
                <div className="profile-card">
                    <h2 className="profile-card-title">Matrix Credits</h2>
                    <div className="credits-total">{credits.total}<span className="credits-total-label"> total</span></div>
                    <div className="credits-breakdown">
                        <div className="credits-bucket">
                            <div className="credits-bucket-val">{credits.base}<span className="credits-bucket-cap"> / {credits.monthly_allotment}</span></div>
                            <div className="credits-bucket-label">Base · resets {formatDate(credits.resets_on)}</div>
                        </div>
                        <div className="credits-bucket">
                            <div className="credits-bucket-val boost">{credits.boost}</div>
                            <div className="credits-bucket-label">Boost · never expires</div>
                        </div>
                    </div>
                    {user.tier === 'base' && (
                        <div className="profile-upgrade-note">
                            Premium unlocks 500 monthly credits. <span className="muted">(coming soon)</span>
                        </div>
                    )}
                    {user.is_admin && (
                        <div className="profile-admin">
                            <span className="profile-admin-tag">ADMIN</span>
                            <button
                                className="profile-btn"
                                disabled={switching}
                                onClick={() => switchTier(user.tier === 'premium' ? 'base' : 'premium')}
                            >
                                {switching ? '…' : (user.tier === 'premium' ? 'Switch to Base' : 'Switch to Premium')}
                            </button>
                        </div>
                    )}
                </div>

                {/* Referral card */}
                <div className="profile-card">
                    <h2 className="profile-card-title">Invite friends</h2>
                    <p className="referral-sub">
                        You earn <strong>+100</strong> boost credits per friend who joins &amp; verifies — they get <strong>+50</strong>.
                    </p>
                    <div className="referral-link-row">
                        <input className="referral-link-input" readOnly value={referral.referral_link || ''} />
                        <button className="profile-btn" onClick={copyLink}>{copied ? 'Copied!' : 'Copy'}</button>
                    </div>
                    <div className="referral-stats">
                        <div className="referral-stat"><span className="referral-stat-num">{referral.total_referred}</span><span className="referral-stat-label">invited</span></div>
                        <div className="referral-stat"><span className="referral-stat-num">{referral.successful}</span><span className="referral-stat-label">joined</span></div>
                        <div className="referral-stat"><span className="referral-stat-num">{referral.credits_earned}</span><span className="referral-stat-label">credits earned</span></div>
                    </div>
                </div>
            </div>

            {/* Usage history */}
            <div className="profile-card">
                <h2 className="profile-card-title">Recent credit activity</h2>
                {history.length === 0 ? (
                    <p className="history-empty">No activity yet. Your AI Chat and Screener usage will show up here.</p>
                ) : (
                    <ul className="history-list">
                        {history.map((h, i) => (
                            <li key={i} className="history-row">
                                <span className="history-action">{ACTION_LABELS[h.action] || h.action}</span>
                                <span className={`history-delta ${h.credits_delta < 0 ? 'neg' : 'pos'}`}>
                                    {h.credits_delta > 0 ? '+' : ''}{h.credits_delta}
                                </span>
                                <span className="history-bucket">{h.bucket}</span>
                                <span className="history-date">{formatDate(h.created_at)}</span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}

export default ProfilePage;
