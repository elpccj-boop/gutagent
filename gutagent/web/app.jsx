const { useState, useEffect, useRef, useCallback } = React;

// Generate a session ID
const SESSION_ID = localStorage.getItem('gutagent_session') || 
    (() => {
        const id = 'session_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('gutagent_session', id);
        return id;
    })();

// Parse markdown safely
function renderMarkdown(text) {
    if (!text) return '';
    try {
        return marked.parse(text, { breaks: true, gfm: true });
    } catch (e) {
        return text;
    }
}

// Message bubble component
function MessageBubble({ message }) {
    const isUser = message.role === 'user';
    const isError = message.role === 'error';
    
    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 ${
                isUser 
                    ? 'bg-gut-600 text-white rounded-br-md' 
                    : isError
                        ? 'bg-red-100 text-red-800 rounded-bl-md'
                        : 'bg-white text-gray-800 shadow-sm border border-gray-100 rounded-bl-md'
            }`}>
                {message.tools && message.tools.length > 0 && (
                    <div className="tool-call mb-2 pb-2 border-b border-gray-200">
                        {message.tools.map((tool, i) => (
                            <div key={i} className="text-gut-700">
                                🔧 {tool.name}
                            </div>
                        ))}
                    </div>
                )}
                <div 
                    className="markdown-content"
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
                />
            </div>
        </div>
    );
}

// Typing indicator
function TypingIndicator() {
    return (
        <div className="flex justify-start mb-3">
            <div className="bg-white rounded-2xl rounded-bl-md px-4 py-3 shadow-sm border border-gray-100">
                <div className="flex space-x-1.5">
                    <div className="w-2 h-2 bg-gut-400 rounded-full typing-dot"></div>
                    <div className="w-2 h-2 bg-gut-400 rounded-full typing-dot"></div>
                    <div className="w-2 h-2 bg-gut-400 rounded-full typing-dot"></div>
                </div>
            </div>
        </div>
    );
}

// Settings panel
function SettingsPanel({ isOpen, onClose, settings, onSettingsChange }) {
    if (!isOpen) return null;
    
    return (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center"
             onClick={onClose}>
            <div className="bg-white w-full sm:w-96 sm:rounded-2xl rounded-t-2xl p-5 safe-bottom"
                 onClick={e => e.stopPropagation()}>
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-lg font-semibold text-gray-800">Settings</h2>
                    <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-full">
                        <svg className="w-6 h-6 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
                
                <div className="space-y-4">
                    {/* Model selection */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">Model</label>
                        <div className="flex rounded-lg overflow-hidden border border-gray-200">
                            <button
                                className={`flex-1 py-2.5 text-sm font-medium transition ${
                                    settings.model === 'smart' 
                                        ? 'bg-gut-600 text-white' 
                                        : 'bg-white text-gray-600 hover:bg-gray-50'
                                }`}
                                onClick={() => onSettingsChange({ ...settings, model: 'smart' })}
                            >
                                Smart
                                <span className="block text-xs opacity-75">Better</span>
                            </button>
                            <button
                                className={`flex-1 py-2.5 text-sm font-medium transition ${
                                    settings.model === 'default' 
                                        ? 'bg-gut-600 text-white' 
                                        : 'bg-white text-gray-600 hover:bg-gray-50'
                                }`}
                                onClick={() => onSettingsChange({ ...settings, model: 'default' })}
                            >
                                Default
                                <span className="block text-xs opacity-75">Faster</span>
                            </button>
                        </div>
                    </div>
                    
                    {/* Show tools toggle */}
                    <div className="flex items-center justify-between">
                        <div>
                            <label className="text-sm font-medium text-gray-700">Show tool calls</label>
                            <p className="text-xs text-gray-500">See when Claude uses tools</p>
                        </div>
                        <button
                            className={`relative w-12 h-7 rounded-full transition ${
                                settings.showTools ? 'bg-gut-600' : 'bg-gray-200'
                            }`}
                            onClick={() => onSettingsChange({ ...settings, showTools: !settings.showTools })}
                        >
                            <div className={`absolute top-1 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                                settings.showTools ? 'translate-x-6' : 'translate-x-1'
                            }`} />
                        </button>
                    </div>
                </div>
                
                {/* Clear conversation */}
                <button
                    onClick={async () => {
                        await fetch('/api/clear', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ session_id: SESSION_ID }),
                        });
                        localStorage.removeItem('gutagent_messages');
                        window.location.reload();
                    }}
                    className="mt-6 w-full py-2.5 text-red-600 border border-red-200 rounded-lg 
                             hover:bg-red-50 transition text-sm font-medium"
                >
                    Clear Conversation
                </button>
            </div>
        </div>
    );
}

// Quick action buttons
function QuickActions({ onAction, disabled }) {
    const actions = [
        { emoji: '🍽️', label: 'Meal', prompt: 'I just had ' },
        { emoji: '🤒', label: 'Symptom', prompt: "I'm feeling " },
        { emoji: '❤️', label: 'Vitals', prompt: 'My BP is ' },
        { emoji: '😴', label: 'Sleep', prompt: 'I slept about ' },
        { emoji: '🏃', label: 'Exercise', prompt: 'I did ' },
        { emoji: '💊', label: 'Medication', prompt: 'I took ' },
        { emoji: '📝', label: 'Journal', prompt: 'Note: ' },
        { emoji: '🍲', label: 'Recipe', prompt: 'Save recipe for ' },
    ];
    
    return (
        <div className="flex flex-wrap justify-center gap-2 px-4 py-2">
            {actions.map(action => (
                <button
                    key={action.label}
                    disabled={disabled}
                    onClick={() => onAction(action.prompt)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 
                             rounded-full text-sm text-gray-600 hover:border-gut-300 hover:bg-gut-50 
                             transition disabled:opacity-50"
                >
                    <span>{action.emoji}</span>
                    <span>{action.label}</span>
                </button>
            ))}
        </div>
    );
}

// Main App
function App() {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [settings, setSettings] = useState(() => {
        const saved = localStorage.getItem('gutagent_settings');
        return saved ? JSON.parse(saved) : { model: 'default', showTools: false };
    });
    
    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);
    
    // Save settings
    useEffect(() => {
        localStorage.setItem('gutagent_settings', JSON.stringify(settings));
    }, [settings]);
    
    // Scroll to bottom on new messages
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);
    
    // Autofocus input on load and after sending
    useEffect(() => {
        inputRef.current?.focus();
    }, []);

    // Check auth on mount — this triggers browser login prompt if needed
    useEffect(() => {
        fetch('/api/profile', { credentials: 'include' })
            .then(res => {
                if (res.status === 401) {
                    // This shouldn't normally happen since browser will show login
                    // But just in case, show an error
                    setMessages([{ role: 'error', content: 'Authentication required. Please refresh and log in.' }]);
                }
            })
            .catch(() => {});
    }, []);

    // Load stored messages on mount
    useEffect(() => {
        const stored = localStorage.getItem('gutagent_messages');
        if (stored) {
            try {
                setMessages(JSON.parse(stored));
            } catch (e) {}
        }
    }, []);
    
    // Save messages when they change
    useEffect(() => {
        if (messages.length > 0) {
            // Keep last 50 messages in localStorage
            const toStore = messages.slice(-50);
            localStorage.setItem('gutagent_messages', JSON.stringify(toStore));
        }
    }, [messages]);
    
    const sendMessage = useCallback(async (messageText) => {
        const text = (messageText || input).trim();
        if (!text || isLoading) return;
        
        setInput('');
        setIsLoading(true);
        
        // Add user message
        const userMessage = { role: 'user', content: text };
        setMessages(prev => [...prev, userMessage]);
        
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    message: text,
                    session_id: SESSION_ID,
                    model: settings.model,
                    show_tools: settings.showTools,
                }),
            });
            
            if (response.status === 401) {
                // Auth required — reload to trigger browser login prompt
                window.location.reload();
                return;
            }

            if (!response.ok) throw new Error('Network error');
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            let assistantContent = '';
            let tools = [];
            
            // Add placeholder for assistant message
            setMessages(prev => [...prev, { role: 'assistant', content: '', tools: [] }]);
            
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.type === 'text') {
                            assistantContent += data.content;
                            setMessages(prev => {
                                const updated = [...prev];
                                updated[updated.length - 1] = {
                                    role: 'assistant',
                                    content: assistantContent,
                                    tools: tools,
                                };
                                return updated;
                            });
                        } else if (data.type === 'tool_call' && settings.showTools) {
                            tools.push({ name: data.name });
                            setMessages(prev => {
                                const updated = [...prev];
                                updated[updated.length - 1] = {
                                    role: 'assistant',
                                    content: assistantContent,
                                    tools: [...tools],
                                };
                                return updated;
                            });
                        } else if (data.type === 'error') {
                            throw new Error(data.message);
                        }
                    } catch (e) {
                        if (e.message !== 'Unexpected end of JSON input') {
                            console.error('Parse error:', e);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Chat error:', error);
            setMessages(prev => [...prev, { 
                role: 'error', 
                content: `Error: ${error.message}. Please try again.` 
            }]);
        } finally {
            setIsLoading(false);
            inputRef.current?.focus();
        }
    }, [input, isLoading, settings]);
    
    const handleSubmit = (e) => {
        e.preventDefault();
        sendMessage();
    };
    
    const handleQuickAction = (prompt) => {
        setInput(prompt);
        inputRef.current?.focus();
    };
    
    return (
        <div className="flex flex-col h-screen bg-gray-50">
            {/* Header */}
            <header className="bg-gut-700 text-white px-4 py-3 flex items-center justify-between safe-top shadow-md">
                <div className="flex items-center gap-2">
                    <span className="text-2xl">🥗</span>
                    <div>
                        <h1 className="font-semibold text-lg leading-tight">GutAgent</h1>
                        <p className="text-xs text-gut-200">
                            {settings.model === 'smart' ? 'Smart' : 'Default'}
                        </p>
                    </div>
                </div>
                <button 
                    onClick={() => setSettingsOpen(true)}
                    className="p-2 hover:bg-gut-600 rounded-full transition"
                >
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                              d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                </button>
            </header>
            
            {/* Messages */}
            <main className="flex-1 overflow-y-auto px-4 py-4 hide-scrollbar">
                {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center px-6">
                        <span className="text-6xl mb-4">🥗</span>
                        <h2 className="text-xl font-semibold text-gray-700 mb-2">Welcome to GutAgent</h2>
                        <p className="text-gray-500 text-sm max-w-xs">
                            Tell me what you ate, how you're feeling, or ask for meal suggestions.
                        </p>
                    </div>
                ) : (
                    <>
                        {messages.map((msg, i) => (
                            <MessageBubble key={i} message={msg} />
                        ))}
                        {isLoading && messages[messages.length - 1]?.role === 'user' && (
                            <TypingIndicator />
                        )}
                    </>
                )}
                <div ref={messagesEndRef} />
            </main>
            
            {/* Quick actions */}
            {messages.length === 0 && (
                <QuickActions onAction={handleQuickAction} disabled={isLoading} />
            )}
            
            {/* Input */}
            <div className="border-t border-gray-200 bg-white safe-bottom">
                <form onSubmit={handleSubmit} className="flex items-end gap-2 p-3">
                    <div className="flex-1 relative">
                        <textarea
                            ref={inputRef}
                            value={input}
                            onChange={(e) => {
                                setInput(e.target.value);
                                // Auto-resize
                                e.target.style.height = 'auto';
                                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
                            }}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault();
                                    sendMessage();
                                }
                            }}
                            placeholder="Message GutAgent..."
                            disabled={isLoading}
                            rows={1}
                            className="w-full px-4 py-2.5 bg-gray-100 rounded-2xl resize-none 
                                     focus:outline-none focus:ring-2 focus:ring-gut-500 focus:bg-white
                                     disabled:opacity-50 transition"
                            style={{ maxHeight: '120px' }}
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={!input.trim() || isLoading}
                        className="p-2.5 bg-gut-600 text-white rounded-full hover:bg-gut-700 
                                 disabled:opacity-50 disabled:hover:bg-gut-600 transition
                                 flex-shrink-0"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                        </svg>
                    </button>
                </form>
            </div>
            
            {/* Settings panel */}
            <SettingsPanel 
                isOpen={settingsOpen}
                onClose={() => setSettingsOpen(false)}
                settings={settings}
                onSettingsChange={setSettings}
            />
        </div>
    );
}

// Render
ReactDOM.createRoot(document.getElementById('root')).render(<App />);
