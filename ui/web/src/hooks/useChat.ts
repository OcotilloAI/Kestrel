import { useState, useEffect, useRef, useCallback } from 'react';
import type { Message } from '../types';
import { v4 as uuidv4 } from 'uuid';
import { cleanTextForTTS } from '../utils/textProcessing';

export const useChat = (sessionId: string | null) => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [status, setStatus] = useState<'connected' | 'disconnected' | 'connecting'>('disconnected');
    const [isProcessing, setIsProcessing] = useState(false);
    const socketRef = useRef<WebSocket | null>(null);
    const synth = window.speechSynthesis;
    const ttsBufferRef = useRef<string>("");

    const speak = useCallback((text: string) => {
        const cleanText = cleanTextForTTS(text);
        if (!cleanText) return;

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
                setIsProcessing(false);
                const msgContent = text.substring(3);
                if (msgContent.startsWith("[LOG]")) {
                    console.log("Backend Log:", msgContent);
                    return;
                }
                
                // Buffer and Speak
                ttsBufferRef.current += msgContent;
                
                // Find last sentence boundary
                // Look for . ! ? followed by space or newline
                // We regex search for the *last* occurrence to split safely
                // Actually, just find *any* sentence boundary and speak up to it
                // to keep latency low.
                
                let buffer = ttsBufferRef.current;
                // Regex: punctuation followed by whitespace
                const sentenceRegex = /([.!?]+)(\s+)/g;
                let lastIndex = 0;
                
                // Find all sentences
                while (sentenceRegex.exec(buffer) !== null) {
                    const sentence = buffer.substring(lastIndex, sentenceRegex.lastIndex);
                    speak(sentence);
                    lastIndex = sentenceRegex.lastIndex;
                }
                
                // Keep the remainder in buffer
                if (lastIndex > 0) {
                    ttsBufferRef.current = buffer.substring(lastIndex);
                }

                // Stream handling for UI
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

    const stopSpeaking = useCallback(() => {
        synth.cancel();
        ttsBufferRef.current = "";
    }, [synth]);

    const sendMessage = useCallback((text: string) => {
        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            setIsProcessing(true);
            stopSpeaking();
            socketRef.current.send(text);
            addMessage('user', text);
        } else {
            console.warn("Socket not connected");
            addMessage('agent', "Error: Not connected.");
        }
    }, [stopSpeaking]);

    return { messages, status, sendMessage, isProcessing, stopSpeaking, speakText: speak };
};
