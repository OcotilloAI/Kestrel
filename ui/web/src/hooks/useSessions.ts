import { useState, useEffect, useCallback } from 'react';
import type { Session } from '../types';

export const useSessions = () => {
    const [sessions, setSessions] = useState<Session[]>([]);
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchSessions = useCallback(async () => {
        setIsLoading(true);
        try {
            const res = await fetch('/sessions');
            if (!res.ok) throw new Error('Failed to fetch sessions');
            const data = await res.json();
            setSessions(data);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    }, []);

    const createSession = async (cwd: string = '.', copyFrom?: string) => {
        setIsLoading(true);
        try {
            const body: any = { cwd };
            if (copyFrom) body.copy_from_path = copyFrom;

            const res = await fetch('/session/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to create session');
            }
            
            const newSession = await res.json();
            // Backend returns { session_id, cwd, ... } map it to Session if needed
            // Assuming the backend returns the session object or similar
            // We might need to refresh the list or construct the object
            await fetchSessions();
            return newSession.session_id;
        } catch (err: any) {
            setError(err.message);
            throw err;
        } finally {
            setIsLoading(false);
        }
    };

    const deleteSession = async (sessionId: string) => {
         try {
            const res = await fetch(`/session/${sessionId}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Failed to delete session');
            await fetchSessions();
            if (activeSessionId === sessionId) {
                setActiveSessionId(null);
            }
        } catch (err: any) {
            setError(err.message);
        }
    };

    useEffect(() => {
        fetchSessions();
    }, [fetchSessions]);

    return {
        sessions,
        activeSessionId,
        setActiveSessionId,
        createSession,
        deleteSession,
        fetchSessions,
        isLoading,
        error
    };
};
