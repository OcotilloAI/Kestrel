import { useState, useEffect, useRef, useCallback } from 'react';
import type { Message } from '../types';
import { v4 as uuidv4 } from 'uuid';
import { cleanTextForTTS } from '../utils/textProcessing';

export const useChat = (sessionId: string | null, onSessionInvalid?: () => void) => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [status, setStatus] = useState<'connected' | 'disconnected' | 'connecting'>('disconnected');
    const [isProcessing, setIsProcessing] = useState(false);
    const socketRef = useRef<WebSocket | null>(null);
    const synth = window.speechSynthesis;
    
    // Refs for processing
    const rawBufferRef = useRef<string>("");
    const messageAccumulatorRef = useRef<string>(""); // Track full message for turn summary
    const turnTimerRef = useRef<any>(null);
    const connectionIdRef = useRef<number>(0);

    const speak = useCallback(async (text: string, isSummary: boolean = false) => {
        let toSpeak = "";
        if (isSummary) {
            try {
                const response = await fetch('/summarize', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text }),
                });
                if (response.ok) {
                    const data = await response.json();
                    toSpeak = data.summary;
                } else {
                    // Fallback to cleaning if summarization fails
                    toSpeak = cleanTextForTTS(text);
                }
            } catch (e) {
                console.error("Summarization API call failed", e);
                toSpeak = cleanTextForTTS(text); // Fallback on network error
            }
        } else {
            toSpeak = cleanTextForTTS(text);
        }

        if (!toSpeak) return;

        const utterance = new SpeechSynthesisUtterance(toSpeak);
        utterance.rate = 1.0;
        synth.speak(utterance);
    }, [synth]);

    const reconnectTimeoutRef = useRef<any>(null);
    const shouldReconnectRef = useRef<boolean>(true);

    useEffect(() => {
        if (!sessionId) {
            setMessages([]);
            setStatus('disconnected');
            return;
        }

        const connect = () => {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`;
            const connectionId = ++connectionIdRef.current;
            
            console.log("Connecting to:", wsUrl);
            
            setStatus('connecting');
            const socket = new WebSocket(wsUrl);
            socketRef.current = socket;
            shouldReconnectRef.current = true;

                    socket.onopen = () => {
                        setStatus('connected');
                         setMessages([]); 
                         // addMessage("system", "Connected to session " + sessionId.substr(0, 8));
                    };
            
        socket.onmessage = (event) => {
            const text = event.data;
            if (text.startsWith("G: ")) {
                const msgContent = text.substring(3);

                // Do not trigger 'thinking' state for the initial welcome message
                if (msgContent.includes("Welcome to Kestrel")) {
                    // Just add the welcome message without triggering state changes
                    setMessages(prev => [...prev, {
                        id: uuidv4(),
                        role: 'agent',
                        content: msgContent,
                        timestamp: Date.now()
                    }]);
                    return;
                }

                setIsProcessing(true);
                if (turnTimerRef.current) clearTimeout(turnTimerRef.current);

                if (msgContent.startsWith("[LOG]")) {
                    console.log("Backend Log:", msgContent);
                    return;
                }

                messageAccumulatorRef.current += msgContent;
                
                turnTimerRef.current = setTimeout(() => {
                    setIsProcessing(false);
                    const finalContent = messageAccumulatorRef.current;
                    if (finalContent) {
                        speak(finalContent, true);
                    }
                    messageAccumulatorRef.current = ""; 
                }, 2000);


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
                     setIsProcessing(false);
                }
            };

            socket.onclose = (event) => {
                if (socketRef.current !== socket || connectionIdRef.current !== connectionId) {
                    return;
                }
                setStatus('disconnected');
                const reason = (event.reason || '').toLowerCase();
                const isTerminal = event.code === 1008 || reason.includes('session not found');
                if (!shouldReconnectRef.current || isTerminal) {
                    shouldReconnectRef.current = false;
                    if (isTerminal) {
                        setMessages(prev => [...prev, {
                            id: uuidv4(),
                            role: 'system',
                            content: 'Session not found. Please select or create a new session.',
                            timestamp: Date.now()
                        }]);
                        onSessionInvalid?.();
                    }
                    return;
                }
                // Attempt reconnect in 3s
                reconnectTimeoutRef.current = setTimeout(() => {
                    if (connectionIdRef.current !== connectionId) return;
                    console.log("Attempting reconnect...");
                    connect();
                }, 3000);
            };

            socket.onerror = (error) => {
                console.error("WebSocket Error:", error);
                socket.close();
            };
        };

        connect();

        return () => {
            shouldReconnectRef.current = false;
            connectionIdRef.current += 1;
            if (socketRef.current) {
                socketRef.current.close();
                socketRef.current = null;
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
            synth.cancel(); 
        };
    }, [sessionId, speak, synth]);

    const addMessage = (role: 'user' | 'agent' | 'system', content: string) => {
        // Use 'system' role directly, don't convert to agent
        setMessages(prev => [...prev, {
            id: uuidv4(),
            role: role as 'user' | 'agent' | 'system', // Cast to allowed types
            content,
            timestamp: Date.now()
        }]);
    };

    const stopSpeaking = useCallback(() => {
        synth.cancel();
        rawBufferRef.current = "";
        messageAccumulatorRef.current = "";
        if (turnTimerRef.current) clearTimeout(turnTimerRef.current);
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
