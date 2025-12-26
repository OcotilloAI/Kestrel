import React, { useEffect, useRef, useState } from 'react';
import type { Message } from '../types';
import { MessageBubble } from './MessageBubble';
import { Button, ButtonGroup } from 'react-bootstrap';
import { FaChevronLeft, FaChevronRight } from 'react-icons/fa';

interface ChatAreaProps {
    messages: Message[];
    status: string;
    onSpeak: (text: string) => void;
}

export const ChatArea: React.FC<ChatAreaProps> = ({ messages, status, onSpeak }) => {
    const bottomRef = useRef<HTMLDivElement>(null);
    const scrollRef = useRef<HTMLDivElement>(null);
    const [shouldAutoScroll, setShouldAutoScroll] = useState(true);
    const [activePageIdx, setActivePageIdx] = useState(0);

    // Group messages into pages (User message starts a new page)
    const pages: Message[][] = [];
    let currentPage: Message[] = [];
    
    messages.forEach(msg => {
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
                <div className="small text-muted">
                    Status: <span className={status === 'connected' ? 'text-success' : 'text-danger'}>{status}</span>
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
            
            <div 
                className="flex-grow-1 overflow-auto p-4" 
                style={{ minHeight: 0 }} 
                ref={scrollRef}
                onScroll={handleScroll}
            >
                {messages.length === 0 && (
                    <div className="text-center text-muted mt-5">
                        <p>No messages yet. Start a conversation!</p>
                    </div>
                )}
                
                <div className="mb-3">
                    {activePageMsgs.map(msg => (
                        <MessageBubble key={msg.id} message={msg} onSpeak={onSpeak} />
                    ))}
                </div>
                <div ref={bottomRef} />
            </div>
        </div>
    );
};
