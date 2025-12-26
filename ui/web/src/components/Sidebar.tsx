import React, { useState } from 'react';
import type { Session } from '../types';
import { Button, Form, ListGroup } from 'react-bootstrap';
import { FaTrash, FaCopy, FaPlus, FaFolder } from 'react-icons/fa';

interface SidebarProps {
    sessions: Session[];
    activeSessionId: string | null;
    onSelectSession: (id: string) => void;
    onCreateSession: (cwd: string) => void;
    onDeleteSession: (id: string) => void;
    onDuplicateSession: (id: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
    sessions,
    activeSessionId,
    onSelectSession,
    onCreateSession,
    onDeleteSession,
    onDuplicateSession
}) => {
    const [cwd, setCwd] = useState('/app/workdir');

    return (
        <div className="d-flex flex-column h-100 bg-light border-end" style={{ width: '280px', minWidth: '280px' }}>
            <div className="p-3 border-bottom">
                <h5 className="mb-0">Kestrel</h5>
            </div>

            <div className="p-3 border-bottom">
                 <Form.Label className="small text-muted text-uppercase fw-bold">New Session</Form.Label>
                 <Form.Group className="mb-2">
                    <Form.Control 
                        type="text" 
                        size="sm" 
                        placeholder="Working Directory" 
                        value={cwd} 
                        onChange={(e) => setCwd(e.target.value)} 
                    />
                 </Form.Group>
                 <div className="d-grid gap-2">
                    <Button variant="primary" size="sm" onClick={() => onCreateSession(cwd)}>
                        <FaFolder className="me-2" /> Shared Session
                    </Button>
                    <Button variant="secondary" size="sm" onClick={() => onCreateSession('.')}>
                        <FaPlus className="me-2" /> Isolated Session
                    </Button>
                 </div>
            </div>

            <div className="flex-grow-1 overflow-auto p-3">
                <div className="small text-muted text-uppercase fw-bold mb-2">Active Sessions</div>
                <ListGroup variant="flush">
                    {sessions.map(session => (
                        <ListGroup.Item 
                            key={session.id} 
                            action 
                            active={session.id === activeSessionId}
                            onClick={() => onSelectSession(session.id)}
                            className="d-flex justify-content-between align-items-center p-2 rounded mb-1 border-0"
                        >
                            <div className="text-truncate me-2" style={{maxWidth: '140px'}}>
                                <small className="fw-bold d-block">{session.name || session.id.substring(0,8)}</small>
                                <small className="text-muted d-block text-truncate" style={{fontSize: '0.75rem'}}>{session.cwd}</small>
                            </div>
                            <div className="d-flex gap-1">
                                <Button 
                                    variant="link" 
                                    size="sm" 
                                    className="p-0 text-secondary" 
                                    onClick={(e) => { e.stopPropagation(); onDuplicateSession(session.id); }}
                                    title="Duplicate"
                                >
                                    <FaCopy size={12} />
                                </Button>
                                <Button 
                                    variant="link" 
                                    size="sm" 
                                    className="p-0 text-danger" 
                                    onClick={(e) => { e.stopPropagation(); onDeleteSession(session.id); }}
                                    title="Delete"
                                >
                                    <FaTrash size={12} />
                                </Button>
                            </div>
                        </ListGroup.Item>
                    ))}
                    {sessions.length === 0 && (
                        <div className="text-muted small text-center mt-4">No active sessions</div>
                    )}
                </ListGroup>
            </div>
        </div>
    );
};
