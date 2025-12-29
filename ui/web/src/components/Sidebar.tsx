import React, { useEffect, useState } from 'react';
import type { Session } from '../types';
import { Button, ListGroup, Offcanvas, Form, Modal } from 'react-bootstrap';
import { FaTrash, FaFolderPlus } from 'react-icons/fa';
import '../App.css';

// ... (Props interface remains large for now, will simplify later if possible)
interface SidebarProps {
    sessions: Session[];
    activeSessionId: string | null;
    projectNames: string[];
    onSelectSession: (id: string) => void;
    onCreateSession: (cwd?: string, copyFrom?: string) => void;
    onDeleteBranch: (id: string) => void;
    onDeleteBranchByName: (projectName: string, branchName: string) => void;
    onDeleteProject: (projectName: string) => void;
    onCreateBranch: (projectName: string, branchName?: string, sourceBranch?: string) => Promise<string | undefined>;
    onMergeBranch: (projectName: string, branchName: string) => void;
    onSyncBranch: (projectName: string, branchName: string) => void;
    onOpenBranch: (projectName: string, branchName: string) => void;
    branchListByProject: Record<string, string[]>;
    fetchBranches: (projectName: string) => void;
    // Responsive props
    isOffcanvas?: boolean;
    show?: boolean;
    onHide?: () => void;
}


