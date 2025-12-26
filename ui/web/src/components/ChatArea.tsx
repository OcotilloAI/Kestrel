import React, { useEffect, useRef } from 'react';
import type { Message } from '../types';
import { MessageBubble } from './MessageBubble';

interface ChatAreaProps {
    messages: Message[];
    status: string;
}

export const ChatArea: React.FC<ChatAreaProps> = ({ messages, status }) => {
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    return (
        <div className="flex-grow-1 d-flex flex-column bg-light">
             <div className="p-2 text-center small text-muted border-bottom bg-white">
                Status: <span className={status === 'connected' ? 'text-success' : 'text-danger'}>{status}</span>
            </div>
            
            <div className="flex-grow-1 overflow-auto p-4" style={{ minHeight: 0 }}>
                {messages.length === 0 && (
                    <div className="text-center text-muted mt-5">
                        <p>No messages yet. Start a conversation!</p>
                    </div>
                )}
                
                {messages.map(msg => (
                    <MessageBubble key={msg.id} message={msg} />
                ))}
                <div ref={bottomRef} />
            </div>
        </div>
    );
};
