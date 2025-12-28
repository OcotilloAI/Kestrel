import React, { useState } from 'react';
import type { Message } from '../types';
import { marked } from 'marked';
import { Card, Button, Collapse } from 'react-bootstrap';
import { FaPlay, FaAlignLeft, FaTerminal } from 'react-icons/fa';
import { cleanTextForTTS } from '../utils/textProcessing';

interface MessageBubbleProps {
    message: Message;
    onSpeak: (text: string) => void;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message, onSpeak }) => {
    const isUser = message.role === 'user';
    const isSystem = message.role === 'system';
    
    if (isSystem) {
        return (
            <div className="d-flex justify-content-center mb-3">
                <div className="small text-muted fst-italic px-3 py-1 bg-light rounded-pill border">
                    {message.content}
                </div>
            </div>
        );
    }

    const summary = !isUser ? cleanTextForTTS(message.content) : '';
    const [showSummary, setShowSummary] = useState(false);

    // Parse content to separate tool logs
    // We assume tool logs start with "───" and might end or be interspersed.
    // Simple split:
    const renderContent = (text: string) => {
        // Regex for tool header: ─── tool | extension ───
        const parts = text.split(/(?=^\s*?[─-]{3,}\s+[\w_]+\s+\|\s+[\w_]+\s+[─-]+)/m);
        
        return parts.map((part, idx) => {
            const match = part.match(/^\s*?[─-]{3,}\s+([\w_]+)\s+\|\s+([\w_]+)\s+[─-]+/);
            if (match) {
                const [fullMatch, tool, extension] = match;
                const content = part.substring(fullMatch.length).trim();
                // Check if there is output after the command block?
                // Often the block contains command params and then output.
                
                return (
                    <div key={idx} className="my-2">
                        <details className="mb-2 p-2 border rounded bg-light small">
                            <summary className="cursor-pointer text-muted font-monospace d-flex align-items-center gap-2">
                                <FaTerminal size={12} />
                                {tool} ({extension})
                            </summary>
                            <pre className="mt-2 mb-0 p-2 bg-white border rounded overflow-auto" style={{maxHeight: '200px'}}>
                                {content}
                            </pre>
                        </details>
                    </div>
                );
            } else {
                if (!part.trim()) return null;
                const html = marked.parse(part);
                return (
                    <div 
                        key={idx}
                        className="markdown-content"
                        dangerouslySetInnerHTML={{ __html: html }} 
                        style={{ 
                            color: isUser ? 'white' : 'inherit',
                            fontSize: '0.95rem',
                            lineHeight: '1.5'
                        }}
                    />
                );
            }
        });
    };

    return (
        <div className={`d-flex mb-3 ${isUser ? 'justify-content-end' : 'justify-content-start'}`} data-testid="message-bubble" data-role={message.role} data-source={message.source || ''}>
            <Card 
                className={`border-0 shadow-sm ${isUser ? 'bg-primary text-white' : 'bg-white'}`}
                style={{ maxWidth: '85%', borderRadius: '18px' }}
            >
                <Card.Body className="p-3">
                    {renderContent(message.content)}
                    
                    {!isUser && summary && (
                        <div className="mt-2 pt-2 border-top">
                            <div className="d-flex gap-2 justify-content-end">
                                <Button 
                                    variant="link" 
                                    size="sm" 
                                    className={`p-0 ${isUser ? 'text-white' : 'text-muted'}`}
                                    onClick={() => setShowSummary(!showSummary)}
                                    title="Toggle Speech Summary"
                                >
                                    <FaAlignLeft />
                                </Button>
                                <Button 
                                    variant="link" 
                                    size="sm" 
                                    className={`p-0 ${isUser ? 'text-white' : 'text-muted'}`}
                                    onClick={() => onSpeak(message.content)}
                                    title="Read Aloud"
                                >
                                    <FaPlay size={12} />
                                </Button>
                            </div>
                            <Collapse in={showSummary}>
                                <div className={`small mt-2 fst-italic ${isUser ? 'text-white-50' : 'text-muted'}`}>
                                    <strong>Summary (Spoken):</strong><br/>
                                    {summary}
                                </div>
                            </Collapse>
                        </div>
                    )}
                </Card.Body>
            </Card>
        </div>
    );
};
