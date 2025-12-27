import React, { useEffect, useState } from 'react';
import type { Session } from '../types';
import { Button, ListGroup, Offcanvas, Form } from 'react-bootstrap';
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
    onCreateBranch: (projectName: string, branchName?: string, sourceBranch?: string) => void;
    onOpenBranch: (projectName: string, branchName: string) => void;
    branchListByProject: Record<string, string[]>;
    fetchBranches: (projectName: string) => void;
    // Responsive props
    isOffcanvas?: boolean;
    show?: boolean;
    onHide?: () => void;
}


export const Sidebar: React.FC<SidebarProps> = (props) => {
    const { sessions, activeSessionId, projectNames, onSelectSession, onCreateSession, onDeleteBranch, onDeleteBranchByName, onDeleteProject, onCreateBranch, onOpenBranch, branchListByProject, fetchBranches } = props;
    const [newBranchName, setNewBranchName] = useState('');
    const [sourceBranch, setSourceBranch] = useState('main');

    const activeSession = sessions.find(s => s.id === activeSessionId);
    const activeProjectName = activeSession?.name.split('/')[0];
    const [currentProjectName, setCurrentProjectName] = useState(activeProjectName || projectNames[0] || '');
    const branchList = branchListByProject[currentProjectName] || [];

    useEffect(() => {
        if (activeProjectName && activeProjectName !== currentProjectName) {
            setCurrentProjectName(activeProjectName);
        }
        if (!activeProjectName && !currentProjectName && projectNames.length > 0) {
            setCurrentProjectName(projectNames[0]);
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
        const confirmed = window.confirm(`Delete project "${currentProjectName}" and all branches? This cannot be undone.`);
        if (confirmed) {
            onDeleteProject(currentProjectName);
        }
    };

    const handleDeleteBranch = (sessionId: string, branchLabel: string) => {
        const confirmed = window.confirm(`Delete branch "${branchLabel}"? This will remove the on-disk repo.`);
        if (confirmed) {
            onDeleteBranch(sessionId);
        }
    };

    const handleCreateBranch = () => {
        if (!currentProjectName) return;
        const trimmed = newBranchName.trim();
        onCreateBranch(currentProjectName, trimmed || undefined, sourceBranch);
        setNewBranchName('');
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
                        >
                            {branchList.map(b => <option key={b} value={b}>{b}</option>)}
                        </Form.Select>
                        <Form.Control
                            size="sm"
                            placeholder="New branch name (optional)"
                            value={newBranchName}
                            onChange={(e) => setNewBranchName(e.target.value)}
                            disabled={projectNames.length === 0}
                        />
                        <Button size="sm" variant="outline-primary" onClick={handleCreateBranch} disabled={projectNames.length === 0}>
                            Create Branch
                        </Button>
                    </div>
                    <ListGroup variant="flush">
                        {branchList.map(branchName => {
                            const session = sessions.find(s => s.name === `${currentProjectName}/${branchName}`);
                            const isActive = session?.id === activeSessionId;
                            return (
                            <ListGroup.Item 
                                key={branchName} 
                                action 
                                active={isActive}
                                onClick={() => {
                                    if (session) {
                                        onSelectSession(session.id);
                                    } else {
                                        onOpenBranch(currentProjectName, branchName);
                                    }
                                }}
                                className="d-flex justify-content-between align-items-center p-2 rounded mb-1 border-0"
                            >
                                <span className="text-truncate">{branchName}</span>
                                <Button 
                                    variant="link" 
                                    size="sm" 
                                    className="p-0 text-danger" 
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        if (session) {
                                            handleDeleteBranch(session.id, branchName);
                                        } else {
                                            onDeleteBranchByName(currentProjectName, branchName);
                                        }
                                    }}
                                    title="Delete Branch"
                                >
                                    <FaTrash size={12} />
                                </Button>
                            </ListGroup.Item>
                        )})}
                    </ListGroup>
                </div>

                <div className="p-3 border-top">
                    <Button variant="primary" className="w-100" onClick={() => onCreateSession()}>
                        <FaFolderPlus className="me-2"/> New Project
                    </Button>
                    <Button variant="outline-danger" className="w-100 mt-2" onClick={handleDeleteProject} disabled={!currentProjectName}>
                        Delete Project
                    </Button>
                </div>
            </div>
        </div>
    );

    if (props.isOffcanvas) {
        return (
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
        );
    }
    return content;
};
