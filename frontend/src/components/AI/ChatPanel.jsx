import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './ChatPanel.css';

const API_BASE = 'http://localhost:8000';

const DEFAULT_WIDTH = 480;
const MIN_WIDTH = 360;
const MAX_WIDTH = 900;

function ChatPanel() {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isStreaming, setIsStreaming] = useState(false);
    const [conversationId, setConversationId] = useState(null);
    const [toolCalls, setToolCalls] = useState([]);
    const [drawerWidth, setDrawerWidth] = useState(DEFAULT_WIDTH);
    const isResizing = useRef(false);
    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, toolCalls, scrollToBottom]);

    useEffect(() => {
        if (isOpen && inputRef.current) {
            inputRef.current.focus();
        }
    }, [isOpen]);

    const handleResizeStart = useCallback((e) => {
        e.preventDefault();
        isResizing.current = true;
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';

        const onMouseMove = (e) => {
            if (!isResizing.current) return;
            const newWidth = window.innerWidth - e.clientX;
            setDrawerWidth(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, newWidth)));
        };
        const onMouseUp = () => {
            isResizing.current = false;
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            window.removeEventListener('mousemove', onMouseMove);
            window.removeEventListener('mouseup', onMouseUp);
        };
        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
    }, []);

    const handleSend = async () => {
        const text = input.trim();
        if (!text || isStreaming) return;

        setInput('');
        setMessages(prev => [...prev, { role: 'user', content: text }]);
        setIsStreaming(true);
        setToolCalls([]);

        let assistantContent = '';
        let currentToolCalls = [];

        try {
            const resp = await fetch(`${API_BASE}/api/ai/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    message: text,
                    conversation_id: conversationId,
                }),
            });

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    const dataStr = line.slice(6);
                    let event;
                    try {
                        event = JSON.parse(dataStr);
                    } catch {
                        continue;
                    }

                    switch (event.type) {
                        case 'conversation_id':
                            setConversationId(event.conversation_id);
                            break;

                        case 'tool_call':
                            currentToolCalls = [...currentToolCalls, {
                                name: event.name,
                                arguments: event.arguments,
                                status: 'running',
                                result: null,
                            }];
                            setToolCalls([...currentToolCalls]);
                            break;

                        case 'tool_result':
                            currentToolCalls = currentToolCalls.map(tc =>
                                tc.name === event.name && tc.status === 'running'
                                    ? { ...tc, status: 'done', result: event.data }
                                    : tc
                            );
                            setToolCalls([...currentToolCalls]);
                            break;

                        case 'text':
                            assistantContent = event.content;
                            setMessages(prev => {
                                const updated = [...prev];
                                const lastIdx = updated.length - 1;
                                if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
                                    updated[lastIdx] = { role: 'assistant', content: assistantContent };
                                } else {
                                    updated.push({ role: 'assistant', content: assistantContent });
                                }
                                return updated;
                            });
                            break;

                        case 'error':
                            setMessages(prev => [...prev, {
                                role: 'assistant',
                                content: `Error: ${event.content}`,
                                isError: true,
                            }]);
                            break;

                        case 'done':
                            break;

                        default:
                            break;
                    }
                }
            }
        } catch (err) {
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: `Connection error: ${err.message}`,
                isError: true,
            }]);
        } finally {
            setIsStreaming(false);
            setToolCalls([]);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleNewChat = () => {
        setMessages([]);
        setConversationId(null);
        setToolCalls([]);
    };

    const toolDisplayName = (name) => {
        const names = {
            get_stock_price: 'Fetching price data',
            get_technical_indicators: 'Analyzing indicators',
            get_moving_averages: 'Checking moving averages',
            get_company_overview: 'Looking up company info',
            get_financial_statements: 'Reading financials',
            get_news_sentiment: 'Checking news sentiment',
            get_market_summary: 'Getting market overview',
            compare_stocks: 'Comparing stocks',
        };
        return names[name] || name;
    };

    return (
        <>
            {!isOpen && (
                <button
                    className="chat-fab"
                    onClick={() => setIsOpen(true)}
                    title="AI Stock Analyst"
                >
                    {'✨'}
                </button>
            )}

            <div
                className={`chat-drawer ${isOpen ? 'open' : ''}`}
                style={isOpen ? { width: drawerWidth, right: 0 } : undefined}
            >
                <div className="chat-resize-handle" onMouseDown={handleResizeStart} />
                <div className="chat-header">
                    <div className="chat-header-left">
                        <span className="chat-header-icon">{'✨'}</span>
                        <span className="chat-header-title">Stock Matrix AI</span>
                    </div>
                    <div className="chat-header-right">
                        <button className="chat-new-btn" onClick={handleNewChat} title="New conversation">
                            +
                        </button>
                        <button className="chat-close-btn" onClick={() => setIsOpen(false)} title="Close chat">
                            ✕
                        </button>
                    </div>
                </div>

                <div className="chat-messages">
                    {messages.length === 0 && (
                        <div className="chat-welcome">
                            <div className="chat-welcome-icon">{'✨'}</div>
                            <p>Ask me anything about stocks.</p>
                            <div className="chat-suggestions">
                                {[
                                    "What's AAPL's current RSI?",
                                    "Compare NVDA and AMD",
                                    "Show me today's top movers",
                                    "Analyze TSLA's fundamentals",
                                ].map((q, i) => (
                                    <button
                                        key={i}
                                        className="chat-suggestion"
                                        onClick={() => {
                                            setInput(q);
                                            setTimeout(() => inputRef.current?.focus(), 0);
                                        }}
                                    >
                                        {q}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {messages.map((msg, i) => (
                        <div key={i} className={`chat-message ${msg.role} ${msg.isError ? 'error' : ''}`}>
                            {msg.role === 'assistant' ? (
                                <div className="chat-message-content">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                                </div>
                            ) : (
                                <div className="chat-message-content">{msg.content}</div>
                            )}
                        </div>
                    ))}

                    {toolCalls.length > 0 && (
                        <div className="chat-tool-calls">
                            {toolCalls.map((tc, i) => (
                                <div key={i} className={`tool-call-card ${tc.status}`}>
                                    <span className="tool-call-icon">
                                        {tc.status === 'running' ? '⏳' : '✓'}
                                    </span>
                                    <span className="tool-call-label">
                                        {toolDisplayName(tc.name)}
                                        {tc.arguments?.symbol ? ` (${tc.arguments.symbol})` : ''}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}

                    {isStreaming && toolCalls.length === 0 && (
                        <div className="chat-typing">
                            <span></span><span></span><span></span>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>

                <div className="chat-input-area">
                    <textarea
                        ref={inputRef}
                        className="chat-input"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask about any stock..."
                        rows={1}
                        disabled={isStreaming}
                    />
                    <button
                        className="chat-send-btn"
                        onClick={handleSend}
                        disabled={!input.trim() || isStreaming}
                    >
                        {'↑'}
                    </button>
                </div>
            </div>
        </>
    );
}

export default ChatPanel;
