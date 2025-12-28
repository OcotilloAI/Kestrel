import React, { useEffect, useRef, useState } from 'react';
import type { Message } from '../types';
import { MessageBubble } from './MessageBubble';
import { Button, ButtonGroup, Collapse, Form } from 'react-bootstrap';
import { FaChevronLeft, FaChevronRight } from 'react-icons/fa';

interface ChatAreaProps {
    messages: Message[];
    status: string;
    onSpeak: (text: string) => void;
    isProcessing?: boolean;
    sessionName?: string;
    audioUnlocked?: boolean;
    onUnlockAudio?: () => void;
    readOnlyMessage?: string;
}

export const ChatArea: React.FC<ChatAreaProps> = ({ messages, status, onSpeak, isProcessing, sessionName, audioUnlocked, onUnlockAudio, readOnlyMessage }) => {
    const bottomRef = useRef<HTMLDivElement>(null);
    const scrollRef = useRef<HTMLDivElement>(null);
    const [shouldAutoScroll, setShouldAutoScroll] = useState(true);
    const [activePageIdx, setActivePageIdx] = useState(0);
    const [showFilters, setShowFilters] = useState(false);
    const expectedSources = ['user', 'goose', 'controller', 'system', 'detail', 'summary', 'tool'];
    const [enabledSources, setEnabledSources] = useState<Record<string, boolean>>(() => (
        expectedSources.reduce((acc, source) => {
            acc[source] = true;
            return acc;
        }, {} as Record<string, boolean>)
    ));

    const resolveSource = (message: Message) => {
        if (message.source) return message.source;
        if (message.role === 'user') return 'user';
        if (message.role === 'system') return 'system';
        return 'goose';
    };

    const sourcesInMessages = Array.from(new Set(messages.map(resolveSource)));
    const allSources = Array.from(new Set([...expectedSources, ...sourcesInMessages]));
    const missingSources = expectedSources.filter(source => !sourcesInMessages.includes(source));

    useEffect(() => {
        setEnabledSources(prev => {
            const next = { ...prev };
            let changed = false;
            allSources.forEach(source => {
                if (typeof next[source] === 'undefined') {
                    next[source] = true;
                    changed = true;
                }
            });
            return changed ? next : prev;
        });
    }, [allSources]);

    const filteredMessages = messages.filter(msg => enabledSources[resolveSource(msg)] !== false);

    // Group messages into pages (User message starts a new page)
    const pages: Message[][] = [];
    let currentPage: Message[] = [];
    
    filteredMessages.forEach(msg => {
        if (msg.role === 'user') {
            if (currentPage.length > 0) {
                pages.push(currentPage);
            }
            currentPage = [msg];
        } else {
            currentPage.push(msg);
        }
    });
    if (currentPage.length > 0) {
        pages.push(currentPage);
    }

    // Auto-advance to latest page when a new one is created
    useEffect(() => {
        if (pages.length > 0) {
            setActivePageIdx(pages.length - 1);
        }
    }, [pages.length]);

    // Scroll to bottom when messages on active page change
    useEffect(() => {
        if (shouldAutoScroll) {
            bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages, shouldAutoScroll, activePageIdx]);

    const handleScroll = () => {
        if (scrollRef.current) {
            const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
            const isNearBottom = scrollHeight - scrollTop - clientHeight < 50;
            setShouldAutoScroll(isNearBottom);
        }
    };

    const activePageMsgs = pages[activePageIdx] || [];

    return (
        <div className="flex-grow-1 d-flex flex-column bg-light overflow-hidden">
             <div className="p-2 d-flex justify-content-between align-items-center border-bottom bg-white shadow-sm">
                <div className="small text-muted d-flex flex-column">
                    <span>
                        Status:{' '}
                        <span
                            className={status === 'connected' ? 'text-success' : 'text-danger'}
                            data-testid="session-status"
                        >
                            {status}
                        </span>
                    </span>
                    {sessionName && <span className="fw-bold text-dark" data-testid="session-name">{sessionName}</span>}
                </div>

                <div className="d-flex gap-2 align-items-center">
                    <Button
                        variant="outline-secondary"
                        size="sm"
                        onClick={() => setShowFilters(prev => !prev)}
                        data-testid="source-filter-toggle"
                    >
                        Filters
                    </Button>
                    {readOnlyMessage && (
                        <span className="small text-warning fw-semibold">{readOnlyMessage}</span>
                    )}
                    {!audioUnlocked && onUnlockAudio && (
                        <Button variant="outline-primary" size="sm" onClick={onUnlockAudio}>
                            Enable Audio
                        </Button>
                    )}
                </div>
                
                {pages.length > 1 && (
                    <div className="d-flex align-items-center gap-3">
                        <ButtonGroup size="sm">
                            <Button 
                                variant="outline-secondary" 
                                disabled={activePageIdx === 0}
                                onClick={() => setActivePageIdx(prev => prev - 1)}
                            >
                                <FaChevronLeft />
                            </Button>
                            <Button variant="light" disabled className="text-dark fw-bold border-secondary">
                                Page {activePageIdx + 1} of {pages.length}
                            </Button>
                            <Button 
                                variant="outline-secondary" 
                                disabled={activePageIdx === pages.length - 1}
                                onClick={() => setActivePageIdx(prev => prev + 1)}
                            >
                                <FaChevronRight />
                            </Button>
                        </ButtonGroup>
                    </div>
                )}
            </div>

            <Collapse in={showFilters}>
                <div className="border-bottom bg-white px-3 py-2">
                    <div className="d-flex flex-wrap gap-3 align-items-center">
                        {allSources.map(source => (
                            <Form.Check
                                key={source}
                                type="checkbox"
                                label={source}
                                checked={enabledSources[source]}
                                onChange={() => setEnabledSources(prev => ({ ...prev, [source]: !prev[source] }))}
                                data-testid={`source-filter-${source}`}
                                className="small text-muted"
                            />
                        ))}
                        {missingSources.length > 0 && (
                            <span className="small text-muted">
                                Missing: {missingSources.join(', ')}
                            </span>
                        )}
                    </div>
                </div>
            </Collapse>
            
            <div 
                className="flex-grow-1 overflow-auto p-4" 
                style={{ minHeight: 0 }} 
                ref={scrollRef}
                onScroll={handleScroll}
            >
                {filteredMessages.length === 0 && (
                    <div className="text-center text-muted mt-5">
                        <p>No messages yet. Start a conversation!</p>
                    </div>
                )}
                
                <div className="mb-3">
                    {activePageMsgs.map(msg => (
                        <MessageBubble key={msg.id} message={msg} onSpeak={onSpeak} />
                    ))}
                    {isProcessing && (
                        <div className="text-muted small ms-2 fst-italic">
                            <span className="spinner-grow spinner-grow-sm me-2" role="status" aria-hidden="true"></span>
                            Kestrel is thinking...
                        </div>
                    )}
                </div>
                <div ref={bottomRef} />
            </div>
        </div>
    );
};
