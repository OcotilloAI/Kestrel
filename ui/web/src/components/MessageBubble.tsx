import React, { useState } from 'react';
import type { Message } from '../types';
import { marked } from 'marked';
import { Card, Button, Collapse } from 'react-bootstrap';
import { FaPlay, FaAlignLeft } from 'react-icons/fa';
import { cleanTextForTTS } from '../utils/textProcessing';

interface MessageBubbleProps {
    message: Message;
    onSpeak: (text: string) => void;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message, onSpeak }) => {
    const isUser = message.role === 'user';
    const htmlContent = marked.parse(message.content);
    const summary = !isUser ? cleanTextForTTS(message.content) : '';
    const [showSummary, setShowSummary] = useState(false);

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
                    
                    {!isUser && summary && (
                        <div className="mt-2 pt-2 border-top">
                            <div className="d-flex gap-2 justify-content-end">
                                <Button 
                                    variant="link" 
                                    size="sm" 
                                    className="p-0 text-muted" 
                                    onClick={() => setShowSummary(!showSummary)}
                                    title="Toggle Speech Summary"
                                >
                                    <FaAlignLeft />
                                </Button>
                                <Button 
                                    variant="link" 
                                    size="sm" 
                                    className="p-0 text-muted" 
                                    onClick={() => onSpeak(message.content)}
                                    title="Read Aloud"
                                >
                                    <FaPlay size={12} />
                                </Button>
                            </div>
                            <Collapse in={showSummary}>
                                <div className="small text-muted mt-2 fst-italic">
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
