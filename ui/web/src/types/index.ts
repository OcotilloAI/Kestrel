export interface Session {
    id: string;
    name: string;
    cwd: string;
    created_at?: string; // Optional depending on backend
}

export interface Message {
    id: string;
    role: 'user' | 'agent' | 'system';
    content: string;
    timestamp: number;
    source?: string;
}

export type SessionMode = 'continue' | 'duplicate' | 'new';
