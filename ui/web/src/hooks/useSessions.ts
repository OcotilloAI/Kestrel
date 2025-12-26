import { useState, useEffect, useCallback } from 'react';
import type { Session } from '../types';

export const useSessions = () => {
    const [sessions, setSessions] = useState<Session[]>([]);
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [hasLoaded, setHasLoaded] = useState(false);
    const [projects, setProjects] = useState<string[]>([]);
    const [projectsLoaded, setProjectsLoaded] = useState(false);
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
            setHasLoaded(true);
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

    const fetchProjects = useCallback(async () => {
        try {
            const res = await fetch('/projects');
            if (!res.ok) throw new Error('Failed to fetch projects');
            const data = await res.json();
            setProjects(data);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setProjectsLoaded(true);
        }
    }, []);

    const getProjectAndBranch = (session: Session) => {
        const nameParts = session.name.split('/');
        if (nameParts.length >= 2) {
            return { project: nameParts[0], branch: nameParts[1] };
        }
        if (session.cwd) {
            const cwdParts = session.cwd.replace(/\\/g, '/').split('/').filter(Boolean);
            if (cwdParts.length >= 2) {
                return { project: cwdParts[cwdParts.length - 2], branch: cwdParts[cwdParts.length - 1] };
            }
        }
        return null;
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

    const deleteBranch = async (sessionId: string) => {
        const session = sessions.find(s => s.id === sessionId);
        if (!session) {
            setError('Session not found');
            return;
        }
        const projectBranch = getProjectAndBranch(session);
        if (!projectBranch) {
            setError('Unable to determine project/branch');
            return;
        }
        try {
            const res = await fetch(
                `/project/${encodeURIComponent(projectBranch.project)}/branch/${encodeURIComponent(projectBranch.branch)}`,
                { method: 'DELETE' }
            );
            if (!res.ok) throw new Error('Failed to delete branch');
            await fetchSessions();
            await fetchProjects();
            if (activeSessionId === sessionId) {
                setActiveSessionId(null);
            }
        } catch (err: any) {
            setError(err.message);
        }
    };

    const deleteProject = async (projectName: string) => {
        try {
            const res = await fetch(`/project/${encodeURIComponent(projectName)}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Failed to delete project');
            const activeSession = sessions.find(s => s.id === activeSessionId);
            if (activeSession?.name.startsWith(`${projectName}/`)) {
                setActiveSessionId(null);
            }
            await fetchSessions();
            await fetchProjects();
        } catch (err: any) {
            setError(err.message);
        }
    };

    const createBranch = async (projectName: string, branchName?: string) => {
        try {
            const res = await fetch(`/project/${encodeURIComponent(projectName)}/branch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: branchName || null }),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to create branch');
            }
            await fetchSessions();
            await fetchProjects();
        } catch (err: any) {
            setError(err.message);
            throw err;
        }
    };

    useEffect(() => {
        fetchSessions();
        fetchProjects();
    }, [fetchSessions, fetchProjects]);

    return {
        sessions,
        activeSessionId,
        setActiveSessionId,
        createSession,
        deleteSession,
        deleteBranch,
        deleteProject,
        createBranch,
        fetchSessions,
        isLoading,
        hasLoaded,
        projects,
        projectsLoaded,
        error
    };
};
