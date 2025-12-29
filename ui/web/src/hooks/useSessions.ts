import { useState, useEffect, useCallback } from 'react';
import type { Session } from '../types';

export const useSessions = () => {
    const [sessions, setSessions] = useState<Session[]>([]);
    const [activeSessionId, setActiveSessionId] = useState<string | null>(
        () => localStorage.getItem('kestrel_active_session')
    );
    const [isLoading, setIsLoading] = useState(false);
    const [hasLoaded, setHasLoaded] = useState(false);
    const [projects, setProjects] = useState<string[]>([]);
    const [branchListByProject, setBranchListByProject] = useState<Record<string, string[]>>({});
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
            await fetchSessions();
            await fetchProjects();
            return newSession;
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
            await fetchBranches(projectBranch.project);
            if (activeSessionId === sessionId) {
                setActiveSessionId(null);
            }
        } catch (err: any) {
            setError(err.message);
        }
    };

    const deleteBranchByName = async (projectName: string, branchName: string) => {
        try {
            const res = await fetch(
                `/project/${encodeURIComponent(projectName)}/branch/${encodeURIComponent(branchName)}`,
                { method: 'DELETE' }
            );
            if (!res.ok) throw new Error('Failed to delete branch');
            await fetchSessions();
            await fetchProjects();
            await fetchBranches(projectName);
            if (activeSessionId) {
                const activeSession = sessions.find(s => s.id === activeSessionId);
                if (activeSession?.name === `${projectName}/${branchName}`) {
                    setActiveSessionId(null);
                }
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

    const createBranch = async (projectName: string, branchName?: string, sourceBranch?: string) => {
        try {
            const res = await fetch(`/project/${encodeURIComponent(projectName)}/branch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: branchName || null, source_branch: sourceBranch || 'main' }),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to create branch');
            }
            const data = await res.json();
            await fetchSessions();
            await fetchProjects();
            await fetchBranches(projectName);
            return data?.branch as string | undefined;
        } catch (err: any) {
            setError(err.message);
            throw err;
        }
    };

    const mergeBranch = async (projectName: string, branchName: string) => {
        try {
            const res = await fetch(`/project/${encodeURIComponent(projectName)}/branch/${encodeURIComponent(branchName)}/merge`, {
                method: 'POST',
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to merge branch');
            }
            await fetchSessions();
            await fetchBranches(projectName);
        } catch (err: any) {
            setError(err.message);
            throw err;
        }
    };

    const syncBranch = async (projectName: string, branchName: string) => {
        try {
            const res = await fetch(`/project/${encodeURIComponent(projectName)}/branch/${encodeURIComponent(branchName)}/sync`, {
                method: 'POST',
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to sync branch');
            }
            await fetchSessions();
            await fetchBranches(projectName);
        } catch (err: any) {
            setError(err.message);
            throw err;
        }
    };

    const fetchBranches = useCallback(async (projectName: string) => {
        try {
            const res = await fetch(`/project/${encodeURIComponent(projectName)}/branches`);
            if (!res.ok) throw new Error('Failed to fetch branches');
            const data = await res.json();
            setBranchListByProject(prev => ({ ...prev, [projectName]: data }));
        } catch (err: any) {
            setError(err.message);
        }
    }, []);

    const openBranchSession = async (projectName: string, branchName: string) => {
        try {
            const res = await fetch(`/project/${encodeURIComponent(projectName)}/branch/${encodeURIComponent(branchName)}/session`, {
                method: 'POST',
            });
            if (!res.ok) throw new Error('Failed to open branch session');
            const data = await res.json();
            if (data?.session_id) {
                setSessions(prev => {
                    if (prev.some(session => session.id === data.session_id)) return prev;
                    return [
                        ...prev,
                        {
                            id: data.session_id,
                            name: `${projectName}/${branchName}`,
                            cwd: data.cwd || ''
                        }
                    ];
                });
                setActiveSessionId(data.session_id);
            }
            await fetchSessions();
        } catch (err: any) {
            setError(err.message);
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
        deleteBranchByName,
        deleteProject,
        createBranch,
        openBranchSession,
        mergeBranch,
        syncBranch,
        fetchSessions,
        isLoading,
        hasLoaded,
        projects,
        projectsLoaded,
        branchListByProject,
        fetchBranches,
        error
    };
};
