import React from 'react';
import type { Message } from '../types';
import { marked } from 'marked';
import { Card } from 'react-bootstrap';

interface MessageBubbleProps {
    message: Message;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
    const isUser = message.role === 'user';
    const htmlContent = marked.parse(message.content);

    return (
        <div className={`d-flex mb-3 ${isUser ? 'justify-content-end' : 'justify-content-start'}`}>
            <Card 
                className={`border-0 shadow-sm ${isUser ? 'bg-primary text-white' : 'bg-white'}`}
                style={{ maxWidth: '85%', borderRadius: '18px' }}
            >
                <Card.Body className="p-3">
                    <div 
                        className="markdown-content"
                        dangerouslySetInnerHTML={{ __html: htmlContent }} 
                        style={{ 
                            color: isUser ? 'white' : 'inherit',
                            fontSize: '0.95rem',
                            lineHeight: '1.5'
                        }}
                    />
                </Card.Body>
            </Card>
        </div>
    );
};
