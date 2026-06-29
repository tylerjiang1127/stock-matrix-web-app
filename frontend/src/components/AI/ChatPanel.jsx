import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { openAuthModal, interpretQuota, errorText } from '../../utils/quota';
import { useAuth } from '../../contexts/AuthContext';
import './ChatPanel.css';

const API_BASE = 'http://localhost:8000';
const DEFAULT_WIDTH = 480;
const MIN_WIDTH = 360;
const MAX_WIDTH = 900;

let _tabSeq = 0;
const makeSession = (overrides = {}) => ({
    tabId: `tab_${++_tabSeq}`,
    conversationId: null,
    title: 'New Chat',
    messages: [],
    loaded: true,
    ...overrides,
});

function ChatPanel() {
    const { isAuthenticated } = useAuth();

    // Combined chat state to keep list + activeTabId in sync atomically
    const [chat, setChat] = useState(() => {
        const s = makeSession();
        return { list: [s], activeTabId: s.tabId };
    });
    const { list: sessionList, activeTabId } = chat;
    const activeSession = sessionList.find(s => s.tabId === activeTabId) || sessionList[0];

    const [input, setInput] = useState('');
    const [isStreaming, setIsStreaming] = useState(false);
    const [editingTabId, setEditingTabId] = useState(null);
    const [editingTitle, setEditingTitle] = useState('');

    const [isOpen, setIsOpen] = useState(false);
    const [drawerWidth, setDrawerWidth] = useState(DEFAULT_WIDTH);

    const isResizing = useRef(false);
    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);
    const editInputRef = useRef(null);
    const tabBarRef = useRef(null);

    // ── Helpers ───────────────────────────────────────────
    const patchSession = useCallback((tabId, patch) => {
        setChat(prev => ({
            ...prev,
            list: prev.list.map(s => s.tabId === tabId ? { ...s, ...patch } : s),
        }));
    }, []);

    // ── Scroll to bottom on new messages ─────────────────
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [activeSession?.messages]);

    // ── Focus input when opening or switching tabs ────────
    useEffect(() => {
        if (isOpen) inputRef.current?.focus();
    }, [isOpen, activeTabId]);

    // ── Focus rename input when edit starts ───────────────
    useEffect(() => {
        if (editingTabId) {
            editInputRef.current?.focus();
            editInputRef.current?.select();
        }
    }, [editingTabId]);

    // ── Scroll active tab into view in the tab bar ────────
    useEffect(() => {
        const bar = tabBarRef.current;
        if (!bar) return;
        const activeEl = bar.querySelector('.chat-tab.active');
        if (activeEl) activeEl.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    }, [activeTabId, sessionList.length]);

    // ── Load conversation history for logged-in users ─────
    const loadHistory = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/api/ai/chat/conversations`, { credentials: 'include' });
            if (!res.ok) return;
            const { conversations } = await res.json();
            const fresh = makeSession();
            const history = (conversations || []).map(c => makeSession({
                tabId: c.conversation_id,
                conversationId: c.conversation_id,
                title: c.title || 'Chat',
                messages: [],
                loaded: false,
            }));
            setChat({ list: [fresh, ...history], activeTabId: fresh.tabId });
        } catch {}
    }, []);

    useEffect(() => {
        if (isAuthenticated) {
            loadHistory();
        } else {
            const s = makeSession();
            setChat({ list: [s], activeTabId: s.tabId });
        }
    }, [isAuthenticated, loadHistory]);

    // ── Session management ────────────────────────────────
    const createNewSession = () => {
        const s = makeSession();
        setChat(prev => ({ list: [...prev.list, s], activeTabId: s.tabId }));
        setInput('');
    };

    const closeSession = (tabId) => {
        // Find the session before removing it so we can delete from backend
        const session = sessionList.find(s => s.tabId === tabId);
        if (isAuthenticated && session?.conversationId) {
            fetch(`${API_BASE}/api/ai/chat/conversations/${session.conversationId}`, {
                method: 'DELETE',
                credentials: 'include',
            }).catch(() => {});
        }
        setChat(prev => {
            const remaining = prev.list.filter(s => s.tabId !== tabId);
            if (remaining.length === 0) {
                const s = makeSession();
                return { list: [s], activeTabId: s.tabId };
            }
            let nextActiveTabId = prev.activeTabId;
            if (prev.activeTabId === tabId) {
                const idx = prev.list.findIndex(s => s.tabId === tabId);
                nextActiveTabId = remaining[Math.min(idx, remaining.length - 1)].tabId;
            }
            return { list: remaining, activeTabId: nextActiveTabId };
        });
    };

    const switchSession = async (tabId) => {
        setChat(prev => ({ ...prev, activeTabId: tabId }));
        const s = sessionList.find(s => s.tabId === tabId);
        if (s && !s.loaded && s.conversationId) {
            try {
                const res = await fetch(
                    `${API_BASE}/api/ai/chat/conversations/${s.conversationId}`,
                    { credentials: 'include' }
                );
                if (res.ok) {
                    const data = await res.json();
                    // Collapse consecutive assistant messages caused by the old
                    // bug where every streaming chunk was saved as a separate entry.
                    // Keep the longest (most complete) version of each run.
                    const raw = (data.messages || [])
                        .filter(m => m.role !== 'system' && m.role !== 'tool')
                        .map(m => ({ role: m.role, content: m.content || '' }));
                    const msgs = [];
                    for (const m of raw) {
                        const prev = msgs[msgs.length - 1];
                        if (prev && prev.role === 'assistant' && m.role === 'assistant') {
                            if (m.content.length > prev.content.length) prev.content = m.content;
                        } else {
                            msgs.push({ ...m });
                        }
                    }
                    patchSession(tabId, { messages: msgs, loaded: true });
                }
            } catch {}
        }
    };

    // ── Tab rename ────────────────────────────────────────
    const startRename = (tabId, currentTitle) => {
        setEditingTabId(tabId);
        setEditingTitle(currentTitle);
    };

    const commitRename = async () => {
        if (!editingTabId) return;
        const trimmed = editingTitle.trim() || 'Chat';
        const tabId = editingTabId;
        patchSession(tabId, { title: trimmed });
        setEditingTabId(null);
        setEditingTitle('');
        const s = sessionList.find(s => s.tabId === tabId);
        if (isAuthenticated && s?.conversationId) {
            try {
                await fetch(`${API_BASE}/api/ai/chat/conversations/${s.conversationId}/title`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ title: trimmed }),
                });
            } catch {}
        }
    };

    // ── Resize ────────────────────────────────────────────
    const handleResizeStart = useCallback((e) => {
        e.preventDefault();
        isResizing.current = true;
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        const onMouseMove = (e) => {
            if (!isResizing.current) return;
            setDrawerWidth(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, window.innerWidth - e.clientX)));
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

    // ── Send message ──────────────────────────────────────
    const handleSend = async () => {
        const text = input.trim();
        if (!text || isStreaming) return;

        const sessionTabId = activeTabId;
        const sessionConvId = activeSession?.conversationId ?? null;

        setInput('');
        setChat(prev => ({
            ...prev,
            list: prev.list.map(s =>
                s.tabId === sessionTabId
                    ? { ...s, messages: [...s.messages, { role: 'user', content: text }] }
                    : s
            ),
        }));
        setIsStreaming(true);

        let assistantContent = '';

        try {
            const resp = await fetch(`${API_BASE}/api/ai/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ message: text, conversation_id: sessionConvId }),
            });

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                const quota = interpretQuota(err.detail);
                setChat(prev => ({
                    ...prev,
                    list: prev.list.map(s =>
                        s.tabId !== sessionTabId ? s : {
                            ...s,
                            messages: [...s.messages, {
                                role: 'assistant',
                                content: quota
                                    ? quota.message
                                    : `Error: ${errorText(err.detail, 'Request failed')}`,
                                isError: !quota,
                                isQuota: !!quota,
                                canRegister: quota?.canRegister,
                            }],
                        }
                    ),
                }));
                return;
            }

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
                    let event;
                    try { event = JSON.parse(line.slice(6)); } catch { continue; }

                    switch (event.type) {
                        case 'conversation_id':
                            setChat(prev => ({
                                ...prev,
                                list: prev.list.map(s => {
                                    if (s.tabId !== sessionTabId) return s;
                                    const patch = { conversationId: event.conversation_id };
                                    // Auto-title from first user message on new session
                                    if (s.title === 'New Chat') {
                                        patch.title = text.length > 35 ? text.slice(0, 35) + '…' : text;
                                    }
                                    return { ...s, ...patch };
                                }),
                            }));
                            break;

                        case 'text':
                            assistantContent = event.content;
                            setChat(prev => ({
                                ...prev,
                                list: prev.list.map(s => {
                                    if (s.tabId !== sessionTabId) return s;
                                    const msgs = [...s.messages];
                                    const last = msgs.length - 1;
                                    if (last >= 0 && msgs[last].role === 'assistant') {
                                        msgs[last] = { role: 'assistant', content: assistantContent };
                                    } else {
                                        msgs.push({ role: 'assistant', content: assistantContent });
                                    }
                                    return { ...s, messages: msgs };
                                }),
                            }));
                            break;

                        case 'error':
                            setChat(prev => ({
                                ...prev,
                                list: prev.list.map(s =>
                                    s.tabId !== sessionTabId ? s : {
                                        ...s,
                                        messages: [...s.messages, {
                                            role: 'assistant',
                                            content: 'Something went wrong with the AI service. Please try again in a moment.',
                                            isError: true,
                                        }],
                                    }
                                ),
                            }));
                            break;

                        default: break;
                    }
                }
            }
        } catch (err) {
            setChat(prev => ({
                ...prev,
                list: prev.list.map(s =>
                    s.tabId !== sessionTabId ? s : {
                        ...s,
                        messages: [...s.messages, {
                            role: 'assistant',
                            content: `Connection error: ${err.message}`,
                            isError: true,
                        }],
                    }
                ),
            }));
        } finally {
            setIsStreaming(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const messages = activeSession?.messages || [];

    return (
        <>
            {!isOpen && (
                <button className="chat-fab" onClick={() => setIsOpen(true)} title="AI Stock Analyst">
                    ✨
                </button>
            )}

            <div
                className={`chat-drawer ${isOpen ? 'open' : ''}`}
                style={isOpen ? { width: drawerWidth } : undefined}
            >
                <div className="chat-resize-handle" onMouseDown={handleResizeStart} />

                {/* Header */}
                <div className="chat-header">
                    <div className="chat-header-left">
                        <span className="chat-header-icon">✨</span>
                        <span className="chat-header-title">Stock Matrix AI</span>
                    </div>
                    <div className="chat-header-right">
                        <button className="chat-new-btn" onClick={createNewSession} title="New chat">+</button>
                        <button className="chat-close-btn" onClick={() => setIsOpen(false)} title="Close">✕</button>
                    </div>
                </div>

                {/* Tab Bar */}
                <div className="chat-tab-bar" ref={tabBarRef}>
                    {sessionList.map(s => (
                        <div
                            key={s.tabId}
                            className={`chat-tab${s.tabId === activeTabId ? ' active' : ''}`}
                            onClick={() => switchSession(s.tabId)}
                        >
                            {editingTabId === s.tabId ? (
                                <input
                                    ref={editInputRef}
                                    className="chat-tab-edit"
                                    value={editingTitle}
                                    onChange={e => setEditingTitle(e.target.value)}
                                    onBlur={commitRename}
                                    onKeyDown={e => {
                                        if (e.key === 'Enter') { e.preventDefault(); commitRename(); }
                                        if (e.key === 'Escape') { setEditingTabId(null); setEditingTitle(''); }
                                    }}
                                    onClick={e => e.stopPropagation()}
                                    maxLength={60}
                                />
                            ) : (
                                <span
                                    className="chat-tab-title"
                                    onDoubleClick={e => { e.stopPropagation(); startRename(s.tabId, s.title); }}
                                    title={`${s.title} (double-click to rename)`}
                                >
                                    {s.title}
                                </span>
                            )}
                            <button
                                className="chat-tab-close"
                                onClick={e => { e.stopPropagation(); closeSession(s.tabId); }}
                                title="Close"
                            >×</button>
                        </div>
                    ))}
                </div>

                {/* Messages */}
                <div className="chat-messages">
                    {messages.length === 0 && (
                        <div className="chat-welcome">
                            <div className="chat-welcome-icon">✨</div>
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
                                        onClick={() => { setInput(q); setTimeout(() => inputRef.current?.focus(), 0); }}
                                    >
                                        {q}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {messages.map((msg, i) => (
                        <div
                            key={i}
                            className={`chat-message ${msg.role}${msg.isError ? ' error' : ''}${msg.isQuota ? ' quota' : ''}`}
                        >
                            {msg.role === 'assistant' ? (
                                <div className="chat-message-content">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                                </div>
                            ) : (
                                <div className="chat-message-content">{msg.content}</div>
                            )}
                            {msg.isQuota && msg.canRegister && (
                                <button className="chat-register-cta" onClick={() => openAuthModal('register')}>
                                    Register Free →
                                </button>
                            )}
                        </div>
                    ))}

                    {isStreaming && (
                        <div className="chat-thinking-bar">
                            <div className="chat-thinking-dots">
                                <span /><span /><span />
                            </div>
                            <span className="chat-thinking-text">Stock Matrix AI is working on that...</span>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>

                {/* Input */}
                <div className="chat-input-area">
                    <textarea
                        ref={inputRef}
                        className="chat-input"
                        value={input}
                        onChange={e => setInput(e.target.value)}
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
                        ↑
                    </button>
                </div>
            </div>
        </>
    );
}

export default ChatPanel;
