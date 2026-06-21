import React, { useState, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './DailyIntelligence.css';

const API_BASE = 'http://localhost:8000';

const getTextFromChildren = (children) => {
    let text = '';
    React.Children.forEach(children, (child) => {
        if (typeof child === 'string') text += child;
        else if (typeof child === 'number') text += String(child);
        else if (child?.props?.children) text += getTextFromChildren(child.props.children);
    });
    return text;
};

const classifyCell = (text) => {
    const trimmed = text.trim();
    const lower = trimmed.toLowerCase();

    if (/^low$/i.test(trimmed)) return 'cell-risk cell-risk-low';
    if (/^low-medium$/i.test(trimmed)) return 'cell-risk cell-risk-low-medium';
    if (/^medium$/i.test(trimmed)) return 'cell-risk cell-risk-medium';
    if (/^medium-high$/i.test(trimmed)) return 'cell-risk cell-risk-medium-high';
    if (/^high$/i.test(trimmed)) return 'cell-risk cell-risk-high';

    if (lower.includes('strong momentum')) return 'cell-badge cell-badge-bullish';
    if (lower.includes('breakdown risk') || lower.includes('crash')) return 'cell-badge cell-badge-bearish';
    if (lower.includes('short-term overheated')) return 'cell-badge cell-badge-warning';
    if (lower.includes('consolidating') || lower.includes('awaiting catalyst')) return 'cell-badge cell-badge-neutral';
    if (lower.includes('pullback support') || lower.includes('needs watching')) return 'cell-badge cell-badge-caution';
    if (lower.includes('low-level recovery')) return 'cell-badge cell-badge-recovery';

    if (/^\+\d/.test(trimmed)) return 'cell-positive';
    if (/^-\d/.test(trimmed)) return 'cell-negative';

    if (lower.includes('bullish') || lower.includes('broadly bullish')) return 'cell-signal-positive';
    if (lower.includes('leading') || lower.includes('strongest') || lower.includes('outperforming')) return 'cell-signal-positive';
    if (lower.includes('modestly positive') || lower.includes('healthy')) return 'cell-signal-positive';
    if (lower.includes('bearish') || lower.includes('deeply inverted') || lower.includes('under pressure')) return 'cell-signal-negative';
    if (lower.includes('lagging') || lower.includes('weakest') || lower.includes('underperforming')) return 'cell-signal-negative';
    if (lower.includes('continued weakness') || lower.includes('sharp selloff') || lower.includes('crash')) return 'cell-signal-negative';
    if (lower.includes('overbought') || lower.includes('elevated') || lower.includes('steepening')) return 'cell-signal-warning';
    if (lower.includes('mega-cap driven') || lower.includes('narrow')) return 'cell-signal-warning';

    if (lower.includes('strong uptrend') || lower.includes('strong bounce') || lower.includes('uptrend accelerating')) return 'cell-trend-up';
    if (lower.includes('breakdown') || lower.includes('downtrend') || lower.includes('sharp selloff')) return 'cell-trend-down';
    if (lower.includes('rebounding') || lower.includes('uptrend')) return 'cell-trend-up';
    if (lower.includes('pullback')) return 'cell-trend-down';
    if (lower === 'flat' || lower.includes('breakout')) return 'cell-trend-flat';

    return '';
};

const mdComponents = {
    td: ({ children, ...props }) => {
        const text = getTextFromChildren(children);
        const cls = classifyCell(text);
        return <td className={cls || undefined} {...props}>{children}</td>;
    },
};

const SECTION_NAV = [
    { en: 'Summary', zh: '总结' },
    { en: 'Market', zh: '大盘' },
    { en: 'Intraday', zh: '复盘' },
    { en: 'Macro', zh: '宏观' },
    { en: 'Sectors', zh: '板块' },
    { en: 'Themes', zh: '主题' },
    { en: 'Breadth', zh: '宽度' },
    { en: 'Technicals', zh: '技术面' },
    { en: 'Stocks', zh: '个股' },
    { en: 'Rotation', zh: '轮动' },
    { en: 'Watchlist', zh: '观察' },
    { en: 'Tomorrow', zh: '明日' },
    { en: 'Risk', zh: '风险' },
    { en: 'Conclusion', zh: '结论' },
];

function DailyIntelligence() {
    const [reports, setReports] = useState([]);
    const [selectedDate, setSelectedDate] = useState(null);
    const [currentReport, setCurrentReport] = useState(null);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [genProgress, setGenProgress] = useState('');
    const [lang, setLang] = useState('en');

    const fetchReports = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/api/ai/reports?limit=30`, {
                credentials: 'include',
            });
            const data = await res.json();
            setReports(data.reports || []);
            if (data.reports?.length > 0 && !selectedDate) {
                setSelectedDate(data.reports[0].date);
            }
        } catch (err) {
            console.error('Failed to fetch reports:', err);
        } finally {
            setLoading(false);
        }
    }, [selectedDate]);

    useEffect(() => {
        fetchReports();
    }, [fetchReports]);

    useEffect(() => {
        if (!selectedDate) return;
        const fetchReport = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/ai/reports/${selectedDate}`, {
                    credentials: 'include',
                });
                if (res.ok) {
                    const data = await res.json();
                    setCurrentReport(data);
                }
            } catch (err) {
                console.error('Failed to fetch report:', err);
            }
        };
        fetchReport();
    }, [selectedDate]);

    const handleGenerate = async () => {
        setGenerating(true);
        setGenProgress('Gathering market data...');
        try {
            await fetch(`${API_BASE}/api/ai/reports/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({}),
            });
            setGenProgress('AI is analyzing 500+ stocks and writing report...');
            setTimeout(() => {
                setGenProgress('Finalizing report...');
            }, 15000);
            setTimeout(() => {
                fetchReports();
                setGenerating(false);
                setGenProgress('');
            }, 30000);
        } catch (err) {
            console.error('Failed to generate report:', err);
            setGenerating(false);
            setGenProgress('');
        }
    };

    const reportContent = currentReport?.sections?.report_markdown
        || currentReport?.sections?.executive_summary
        || '';
    const reportContentZh = currentReport?.sections?.report_markdown_zh || '';

    const marketMood = currentReport?.sections?.market_mood || 'neutral';

    const scrollToSection = (index) => {
        const headers = document.querySelectorAll('.report-markdown-body h2');
        if (headers[index]) {
            headers[index].scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    };

    if (loading) {
        return (
            <div className="intelligence-page">
                <div className="di-loading-spinner">Loading reports...</div>
            </div>
        );
    }

    return (
        <div className="intelligence-page">
            <div className="intelligence-header">
                <h1>AI Macro Daily Report</h1>
                <div className="header-actions">
                    <button
                        className="generate-btn"
                        onClick={handleGenerate}
                        disabled={generating}
                    >
                        {generating ? 'Generating...' : 'Generate Report'}
                    </button>
                </div>
            </div>

            <div className="intelligence-layout">
                {/* Left: Date list */}
                <div className="date-list">
                    {reports.length === 0 ? (
                        <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: 13, padding: '12px' }}>
                            No reports yet. Click "Generate Report" to create one.
                        </div>
                    ) : (
                        reports.map(r => {
                            const mood = r.sections?.market_mood || 'neutral';
                            return (
                                <button
                                    key={r.date}
                                    className={`date-item ${selectedDate === r.date ? 'active' : ''}`}
                                    onClick={() => setSelectedDate(r.date)}
                                >
                                    <span className={`mood-dot ${mood}`} />
                                    <span>{r.date}</span>
                                </button>
                            );
                        })
                    )}
                </div>

                {/* Right: Report content */}
                <div className="report-content">
                    {generating && (
                        <div className="report-generating">
                            <div className="gen-spinner" />
                            <p>{genProgress}</p>
                        </div>
                    )}

                    {!currentReport && !generating ? (
                        <div className="empty-state">
                            <div className="empty-state-icon">📊</div>
                            <p>No report selected</p>
                            <p>Generate a report or select one from the left panel</p>
                            <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', marginTop: 8 }}>
                                Reports auto-generate at 6:00 PM ET on trading days
                            </p>
                        </div>
                    ) : currentReport && (
                        <div className="report-markdown-wrap">
                            <div className="report-top-bar">
                                <div className={`market-mood-badge ${marketMood}`}>
                                    <span className={`mood-dot ${marketMood}`} />
                                    {marketMood}
                                </div>
                                <div className="lang-toggle">
                                    <button className={lang === 'en' ? 'active' : ''} onClick={() => setLang('en')}>EN</button>
                                    <button className={lang === 'zh' ? 'active' : ''} onClick={() => setLang('zh')}>中文</button>
                                </div>
                            </div>

                            <div className="section-nav">
                                {SECTION_NAV.map((s, i) => (
                                    <button key={i} className="section-chip" onClick={() => scrollToSection(i)}>
                                        {lang === 'zh' ? s.zh : s.en}
                                    </button>
                                ))}
                            </div>

                            <div className="report-markdown-body">
                                <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                                    {lang === 'zh' && reportContentZh ? reportContentZh : reportContent}
                                </ReactMarkdown>
                            </div>
                            {currentReport?.tokens_used && (
                                <div className="report-meta">
                                    Model: {currentReport.model || 'deepseek-chat'} |
                                    Tokens: {currentReport.tokens_used.input + currentReport.tokens_used.output}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default DailyIntelligence;
