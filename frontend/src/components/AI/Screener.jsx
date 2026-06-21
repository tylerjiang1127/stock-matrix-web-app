import React, { useState, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './Screener.css';

const API_BASE = 'http://localhost:8000';

const EXAMPLE_QUERIES = [
    "Find oversold stocks with RSI below 30",
    "Stocks with strong momentum — RSI above 60 and MACD histogram positive",
    "Stocks trading above their 250-day moving average under $50",
    "High volume breakouts above upper Bollinger Band",
    "Stocks near their 20-day SMA with low RSI",
    "Show me stocks where price crossed above SMA20 today",
];

function Screener() {
    const [query, setQuery] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
    const inputRef = useRef(null);

    const handleSearch = async (searchQuery) => {
        const text = (searchQuery || query).trim();
        if (!text || isLoading) return;

        setIsLoading(true);
        setError(null);
        setResult(null);

        try {
            const resp = await fetch(`${API_BASE}/api/ai/screener`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: text, limit: 30 }),
            });
            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Screening failed');
            }
            const data = await resp.json();
            setResult(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleSearch();
        }
    };

    const handleSort = (key) => {
        setSortConfig(prev => ({
            key,
            direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc',
        }));
    };

    const sortedResults = result?.results ? [...result.results].sort((a, b) => {
        if (!sortConfig.key) return 0;
        const aVal = a[sortConfig.key] ?? 0;
        const bVal = b[sortConfig.key] ?? 0;
        if (typeof aVal === 'string') return sortConfig.direction === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
        return sortConfig.direction === 'asc' ? aVal - bVal : bVal - aVal;
    }) : [];

    const formatNum = (val, decimals = 2) => {
        if (val == null) return '—';
        return Number(val).toFixed(decimals);
    };

    const formatVolume = (val) => {
        if (val == null) return '—';
        if (val >= 1e9) return (val / 1e9).toFixed(1) + 'B';
        if (val >= 1e6) return (val / 1e6).toFixed(1) + 'M';
        if (val >= 1e3) return (val / 1e3).toFixed(0) + 'K';
        return val.toString();
    };

    const getSortIcon = (key) => {
        if (sortConfig.key !== key) return ' ↕';
        return sortConfig.direction === 'asc' ? ' ↑' : ' ↓';
    };

    const columns = [
        { key: 'symbol', label: 'Symbol' },
        { key: 'close', label: 'Price' },
        { key: 'rsi', label: 'RSI' },
        { key: 'macd_hist', label: 'MACD Hist' },
        { key: 'sma20', label: 'SMA20' },
        { key: 'sma60', label: 'SMA60' },
        { key: 'volume', label: 'Volume' },
    ];

    return (
        <div className="screener-page">
            <div className="screener-header">
                <h1 className="screener-title">Stock Screener</h1>
                <p className="screener-subtitle">Describe the stocks you're looking for in plain English</p>
            </div>

            <div className="screener-search-area">
                <div className="screener-input-row">
                    <input
                        ref={inputRef}
                        className="screener-input"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="e.g. Find oversold stocks with high volume..."
                        disabled={isLoading}
                    />
                    <button
                        className="screener-search-btn"
                        onClick={() => handleSearch()}
                        disabled={!query.trim() || isLoading}
                    >
                        {isLoading ? 'Screening...' : 'Screen'}
                    </button>
                </div>

                {!result && !isLoading && (
                    <div className="screener-examples">
                        <span className="screener-examples-label">Try:</span>
                        <div className="screener-chips">
                            {EXAMPLE_QUERIES.map((q, i) => (
                                <button
                                    key={i}
                                    className="screener-chip"
                                    onClick={() => {
                                        setQuery(q);
                                        handleSearch(q);
                                    }}
                                >
                                    {q}
                                </button>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {isLoading && (
                <div className="screener-loading">
                    <div className="screener-spinner" />
                    <p>Analyzing your criteria and scanning 500+ stocks...</p>
                </div>
            )}

            {error && (
                <div className="screener-error">
                    <p>{error}</p>
                </div>
            )}

            {result && (
                <div className="screener-results">
                    <div className="screener-explanation">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.explanation}</ReactMarkdown>
                    </div>

                    <div className="screener-table-header">
                        <h3>{result.total_results} stocks found</h3>
                        <span className="screener-filter-desc">{result.filter_description}</span>
                    </div>

                    <div className="screener-table-wrap">
                        <table className="screener-table">
                            <thead>
                                <tr>
                                    {columns.map(col => (
                                        <th key={col.key} onClick={() => handleSort(col.key)}>
                                            {col.label}{getSortIcon(col.key)}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {sortedResults.map((row, i) => (
                                    <tr key={i}>
                                        <td className="screener-symbol">{row.symbol}</td>
                                        <td>${formatNum(row.close)}</td>
                                        <td className={row.rsi < 30 ? 'val-low' : row.rsi > 70 ? 'val-high' : ''}>
                                            {formatNum(row.rsi)}
                                        </td>
                                        <td className={row.macd_hist > 0 ? 'val-pos' : row.macd_hist < 0 ? 'val-neg' : ''}>
                                            {formatNum(row.macd_hist, 3)}
                                        </td>
                                        <td>{formatNum(row.sma20)}</td>
                                        <td>{formatNum(row.sma60)}</td>
                                        <td>{formatVolume(row.volume)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}

export default Screener;
