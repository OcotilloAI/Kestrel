import { useEffect, useRef, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatArea } from './components/ChatArea';
import { InputArea } from './components/InputArea';
import { Login } from './components/Login';
import { useSessions } from './hooks/useSessions';
import { useChat } from './hooks/useChat';
import { Button } from 'react-bootstrap';
import { FaBars } from 'react-icons/fa';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';

function App() {
    // Auth State
    const [isAuthenticated, setIsAuthenticated] = useState(() => localStorage.getItem('kestrel_auth') === 'true');
    
    // UI State
    const [showMobileSidebar, setShowMobileSidebar] = useState(false);
    const [isDesktopSidebarCollapsed, setIsDesktopSidebarCollapsed] = useState(false);
    const [isDesktop] = useState(() => window.matchMedia('(min-width: 768px)').matches);

    // Data Hooks
    const { sessions, activeSessionId, setActiveSessionId, createSession, deleteBranch, deleteProject, createBranch, isLoading: sessionsLoading, hasLoaded: sessionsLoaded, projects, projectsLoaded } = useSessions();
    const { messages, status, sendMessage, isProcessing, stopSpeaking, speakText } = useChat(
        isAuthenticated ? activeSessionId : null,
        () => setActiveSessionId(null)
    );

    const activeSession = sessions.find(s => s.id === activeSessionId);

    const didInitRef = useRef(false);

    // Session Persistence and Initialization Logic
    useEffect(() => {
        if (sessionsLoading || !sessionsLoaded || !projectsLoaded || !isAuthenticated) return;
        if (activeSessionId && !sessions.some(s => s.id === activeSessionId)) {
            localStorage.removeItem('kestrel_active_session');
            setActiveSessionId(null);
            didInitRef.current = false;
            return;
        }
        if (didInitRef.current) return;
        const lastActiveId = localStorage.getItem('kestrel_active_session');
        const lastActiveCwd = localStorage.getItem('kestrel_active_session_cwd');
        if (lastActiveId && sessions.some(s => s.id === lastActiveId)) {
            if (activeSessionId !== lastActiveId) setActiveSessionId(lastActiveId);
        } else if (sessions.length > 0 && !activeSessionId) {
            if (lastActiveCwd) {
                const matching = sessions.find(s => s.cwd === lastActiveCwd);
                if (matching) {
                    setActiveSessionId(matching.id);
                } else {
                    setActiveSessionId(sessions[0].id);
                }
            } else {
                setActiveSessionId(sessions[0].id);
            }
        } else if (sessions.length === 0 && !activeSessionId && lastActiveCwd) {
            createSession(lastActiveCwd).then(id => { if (id) setActiveSessionId(id); }).catch(() => {
                localStorage.removeItem('kestrel_active_session_cwd');
            });
        } else if (sessions.length === 0 && !activeSessionId && projects.length === 0) {
            createSession('.').then(id => { if (id) setActiveSessionId(id); }).catch(console.error);
        }
        didInitRef.current = true;
    }, [sessions, activeSessionId, setActiveSessionId, sessionsLoading, sessionsLoaded, projectsLoaded, createSession, isAuthenticated, projects]);

    useEffect(() => {
        if (activeSessionId && sessions.some(s => s.id === activeSessionId)) {
            localStorage.setItem('kestrel_active_session', activeSessionId);
            const session = sessions.find(s => s.id === activeSessionId);
            if (session?.cwd) {
                localStorage.setItem('kestrel_active_session_cwd', session.cwd);
            }
        }
    }, [activeSessionId, sessions]);

    useEffect(() => {
        const updateAppHeight = () => {
            document.documentElement.style.setProperty('--app-height', `${window.innerHeight}px`);
        };
        updateAppHeight();
        window.addEventListener('resize', updateAppHeight);
        return () => window.removeEventListener('resize', updateAppHeight);
    }, []);

    // Handlers
    const handleLogin = () => {
        setIsAuthenticated(true);
        localStorage.setItem('kestrel_auth', 'true');
    };

    if (!isAuthenticated) {
        return <Login onLogin={handleLogin} />;
    }

    return (
        <div className={`d-flex app-root overflow-hidden ${isDesktop ? '' : 'mobile-layout'}`}>
            {isDesktop ? (
                <Sidebar 
                    isCollapsed={isDesktopSidebarCollapsed}
                    onToggleCollapse={() => setIsDesktopSidebarCollapsed(prev => !prev)}
                    sessions={sessions}
                    activeSessionId={activeSessionId}
                    onSelectSession={setActiveSessionId}
                    onCreateSession={createSession}
                    onDeleteBranch={deleteBranch}
                    onDeleteProject={deleteProject}
                    onCreateBranch={createBranch}
                    onDuplicateSession={(id) => {
                        const s = sessions.find(s => s.id === id);
                        if(s) createSession(undefined, s.cwd);
                    }}
                />
            ) : (
                <>
                    <div className="mobile-topbar">
                        <Button
                            variant="light"
                            className="mobile-menu-btn"
                            onClick={() => setShowMobileSidebar(prev => !prev)}
                            aria-label="Toggle sidebar"
                        >
                            <FaBars />
                        </Button>
                        <div className="mobile-title">Kestrel</div>
                    </div>
                    <Sidebar 
                        isOffcanvas
                        show={showMobileSidebar}
                        onHide={() => setShowMobileSidebar(false)}
                        sessions={sessions}
                        activeSessionId={activeSessionId}
                        onSelectSession={(id) => { setActiveSessionId(id); setShowMobileSidebar(false); }}
                        onCreateSession={(cwd) => { createSession(cwd); setShowMobileSidebar(false); }}
                        onDeleteBranch={deleteBranch}
                        onDeleteProject={deleteProject}
                        onCreateBranch={createBranch}
                        onDuplicateSession={(id) => {
                            const s = sessions.find(s => s.id === id);
                            if(s) createSession(undefined, s.cwd);
                            setShowMobileSidebar(false);
                        }}
                    />
                </>
            )}

            <div className="d-flex flex-column flex-grow-1 content-pane" style={{minWidth: 0}}>
                <ChatArea 
                    messages={messages} 
                    status={status} 
                    onSpeak={speakText} 
                    isProcessing={isProcessing}
                    sessionName={activeSession?.name}
                />
                <InputArea 
                    onSend={(text) => sendMessage(text)} 
                    onInteraction={stopSpeaking}
                    disabled={status !== 'connected'} 
                    isProcessing={isProcessing} 
                />
            </div>
        </div>
    );
}

export default App;
