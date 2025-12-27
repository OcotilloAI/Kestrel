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
    const [showSidebar, setShowSidebar] = useState(false);

    // Data Hooks
    const { sessions, activeSessionId, setActiveSessionId, createSession, deleteBranch, deleteBranchByName, deleteProject, createBranch, openBranchSession, branchListByProject, fetchBranches, isLoading: sessionsLoading, hasLoaded: sessionsLoaded, projects, projectsLoaded } = useSessions();
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

    // Keep active session in sync after create/delete without forcing full re-init
    useEffect(() => {
        if (sessionsLoading || !sessionsLoaded || !projectsLoaded || !isAuthenticated) return;
        if (activeSessionId && !sessions.some(s => s.id === activeSessionId)) {
            setActiveSessionId(null);
            return;
        }
        if (!activeSessionId && sessions.length > 0) {
            setActiveSessionId(sessions[0].id);
        }
    }, [sessions, activeSessionId, sessionsLoading, sessionsLoaded, projectsLoaded, isAuthenticated, setActiveSessionId]);

    useEffect(() => {
        if (activeSessionId && sessions.some(s => s.id === activeSessionId)) {
            localStorage.setItem('kestrel_active_session', activeSessionId);
            const session = sessions.find(s => s.id === activeSessionId);
            if (session?.cwd) {
                localStorage.setItem('kestrel_active_session_cwd', session.cwd);
            }
        } else if (!activeSessionId) {
            localStorage.removeItem('kestrel_active_session');
            localStorage.removeItem('kestrel_active_session_cwd');
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
        <div className="d-flex app-root overflow-hidden mobile-layout">
            <div className="mobile-topbar">
                <Button
                    variant="light"
                    className="mobile-menu-btn"
                    onClick={() => setShowSidebar(prev => !prev)}
                    aria-label="Toggle sidebar"
                >
                    <FaBars />
                </Button>
                <div className="mobile-title">Kestrel</div>
            </div>
            <Sidebar 
                isOffcanvas
                show={showSidebar}
                onHide={() => setShowSidebar(false)}
                sessions={sessions}
                activeSessionId={activeSessionId}
                projectNames={projects}
                onSelectSession={(id) => { setActiveSessionId(id); setShowSidebar(false); }}
                onCreateSession={(cwd) => { createSession(cwd).then(id => { if (id) setActiveSessionId(id); }); setShowSidebar(false); }}
                onDeleteBranch={deleteBranch}
                onDeleteBranchByName={deleteBranchByName}
                onDeleteProject={deleteProject}
                onCreateBranch={createBranch}
                onOpenBranch={openBranchSession}
                branchListByProject={branchListByProject}
                fetchBranches={fetchBranches}
            />

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
