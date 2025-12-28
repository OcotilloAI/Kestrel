import { useState, useEffect, useRef, useCallback } from 'react';
import type { Message } from '../types';
import { v4 as uuidv4 } from 'uuid';
import { cleanTextForTTS } from '../utils/textProcessing';

export const useChat = (sessionId: string | null, onSessionInvalid?: () => void) => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [status, setStatus] = useState<'connected' | 'disconnected' | 'connecting'>('disconnected');
    const [isProcessing, setIsProcessing] = useState(false);
    const [audioUnlocked, setAudioUnlocked] = useState(false);
    const socketRef = useRef<WebSocket | null>(null);
    const synth = window.speechSynthesis;
    
    // Refs for processing
    const rawBufferRef = useRef<string>("");
    const messageAccumulatorRef = useRef<string>(""); // Track full message for turn summary
    const turnTimerRef = useRef<any>(null);
    const connectionIdRef = useRef<number>(0);

    const recordClientEvent = useCallback(async (eventType: string, role: string, source: string, content: string) => {
        if (!sessionId) return;
        try {
            await fetch(`/session/${encodeURIComponent(sessionId)}/event`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: eventType, role, source, content })
            });
        } catch {
            return;
        }
    }, [sessionId]);

    const speak = useCallback(async (text: string, isSummary: boolean = false) => {
        if (!audioUnlocked) {
            return;
        }
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
        if (isSummary) {
            recordClientEvent('summary', 'system', 'summary', toSpeak);
        }
    }, [audioUnlocked, synth, recordClientEvent]);

    const unlockAudio = useCallback(() => {
        if (audioUnlocked) return;
        const utterance = new SpeechSynthesisUtterance("Audio enabled.");
        utterance.rate = 1.0;
        utterance.onend = () => setAudioUnlocked(true);
        utterance.onerror = () => setAudioUnlocked(false);
        synth.speak(utterance);
    }, [audioUnlocked, synth]);

    const loadTranscript = useCallback(async (id: string) => {
        try {
            const res = await fetch(`/session/${encodeURIComponent(id)}/transcript`);
            if (!res.ok) return;
            const data = await res.json();
            if (!Array.isArray(data) || data.length === 0) return;
            const mapped: Message[] = [];
            for (const event of data) {
                const type = event?.type;
                const role = event?.role;
                const content = String(event?.content ?? '');
                if (!content) continue;
                let msgRole: 'user' | 'agent' | 'system' = 'agent';
                if (type === 'user') msgRole = 'user';
                if (type === 'system' || type === 'detail' || role === 'controller') msgRole = 'system';
                const source = event?.source || role || type || (msgRole === 'agent' ? 'goose' : msgRole);

                const last = mapped[mapped.length - 1];
                if (last && last.role === msgRole && last.source === source) {
                    last.content += content;
                    continue;
                }
                mapped.push({
                    id: uuidv4(),
                    role: msgRole,
                    content,
                    timestamp: event?.timestamp ? Number(event.timestamp) : Date.now(),
                    source
                });
            }
            if (mapped.length > 0) {
                setMessages(mapped);
            }
        } catch {
            return;
        }
    }, []);

    const reconnectTimeoutRef = useRef<any>(null);
    const shouldReconnectRef = useRef<boolean>(true);
    const hasConnectedRef = useRef<boolean>(false);

    useEffect(() => {
        setIsProcessing(false);
        if (!sessionId) {
            setMessages([]);
            setStatus('disconnected');
            return;
        }

        hasConnectedRef.current = false;
        setMessages([]);
        loadTranscript(sessionId);

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
                        if (!hasConnectedRef.current) {
                            hasConnectedRef.current = true;
                        }
                        // addMessage("system", "Connected to session " + sessionId.substr(0, 8));
                    };
            
            socket.onmessage = (event) => {
            const text = event.data;
            let parsed: any = null;
            if (typeof text === 'string' && text.trim().startsWith('{')) {
                try {
                    parsed = JSON.parse(text);
                } catch {
                    parsed = null;
                }
            }

            if (parsed && parsed.content) {
                const eventType = parsed.type || 'assistant';
                const msgContent = String(parsed.content);

                if (eventType === 'system') {
                    addMessage('system', msgContent, parsed?.source || 'system');
                    setIsProcessing(false);
                    return;
                }
                if (eventType === 'detail') {
                    addMessage('system', msgContent, parsed?.source || 'detail');
                    speak(msgContent, false);
                    return;
                }
                if (eventType === 'assistant') {
                    if (msgContent.startsWith("[LOG]")) {
                        console.log("Backend Log:", msgContent);
                        return;
                    }
                    setIsProcessing(true);
                    if (turnTimerRef.current) clearTimeout(turnTimerRef.current);
                    messageAccumulatorRef.current += msgContent;
                    turnTimerRef.current = setTimeout(() => {
                        setIsProcessing(false);
                        const finalContent = messageAccumulatorRef.current;
                        if (finalContent) {
                            speak(finalContent, true);
                        }
                        messageAccumulatorRef.current = "";
                    }, 2000);
                    const role = parsed?.role === 'controller' ? 'system' : 'agent';
                    const source = parsed?.source || (role === 'system' ? 'controller' : 'goose');
                    setMessages(prev => {
                        const last = prev[prev.length - 1];
                        if (last && last.role === role && last.source === source) {
                             return [
                                ...prev.slice(0, -1),
                                { ...last, content: last.content + msgContent }
                            ];
                        } else {
                            return [...prev, {
                                id: uuidv4(),
                                role,
                                content: msgContent,
                                timestamp: Date.now(),
                                source
                            }];
                        }
                    });
                    return;
                }
            }

            if (text.startsWith("G: ")) {
                const msgContent = text.substring(3);

                // Do not trigger 'thinking' state for the initial welcome message
                if (msgContent.includes("Welcome to Kestrel")) {
                    // Just add the welcome message without triggering state changes
                    setMessages(prev => [...prev, {
                        id: uuidv4(),
                        role: 'agent',
                        content: msgContent,
                        timestamp: Date.now(),
                        source: 'goose'
                    }]);
                    return;
                }

                if (msgContent.startsWith("[LOG]")) {
                    console.log("Backend Log:", msgContent);
                    return;
                }

                setIsProcessing(true);
                if (turnTimerRef.current) clearTimeout(turnTimerRef.current);

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
                        if (last && last.role === 'agent' && last.source === 'goose') {
                             return [
                                ...prev.slice(0, -1),
                                { ...last, content: last.content + msgContent }
                            ];
                        } else {
                            return [...prev, {
                                id: uuidv4(),
                                role: 'agent',
                                content: msgContent,
                                timestamp: Date.now(),
                                source: 'goose'
                            }];
                        }
                    });
                } else if (text.startsWith("ERROR:")) {
                     addMessage('agent', "**Error:** " + text, 'system');
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

    const addMessage = (role: 'user' | 'agent' | 'system', content: string, source?: string) => {
        // Use 'system' role directly, don't convert to agent
        setMessages(prev => [...prev, {
            id: uuidv4(),
            role: role as 'user' | 'agent' | 'system', // Cast to allowed types
            content,
            timestamp: Date.now(),
            source
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
            addMessage('user', text, 'user');
        } else {
            console.warn("Socket not connected");
            addMessage('agent', "Error: Not connected.", 'system');
        }
    }, [stopSpeaking]);

    return { messages, status, sendMessage, isProcessing, stopSpeaking, speakText: speak, audioUnlocked, unlockAudio };
};
