import { useState, useEffect, useRef, useCallback } from 'react';
import type { Message } from '../types';
import { v4 as uuidv4 } from 'uuid';

export const useChat = (sessionId: string | null) => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [status, setStatus] = useState<'connected' | 'disconnected' | 'connecting'>('disconnected');
    const socketRef = useRef<WebSocket | null>(null);
    const synth = window.speechSynthesis;
    const inCodeBlockRef = useRef(false);

    const speak = useCallback((text: string) => {
        if (!text.trim()) return;

        // Simple markdown cleaning for speech
        // Toggle code block state
        if (text.trim().startsWith("```")) {
            inCodeBlockRef.current = !inCodeBlockRef.current;
            return; // Don't speak the fence line
        }

        if (inCodeBlockRef.current) {
            return; // Don't speak code
        }

        let cleanText = text
            .replace(/^[#\-*]+ /g, '') // Remove starting bullets/headers
            .replace(/[*_`]/g, '')     // Remove formatting chars
            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1'); // Links -> Text

        if (!cleanText.trim()) return;

        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.rate = 1.0;
        synth.speak(utterance);
    }, [synth]);

    useEffect(() => {
        if (!sessionId) {
            setMessages([]);
            setStatus('disconnected');
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`;
        
        console.log("Connecting to:", wsUrl);
        
        setStatus('connecting');
        const socket = new WebSocket(wsUrl);
        socketRef.current = socket;

        socket.onopen = () => {
            setStatus('connected');
             setMessages([]); 
             addMessage("system", "Connected to session " + sessionId.substr(0, 8));
        };

        socket.onmessage = (event) => {
            const text = event.data;
            if (text.startsWith("G: ")) {
                const msgContent = text.substring(3);
                if (msgContent.startsWith("[LOG]")) {
                    console.log("Backend Log:", msgContent);
                    return;
                }
                
                // Speak the chunk
                speak(msgContent);

                // Stream handling
                setMessages(prev => {
                    const last = prev[prev.length - 1];
                    if (last && last.role === 'agent') {
                         return [
                            ...prev.slice(0, -1),
                            { ...last, content: last.content + msgContent }
                        ];
                    } else {
                        return [...prev, {
                            id: uuidv4(),
                            role: 'agent',
                            content: msgContent,
                            timestamp: Date.now()
                        }];
                    }
                });
            } else if (text.startsWith("ERROR:")) {
                 addMessage('agent', "**Error:** " + text);
            }
        };

        socket.onclose = () => {
            setStatus('disconnected');
        };

        socket.onerror = (error) => {
            console.error("WebSocket Error:", error);
            setStatus('disconnected');
        };

        return () => {
            if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
                socket.close();
            }
            synth.cancel(); // Stop speaking on cleanup
        };
    }, [sessionId, speak, synth]);

    const addMessage = (role: 'user' | 'agent' | 'system', content: string) => {
        if (role === 'system') {
             role = 'agent'; 
             content = `*${content}*`;
        }
        
        setMessages(prev => [...prev, {
            id: uuidv4(),
            role: role as 'user' | 'agent',
            content,
            timestamp: Date.now()
        }]);
    };

    const sendMessage = useCallback((text: string) => {
        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(text);
            addMessage('user', text);
        } else {
            console.warn("Socket not connected");
            addMessage('agent', "Error: Not connected.");
        }
    }, []);

    return { messages, status, sendMessage };
};
