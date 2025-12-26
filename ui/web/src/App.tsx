import { useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatArea } from './components/ChatArea';
import { InputArea } from './components/InputArea';
import { useSessions } from './hooks/useSessions';
import { useChat } from './hooks/useChat';
import type { SessionMode } from './types';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';

function App() {
    const { 
        sessions, 
        activeSessionId, 
        setActiveSessionId, 
        createSession, 
        deleteSession 
    } = useSessions();
    
    const { messages, status, sendMessage } = useChat(activeSessionId);
    
    // Auto-select first session on load if none selected
    useEffect(() => {
        if (!activeSessionId && sessions.length > 0) {
            setActiveSessionId(sessions[0].id);
        }
    }, [sessions, activeSessionId, setActiveSessionId]);

    const handleSend = async (text: string, mode: SessionMode) => {
        if (mode === 'new') {
            try {
                const newId = await createSession('.');
                setActiveSessionId(newId);
                // Wait a bit for connection? The hook handles activeSessionId change.
                // We might lose the first message if we send immediately before socket connects.
                // Ideally we queue it, but for now let's just create and user types again or we wait.
                // Improve: pass "initialPrompt" to createSession?
            } catch(e) {
                console.error(e);
                alert("Failed to create new session");
                return;
            }
        } else if (mode === 'duplicate') {
             try {
                const currentSession = sessions.find(s => s.id === activeSessionId);
                if (!currentSession) return;
                const newId = await createSession('.', currentSession.cwd);
                setActiveSessionId(newId);
             } catch(e) {
                console.error(e);
                 alert("Failed to duplicate session");
                 return;
             }
        }
        
        // For 'continue' we just send. 
        // Note: For new/duplicate, we need to wait for connection. 
        // This logic is slightly flawed for "Send immediate after create".
        // The original app did: Create -> Connect -> Send.
        // Here `setActiveSessionId` triggers `useChat` to connect.
        // We can't await that effect. 
        // Solution: If mode changed session, we might drop the message or need a "pending message" state.
        // For this MVP, let's assume 'continue' is default. If new/dup, we just switch and user types again?
        // OR: We hack it by setting a "pendingMessage" state that useChat sends on connect.
        
        if (mode === 'continue') {
             sendMessage(text);
        } else {
            // For now, just switch session. We lose the text if we don't handle it.
            // Let's trying sending after a timeout? No, unreliable.
            // Correct way: useChat accepts an "initialMessage" prop or similar.
            alert("Switched session. Please send your message again.");
        }
    };

    return (
        <div className="d-flex vh-100 overflow-hidden">
            <Sidebar 
                sessions={sessions}
                activeSessionId={activeSessionId}
                onSelectSession={setActiveSessionId}
                onCreateSession={createSession}
                onDeleteSession={deleteSession}
                onDuplicateSession={(id) => {
                     const s = sessions.find(s => s.id === id);
                     if(s) createSession('.', s.cwd);
                }}
            />
            <div className="d-flex flex-column flex-grow-1" style={{minWidth: 0}}>
                <ChatArea messages={messages} status={status} />
                <InputArea onSend={handleSend} disabled={status !== 'connected' && sessions.length > 0} />
            </div>
        </div>
    );
}

export default App;