export const Sidebar: React.FC<SidebarProps> = (props) => {
    const { sessions, activeSessionId, projectNames, onSelectSession, onCreateSession, onDeleteBranch, onDeleteBranchByName, onDeleteProject, onCreateBranch, onMergeBranch, onSyncBranch, onOpenBranch, branchListByProject, fetchBranches } = props;
    const [newBranchName, setNewBranchName] = useState('');
    const [sourceBranch, setSourceBranch] = useState('main');
    const lastActiveProjectRef = React.useRef<string | undefined>();
    const [confirmState, setConfirmState] = useState<{
        type: 'branch' | 'project' | 'merge' | 'sync';
        projectName: string;
        branchName?: string;
        sessionId?: string;
    } | null>(null);

    const activeSession = sessions.find(s => s.id === activeSessionId);
    const activeProjectName = activeSession?.name.split('/')[0];
    const [currentProjectName, setCurrentProjectName] = useState(activeProjectName || projectNames[0] || '');
    const branchList = branchListByProject[currentProjectName] || [];

    useEffect(() => {
        const activeProjectValid = activeProjectName && projectNames.includes(activeProjectName);
        if (activeProjectValid) {
            if (!lastActiveProjectRef.current) {
                lastActiveProjectRef.current = activeProjectName;
            }
            if (activeProjectName !== lastActiveProjectRef.current) {
                const shouldSync =
                    !currentProjectName ||
                    currentProjectName === lastActiveProjectRef.current ||
                    !projectNames.includes(currentProjectName);
                if (shouldSync) {
                    setCurrentProjectName(activeProjectName);
                }
                lastActiveProjectRef.current = activeProjectName;
                return;
            }
        }
        if (!activeProjectValid && (!currentProjectName || !projectNames.includes(currentProjectName))) {
            setCurrentProjectName(projectNames[0] || '');
        }
    }, [activeProjectName, currentProjectName, projectNames]);

    useEffect(() => {
        if (currentProjectName) {
            fetchBranches(currentProjectName);
        }
    }, [currentProjectName, fetchBranches]);

    useEffect(() => {
        if (branchList.length > 0 && !branchList.includes(sourceBranch)) {
            setSourceBranch(branchList[0]);
        }
    }, [branchList, sourceBranch]);
    const handleDeleteProject = () => {
        if (!currentProjectName) return;
        setConfirmState({ type: 'project', projectName: currentProjectName });
    };

    const handleDeleteBranch = (sessionId: string, branchLabel: string) => {
        setConfirmState({
            type: 'branch',
            projectName: currentProjectName,
            branchName: branchLabel,
            sessionId
        });
    };

    const handleDeleteBranchByName = (branchLabel: string) => {
        setConfirmState({
            type: 'branch',
            projectName: currentProjectName,
            branchName: branchLabel
        });
    };

    const confirmDelete = () => {
        if (!confirmState) return;
        if (confirmState.type === 'project') {
            onDeleteProject(confirmState.projectName);
            setCurrentProjectName('');
        } else if (confirmState.type === 'branch' && confirmState.branchName) {
            if (confirmState.sessionId) {
                onDeleteBranch(confirmState.sessionId);
            } else {
                onDeleteBranchByName(confirmState.projectName, confirmState.branchName);
            }
        } else if (confirmState.type === 'merge' && confirmState.branchName) {
            onMergeBranch(confirmState.projectName, confirmState.branchName);
        } else if (confirmState.type === 'sync' && confirmState.branchName) {
            onSyncBranch(confirmState.projectName, confirmState.branchName);
        }
        setConfirmState(null);
    };

    const handleCreateBranch = async () => {
        if (!currentProjectName) return;
        const trimmed = newBranchName.trim();
        try {
            const createdBranch = await onCreateBranch(currentProjectName, trimmed || undefined, sourceBranch);
            setNewBranchName('');
            if (createdBranch) {
                await onOpenBranch(currentProjectName, createdBranch);
            }
        } catch (err) {
            console.error(err);
        }
    };

    const handleCreateBranchFromMain = async () => {
        if (!currentProjectName) return;
        const trimmed = newBranchName.trim();
        try {
            const createdBranch = await onCreateBranch(currentProjectName, trimmed || undefined, 'main');
            setNewBranchName('');
            if (createdBranch) {
                await onOpenBranch(currentProjectName, createdBranch);
            }
        } catch (err) {
            console.error(err);
        }
    };

    const content = (
        <div className="sidebar-container bg-light border-end">
            {/* Header */}
            <div className="sidebar-header p-3 border-bottom d-flex justify-content-between align-items-center">
                <h5 className="mb-0">Kestrel</h5>
            </div>

            {/* Content Area */}
            <div className="sidebar-content">
                {/* Project Selector & Actions */}
                <div className="p-3 border-bottom">
                    <Form.Label className="small text-muted text-uppercase fw-bold mt-2">Current Project</Form.Label>
                    <Form.Select
                        size="sm"
                        value={currentProjectName}
                        onChange={(e) => setCurrentProjectName(e.target.value)}
                        data-testid="project-select"
                    >
                        {projectNames.map(name => <option key={name} value={name}>{name}</option>)}
                    </Form.Select>
                </div>

                {/* Branch List */}
                <div className="flex-grow-1 overflow-auto p-3">
                    <div className="small text-muted text-uppercase fw-bold mb-2">Branches</div>
                    <div className="d-flex flex-column gap-2 mb-3">
                        <Form.Select
                            size="sm"
                            value={sourceBranch}
                            onChange={(e) => setSourceBranch(e.target.value)}
                            disabled={branchList.length === 0}
                            data-testid="branch-source-select"
                        >
                            {branchList.map(b => <option key={b} value={b}>{b}</option>)}
                        </Form.Select>
                        <Form.Control
                            size="sm"
                            placeholder="New branch name (optional)"
                            value={newBranchName}
                            onChange={(e) => setNewBranchName(e.target.value)}
                            disabled={projectNames.length === 0}
                            data-testid="branch-name-input"
                        />
                        <Button size="sm" variant="outline-primary" onClick={handleCreateBranch} disabled={projectNames.length === 0} data-testid="branch-create-button">
                            Create Branch
                        </Button>
                        <Button size="sm" variant="primary" onClick={handleCreateBranchFromMain} disabled={projectNames.length === 0} data-testid="branch-create-main-button">
                            New Branch from Main
                        </Button>
                    </div>
                    <ListGroup variant="flush" data-testid="branch-list">
                        {branchList.map(branchName => {
                            const session = sessions.find(s => s.name === `${currentProjectName}/${branchName}`);
                            const isActive = session?.id === activeSessionId;
                            const isProtected = branchName === 'main';
                            return (
                            <ListGroup.Item 
                                key={branchName} 
                                as="div"
                                role="button"
                                tabIndex={0}
                                action 
                                active={isActive}
                                data-testid={`branch-item-${branchName}`}
                                onClick={() => {
                                    if (session) {
                                        onSelectSession(session.id);
                                    } else {
                                        onOpenBranch(currentProjectName, branchName);
                                    }
                                }}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' || e.key === ' ') {
                                        e.preventDefault();
                                        if (session) {
                                            onSelectSession(session.id);
                                        } else {
                                            onOpenBranch(currentProjectName, branchName);
                                        }
                                    }
                                }}
                                className="d-flex justify-content-between align-items-center p-2 rounded mb-1 border-0"
                            >
                                <span className="text-truncate">{branchName}</span>
                                <div className="d-flex align-items-center gap-2">
                                    <Button
                                        variant="link"
                                        size="sm"
                                        className="p-0 text-secondary"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            if (isProtected) return;
                                            setConfirmState({
                                                type: 'sync',
                                                projectName: currentProjectName,
                                                branchName,
                                            });
                                        }}
                                        title="Sync from main"
                                        data-testid={`branch-sync-${branchName}`}
                                        disabled={isProtected}
                                    >
                                        Sync
                                    </Button>
                                    <Button
                                        variant="link"
                                        size="sm"
                                        className="p-0 text-primary"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            if (isProtected) return;
                                            setConfirmState({
                                                type: 'merge',
                                                projectName: currentProjectName,
                                                branchName,
                                            });
                                        }}
                                        title="Merge into main"
                                        data-testid={`branch-merge-${branchName}`}
                                        disabled={isProtected}
                                    >
                                        Merge
                                    </Button>
                                    <Button 
                                        variant="link" 
                                        size="sm" 
                                        className="p-0 text-danger" 
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            if (isProtected) return;
                                            if (session) {
                                                handleDeleteBranch(session.id, branchName);
                                            } else {
                                                handleDeleteBranchByName(branchName);
                                            }
                                        }}
                                        title="Delete Branch"
                                        data-testid={`branch-delete-${branchName}`}
                                        disabled={isProtected}
                                    >
                                        <FaTrash size={12} />
                                    </Button>
                                </div>
                            </ListGroup.Item>
                        )})}
                    </ListGroup>
                </div>

                <div className="p-3 border-top">
                    <Button variant="primary" className="w-100" onClick={() => onCreateSession()} data-testid="project-create-button">
                        <FaFolderPlus className="me-2"/> New Project
                    </Button>
                    <Button variant="outline-danger" className="w-100 mt-2" onClick={handleDeleteProject} disabled={!currentProjectName} data-testid="project-delete-button">
                        Delete Project
                    </Button>
                </div>
            </div>
        </div>
    );

    const confirmModal = (
        <Modal show={!!confirmState} onHide={() => setConfirmState(null)} centered data-testid="confirm-modal">
            <Modal.Header closeButton>
            <Modal.Title>
                    {confirmState?.type === 'project'
                        ? 'Delete Project'
                        : confirmState?.type === 'merge'
                            ? 'Merge Branch'
                            : confirmState?.type === 'sync'
                                ? 'Sync Branch'
                                : 'Delete Branch'}
            </Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {confirmState?.type === 'project' ? (
                    <>Delete project "{confirmState.projectName}" and all branches? This cannot be undone.</>
                ) : confirmState?.type === 'merge' ? (
                    <>Merge branch "{confirmState?.branchName}" into main? This will update main with the branch changes.</>
                ) : confirmState?.type === 'sync' ? (
                    <>Sync branch "{confirmState?.branchName}" with main? This will merge main into the branch.</>
                ) : (
                    <>Delete branch "{confirmState?.branchName}"? This will remove the on-disk repo.</>
                )}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={() => setConfirmState(null)} data-testid="confirm-cancel">
                    Cancel
                </Button>
                <Button
                    variant={confirmState?.type === 'merge' || confirmState?.type === 'sync' ? 'primary' : 'danger'}
                    onClick={confirmDelete}
                    data-testid="confirm-delete"
                >
                    {confirmState?.type === 'merge'
                        ? 'Merge'
                        : confirmState?.type === 'sync'
                            ? 'Sync'
                            : 'Delete'}
                </Button>
            </Modal.Footer>
        </Modal>
    );

    if (props.isOffcanvas) {
        return (
            <>
                <Offcanvas
                    className="sidebar-offcanvas"
                    show={props.show}
                    onHide={props.onHide}
                    placement="start"
                    backdrop={false}
                    keyboard={false}
                    scroll
                >
                    {content}
                </Offcanvas>
                {confirmModal}
            </>
        );
    }
    return (
        <>
            {content}
            {confirmModal}
        </>
    );
};
