import React, { useState, useEffect, useRef } from 'react';
import { Button, Form, InputGroup, Spinner } from 'react-bootstrap';
import { FaPaperPlane, FaMicrophone, FaStop } from 'react-icons/fa';
import type { SessionMode } from '../types';

interface InputAreaProps {
    onSend: (text: string, mode: SessionMode) => void;
    onInteraction?: () => void;
    disabled?: boolean;
    isProcessing?: boolean;
}

export const InputArea: React.FC<InputAreaProps> = ({ onSend, onInteraction, disabled, isProcessing }) => {
    const [text, setText] = useState('');
    const [isListening, setIsListening] = useState(false);
    const [autoSend, setAutoSend] = useState(false);
    const recognitionRef = useRef<any>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const sendTimerRef = useRef<any>(null);
    const textRef = useRef(text);
    
    useEffect(() => { textRef.current = text; }, [text]);

    // Auto-resize textarea
    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = 'auto';
            const scrollHeight = textarea.scrollHeight;
            const maxHeight = window.innerHeight * 0.75;
            if (scrollHeight > maxHeight) {
                textarea.style.height = `${maxHeight}px`;
                textarea.style.overflowY = 'auto';
            } else {
                textarea.style.height = `${scrollHeight}px`;
                textarea.style.overflowY = 'hidden';
            }
        }
    }, [text]);

    useEffect(() => {
        if (isProcessing && isListening) {
            setIsListening(false);
            recognitionRef.current?.stop();
        }
    }, [isProcessing, isListening]);

    useEffect(() => {
        const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
        if (SpeechRecognition) {
            const recognition = new SpeechRecognition();
            recognition.continuous = autoSend;
            recognition.interimResults = true;
            recognition.lang = 'en-US';

            recognition.onresult = (event: any) => {
                let newFinalTranscript = '';
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        newFinalTranscript += event.results[i][0].transcript + ' ';
                    }
                }

                if (newFinalTranscript) {
                    setText(prev => prev + newFinalTranscript);
                    onInteraction?.();
                    if (autoSend) {
                        if (sendTimerRef.current) clearTimeout(sendTimerRef.current);
                        sendTimerRef.current = setTimeout(() => {
                            const currentText = textRef.current;
                            if (currentText.trim()) {
                                onSend(currentText, 'continue');
                                setText('');
                            }
                        }, 3000);
                    } else {
                        setIsListening(false);
                        recognition.stop();
                    }
                }
            };
            
            recognition.onerror = (event: any) => { console.error("Speech recognition error", event.error); setIsListening(false); };
            recognition.onend = () => {
                if (isListening && autoSend) {
                    try {
                        recognition.start();
                    } catch (e) {
                        setIsListening(false);
                    }
                } else {
                    setIsListening(false);
                }
            };
            recognitionRef.current = recognition;
        }
    }, [onSend, isListening, autoSend, onInteraction]);

    const toggleListening = () => {
        if (!recognitionRef.current) return alert("Speech recognition not supported.");
        if (isListening) {
            setIsListening(false);
            recognitionRef.current.stop();
        }
        else {
            onInteraction?.();
            setIsListening(true);
            recognitionRef.current.start();
        }
    };

    const handleSend = () => {
        onInteraction?.();
        if (!text.trim()) return;
        onSend(text, 'continue');
        setText('');
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className="bg-white p-3 border-top shadow-sm">
             <div className="d-flex justify-content-end align-items-center mb-2">
                <Form.Check 
                    type="switch"
                    id="auto-send-switch"
                    label="Auto-Send Speech"
                    checked={autoSend}
                    onChange={(e) => setAutoSend(e.target.checked)}
                    className="small text-muted"
                />
            </div>

            <InputGroup>

                <Form.Control
                    as="textarea"
                    ref={textareaRef}
                    placeholder="Type a message..."
                    value={text}
                    onChange={(e) => {
                        setText(e.target.value);
                        onInteraction?.();
                    }}
                    onKeyDown={handleKeyDown}
                    style={{ 
                        borderRadius: '20px', 
                        resize: 'none', 
                        height: 'auto',
                        minHeight: '50px',
                        maxHeight: '75vh',
                        overflowY: 'hidden'
                    }}
                    disabled={disabled}
                    data-testid="message-input"
                />
                <Button 
                    variant={isListening ? "danger" : "outline-secondary"} 
                    className="rounded-circle ms-2 d-flex align-items-center justify-content-center"
                    style={{ width: '50px', height: '50px' }}
                    onClick={toggleListening}
                    disabled={disabled}
                    title={isListening ? "Stop Listening" : "Start Listening"}
                >
                    {isListening ? <FaStop /> : <FaMicrophone />}
                </Button>
                <Button 
                    variant="primary" 
                    className="rounded-circle ms-2 d-flex align-items-center justify-content-center"
                    style={{ width: '50px', height: '50px' }}
                    onClick={handleSend}
                    disabled={disabled || !text.trim()}
                    data-testid="send-button"
                >
                    {isProcessing ? <Spinner animation="border" size="sm" /> : <FaPaperPlane />}
                </Button>
            </InputGroup>
        </div>
    );
};
