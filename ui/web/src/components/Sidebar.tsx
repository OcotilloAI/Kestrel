import React, { useMemo } from 'react';
import type { Session } from '../types';
import { Button, ListGroup, Offcanvas, Dropdown, ButtonGroup, Form } from 'react-bootstrap';
import { FaTrash, FaCopy, FaChevronLeft, FaChevronRight, FaFolderPlus } from 'react-icons/fa';
import '../App.css';

// ... (Props interface remains large for now, will simplify later if possible)
interface SidebarProps {
    sessions: Session[];
    activeSessionId: string | null;
    onSelectSession: (id: string) => void;
    onCreateSession: (cwd?: string, copyFrom?: string) => void;
    onDeleteBranch: (id: string) => void;
    onDeleteProject: (projectName: string) => void;
    onDuplicateSession: (id: string) => void; // This is now Clone Branch
    // Responsive props
    isOffcanvas?: boolean;
    show?: boolean;
    onHide?: () => void;
    isCollapsed?: boolean;
    onToggleCollapse?: () => void;
}


export const Sidebar: React.FC<SidebarProps> = (props) => {
    const { sessions, activeSessionId, onSelectSession, onCreateSession, onDeleteBranch, onDeleteProject, onDuplicateSession } = props;

    // Group sessions into projects
    const { projects, activeProjectName } = useMemo(() => {
        const projectMap: { [key: string]: { name: string, branches: Session[] } } = {};
        let activeProject: string | null = null;

        sessions.forEach(session => {
            const parts = session.name.split('/');
            const projectName = parts.length > 1 ? parts[0] : 'Default';
            
            if (!projectMap[projectName]) {
                projectMap[projectName] = { name: projectName, branches: [] };
            }
            projectMap[projectName].branches.push(session);

            if (session.id === activeSessionId) {
                activeProject = projectName;
            }
        });
        return { projects: Object.values(projectMap), activeProjectName: activeProject };
    }, [sessions, activeSessionId]);

    const activeProject = projects.find(p => p.name === activeProjectName);
    const activeSession = sessions.find(s => s.id === activeSessionId);
    const currentProjectName = activeProjectName || '';
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

    const content = (
        <div className={`sidebar-container bg-light border-end ${props.isCollapsed ? 'collapsed' : ''}`}>
            {/* Header */}
            <div className="sidebar-header p-3 border-bottom d-flex justify-content-between align-items-center">
                {!props.isCollapsed && <h5 className="mb-0">Kestrel</h5>}
                {props.isOffcanvas && <Button variant="close" onClick={props.onHide} />}
                {!props.isOffcanvas && (
                    <Button variant="outline-secondary" size="sm" onClick={props.onToggleCollapse} className="toggle-btn">
                        {props.isCollapsed ? <FaChevronRight /> : <FaChevronLeft />}
                    </Button>
                )}
            </div>

            {/* Content Area */}
            <div className={`sidebar-content ${props.isCollapsed ? 'd-none' : ''}`}>
                {/* Project Selector & Actions */}
                <div className="p-3 border-bottom">
                    <Dropdown as={ButtonGroup} className="d-flex mb-2">
                        <Button variant="primary" onClick={() => onCreateSession()}>
                            <FaFolderPlus className="me-2"/> New Project
                        </Button>
                        <Dropdown.Toggle split variant="primary" id="project-actions-dropdown" />
                        <Dropdown.Menu>
                            <Dropdown.Item onClick={() => onDuplicateSession(activeSessionId!)} disabled={!activeSession}>
                                <FaCopy className="me-2"/> Clone Branch
                            </Dropdown.Item>
                             <Dropdown.Divider />
                             <Dropdown.Item onClick={handleDeleteProject} disabled={!currentProjectName}>
                                 Delete Project
                             </Dropdown.Item>
                        </Dropdown.Menu>
                    </Dropdown>

                    <Form.Label className="small text-muted text-uppercase fw-bold mt-2">Current Project</Form.Label>
                     <Form.Select size="sm" value={currentProjectName} onChange={() => {}} disabled>
                        {projects.map(p => <option key={p.name} value={p.name}>{p.name}</option>)}
                     </Form.Select>
                </div>

                {/* Branch List */}
                <div className="flex-grow-1 overflow-auto p-3">
                    <div className="small text-muted text-uppercase fw-bold mb-2">Branches</div>
                    <ListGroup variant="flush">
                        {activeProject?.branches.map(branch => (
                            <ListGroup.Item 
                                key={branch.id} 
                                action 
                                active={branch.id === activeSessionId}
                                onClick={() => onSelectSession(branch.id)}
                                className="d-flex justify-content-between align-items-center p-2 rounded mb-1 border-0"
                            >
                                <span className="text-truncate">{branch.name.split('/')[1] || 'main'}</span>
                                <Button 
                                    variant="link" 
                                    size="sm" 
                                    className="p-0 text-danger" 
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleDeleteBranch(branch.id, branch.name.split('/')[1] || 'main');
                                    }}
                                    title="Delete Branch"
                                >
                                    <FaTrash size={12} />
                                </Button>
                            </ListGroup.Item>
                        ))}
                    </ListGroup>
                </div>
            </div>
        </div>
    );

    if (props.isOffcanvas) {
        return <Offcanvas show={props.show} onHide={props.onHide} placement="start">{content}</Offcanvas>;
    }
    return content;
};
