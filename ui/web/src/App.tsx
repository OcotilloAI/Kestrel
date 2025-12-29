import { useCallback, useEffect, useRef, useState } from 'react';
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
    const { sessions, activeSessionId, setActiveSessionId, createSession, deleteBranch, deleteBranchByName, deleteProject, createBranch, mergeBranch, syncBranch, openBranchSession, branchListByProject, fetchBranches, isLoading: sessionsLoading, hasLoaded: sessionsLoaded, projects, projectsLoaded } = useSessions();
    const hasValidSession = !!activeSessionId && sessions.some(s => s.id === activeSessionId);
    const effectiveSessionId =
        isAuthenticated && sessionsLoaded && projectsLoaded && hasValidSession ? activeSessionId : null;
    const { messages, status, sendMessage, isProcessing, stopSpeaking, speakText, audioUnlocked, unlockAudio } = useChat(
        effectiveSessionId,
        () => setActiveSessionId(null)
    );

    const activeSession = sessions.find(s => s.id === activeSessionId);
    const activeBranchName = activeSession?.name.split('/')[1];
    const isMainBranch = activeBranchName === 'main';

    const didInitRef = useRef(false);

    const getProjectNameFromCwd = (cwd?: string | null) => {
        if (!cwd) return null;
        const normalized = cwd.replace(/\\/g, '/');
        const parts = normalized.split('/').filter(Boolean);
        const workspaceIndex = parts.lastIndexOf('workspace');
        if (workspaceIndex >= 0 && parts.length > workspaceIndex + 1) {
            return parts[workspaceIndex + 1];
        }
        if (parts.length >= 2) {
            return parts[parts.length - 2];
        }
        return null;
    };

    const handleCreateSession = useCallback(async (cwd?: string) => {
        const result = await createSession(cwd);
        if (!result?.session_id) return;
        const isNewProject = !cwd || cwd === '.';
        if (!isNewProject) {
            setActiveSessionId(result.session_id);
            return;
        }
        const projectName = getProjectNameFromCwd(result.cwd);
        if (!projectName) {
            setActiveSessionId(result.session_id);
            return;
        }
        try {
            const branchName = await createBranch(projectName);
            if (branchName) {
                await openBranchSession(projectName, branchName);
                return;
            }
        } catch (err) {
            console.error(err);
        }
        setActiveSessionId(result.session_id);
    }, [createSession, createBranch, openBranchSession, setActiveSessionId]);

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
        if (lastActiveId) {
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
            handleCreateSession(lastActiveCwd).catch(() => {
                localStorage.removeItem('kestrel_active_session_cwd');
            });
        } else if (sessions.length === 0 && !activeSessionId && projects.length > 0) {
            const projectRoot = `/workspace/${projects[0]}/main`;
            handleCreateSession(projectRoot).catch(console.error);
        } else if (sessions.length === 0 && !activeSessionId && projects.length === 0) {
            handleCreateSession('.').catch(console.error);
        }
        didInitRef.current = true;
    }, [sessions, activeSessionId, setActiveSessionId, sessionsLoading, sessionsLoaded, projectsLoaded, handleCreateSession, isAuthenticated, projects]);

    // Keep active session in sync after create/delete without forcing full re-init
    useEffect(() => {
        if (sessionsLoading || !sessionsLoaded || !projectsLoaded || !isAuthenticated) return;
        if (!didInitRef.current && !activeSessionId) return;
        if (activeSessionId && !sessions.some(s => s.id === activeSessionId)) {
            setActiveSessionId(null);
            return;
        }
        if (!activeSessionId && sessions.length > 0) {
            setActiveSessionId(sessions[0].id);
        }
    }, [sessions, activeSessionId, sessionsLoading, sessionsLoaded, projectsLoaded, isAuthenticated, setActiveSessionId]);

    useEffect(() => {
        if (!isAuthenticated || !didInitRef.current) return;
        if (activeSessionId) {
            localStorage.setItem('kestrel_active_session', activeSessionId);
            const session = sessions.find(s => s.id === activeSessionId);
            if (session?.cwd) {
                localStorage.setItem('kestrel_active_session_cwd', session.cwd);
            }
        } else {
            localStorage.removeItem('kestrel_active_session');
            localStorage.removeItem('kestrel_active_session_cwd');
        }
    }, [activeSessionId, sessions, isAuthenticated]);

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
                onCreateSession={(cwd) => { handleCreateSession(cwd).catch(console.error); setShowSidebar(false); }}
                onDeleteBranch={deleteBranch}
                onDeleteBranchByName={deleteBranchByName}
                onDeleteProject={deleteProject}
                onCreateBranch={createBranch}
                onMergeBranch={mergeBranch}
                onSyncBranch={syncBranch}
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
                    audioUnlocked={audioUnlocked}
                    onUnlockAudio={unlockAudio}
                    readOnlyMessage={isMainBranch ? 'Main is read-only' : undefined}
                />
                <InputArea 
                    onSend={(text) => sendMessage(text)} 
                    onInteraction={stopSpeaking}
                    disabled={status !== 'connected' || isMainBranch} 
                    isProcessing={isProcessing} 
                />
            </div>
        </div>
    );
}

export default App;
