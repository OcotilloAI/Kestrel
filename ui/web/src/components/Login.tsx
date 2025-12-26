import React, { useState } from 'react';
import { Button, Form, Card, Container, Alert } from 'react-bootstrap';

interface LoginProps {
    onLogin: (password: string) => void;
}

export const Login: React.FC<LoginProps> = ({ onLogin }) => {
    const [password, setPassword] = useState('');
    const [error, setError] = useState(false);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (password === 'k3str3lrocks') {
            onLogin(password);
        } else {
            setError(true);
        }
    };

    return (
        <Container className="d-flex align-items-center justify-content-center vh-100 bg-light">
            <Card style={{ width: '400px' }} className="shadow-lg border-0">
                <Card.Body className="p-5">
                    <div className="text-center mb-4">
                        <h2 className="fw-bold">Kestrel</h2>
                        <p className="text-muted">Enter password to access</p>
                    </div>
                    
                    {error && (
                        <Alert variant="danger" className="py-2 small text-center">
                            Incorrect password
                        </Alert>
                    )}

                    <Form onSubmit={handleSubmit}>
                        <Form.Group className="mb-3">
                            <Form.Control 
                                type="password" 
                                placeholder="Password" 
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="text-center"
                                autoFocus
                            />
                        </Form.Group>
                        <div className="d-grid">
                            <Button variant="primary" type="submit" className="fw-bold py-2">
                                Login
                            </Button>
                        </div>
                    </Form>
                </Card.Body>
            </Card>
        </Container>
    );
};
