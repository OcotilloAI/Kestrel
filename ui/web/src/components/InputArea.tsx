import React, { useState, useEffect, useRef } from 'react';
import { Button, Form, InputGroup, Dropdown, DropdownButton } from 'react-bootstrap';
import { FaPaperPlane, FaMicrophone, FaStop } from 'react-icons/fa';
import type { SessionMode } from '../types';

interface InputAreaProps {
    onSend: (text: string, mode: SessionMode) => void;
    disabled?: boolean;
}

export const InputArea: React.FC<InputAreaProps> = ({ onSend, disabled }) => {
    const [text, setText] = useState('');
    const [isListening, setIsListening] = useState(false);
    const [mode, setMode] = useState<SessionMode>('continue');
    const recognitionRef = useRef<any>(null);

    useEffect(() => {
        // Init speech recognition
        const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
        if (SpeechRecognition) {
            const recognition = new SpeechRecognition();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = 'en-US';

            recognition.onresult = (event: any) => {
                let finalTranscript = '';
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        finalTranscript += event.results[i][0].transcript;
                    }
                }
                if (finalTranscript) {
                    // Automatically send on final result? Or just append? 
                    // The original app sent it. Let's append to text for review, or send if we want "hands-free"
                    // Original: handleNewPrompt(finalTranscript) immediately
                    onSend(finalTranscript, mode);
                }
            };
            
            recognition.onerror = (event: any) => {
                console.error("Speech recognition error", event.error);
                setIsListening(false);
            };
            
            recognition.onend = () => {
                if (isListening) {
                     // Auto-restart if we think we are still listening? 
                     // Or just stop.
                     try { recognition.start(); } catch(e) { setIsListening(false); }
                } else {
                    setIsListening(false);
                }
            };

            recognitionRef.current = recognition;
        }
    }, [onSend, mode, isListening]); // Careful with deps here

    const toggleListening = () => {
        if (!recognitionRef.current) {
            alert("Speech recognition not supported in this browser.");
            return;
        }

        if (isListening) {
            setIsListening(false);
            recognitionRef.current.stop();
        } else {
            setIsListening(true);
            recognitionRef.current.start();
        }
    };

    const handleSend = () => {
        if (!text.trim()) return;
        onSend(text, mode);
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
             <div className="d-flex justify-content-center align-items-center mb-2 gap-2">
                <span className="small text-muted">Mode:</span>
                <DropdownButton 
                    id="mode-dropdown" 
                    title={mode === 'continue' ? 'Continue Session' : mode === 'duplicate' ? 'Duplicate Session' : 'New Isolated Session'}
                    size="sm"
                    variant="outline-secondary"
                    onSelect={(e) => setMode(e as SessionMode)}
                >
                    <Dropdown.Item eventKey="continue">Continue Session</Dropdown.Item>
                    <Dropdown.Item eventKey="duplicate">Duplicate Session</Dropdown.Item>
                    <Dropdown.Item eventKey="new">New Isolated Session</Dropdown.Item>
                </DropdownButton>
            </div>

            <InputGroup>
                <Form.Control
                    as="textarea"
                    placeholder="Type a message..."
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={handleKeyDown}
                    style={{ borderRadius: '20px', resize: 'none', height: '50px' }}
                    disabled={disabled}
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
                >
                    <FaPaperPlane />
                </Button>
            </InputGroup>
        </div>
    );
};
