import { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';

const API_BASE = 'https://localhost:8443';

// Types inline to avoid import issues
type RoleName = 'admin' | 'director' | 'site_director' | 'dsp';

interface User {
    id: number;
    first_name: string;
    last_name: string;
    email: string;
    work_phone: string | null;
    profile_image_url: string | null;
    role_id: number;
    role_name: RoleName;
    assigned_location_id: number | null;
    session_id: number;
    last_activity: string;
}

interface AuthState {
    user: User | null;
    token: string | null;
    isAuthenticated: boolean;
    isLoading: boolean;
}

interface AuthContextType extends AuthState {
    login: (email: string, password: string) => Promise<void>;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [state, setState] = useState<AuthState>({
        user: null,
        token: sessionStorage.getItem('token'),
        isAuthenticated: false,
        isLoading: true,
    });

    useEffect(() => {
        // --- 1. Fetch User on Mount ---
        const fetchUser = async () => {
            const token = sessionStorage.getItem('token');
            if (!token) {
                setState(s => ({ ...s, isLoading: false }));
                return;
            }


            try {
                const res = await fetch(`${API_BASE}/auth/me`, {
                    headers: { Authorization: `Bearer ${token}` },
                });

                if (res.ok) {
                    const user: User = await res.json();

                    // Block DSP access to portal
                    if (user.role_name === 'dsp') {
                        sessionStorage.removeItem('token');
                        setState({ user: null, token: null, isAuthenticated: false, isLoading: false });
                        return;
                    }

                    setState({ user, token, isAuthenticated: true, isLoading: false });
                } else {
                    sessionStorage.removeItem('token');
                    setState({ user: null, token: null, isAuthenticated: false, isLoading: false });
                }
            } catch {
                setState(s => ({ ...s, isLoading: false }));
            }
        };

        fetchUser();

        // --- 2. Listen for 401 Unauthorized events from api.ts (Server-side Reactive) ---
        const handleUnauthorized = () => {
            sessionStorage.removeItem('token');
            setState({ user: null, token: null, isAuthenticated: false, isLoading: false });
        };



        window.addEventListener('auth:unauthorized', handleUnauthorized);

        // --- 3. Client-Side Inactivity Timer (Proactive) ---
        // 10 minutes = 600,000 ms
        const INACTIVITY_LIMIT_MS = 10 * 60 * 1000;
        let inactivityTimer: any;

        const logoutUser = async () => {
            // Client-side inactivity timeout reached
            // Notify server for audit log
            const token = sessionStorage.getItem('token');
            if (token) {
                try {
                    await fetch(`${API_BASE}/auth/logout?reason=client_timeout`, {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'Content-Type': 'application/json'
                        },
                        keepalive: true
                    });
                } catch (e) {
                    console.error("Logout failed", e);
                }
            }

            sessionStorage.removeItem('token');
            setState({ user: null, token: null, isAuthenticated: false, isLoading: false });
        };

        const resetTimer = () => {
            if (inactivityTimer) clearTimeout(inactivityTimer);
            inactivityTimer = setTimeout(logoutUser, INACTIVITY_LIMIT_MS);
        };

        // Events to track activity
        const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];

        events.forEach(event => document.addEventListener(event, resetTimer));

        // Start timer initially
        resetTimer();

        // Cleanup
        return () => {
            window.removeEventListener('auth:unauthorized', handleUnauthorized);
            events.forEach(event => document.removeEventListener(event, resetTimer));
            if (inactivityTimer) clearTimeout(inactivityTimer);
        };
    }, []);

    const login = async (email: string, password: string) => {
        const res = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });

        if (!res.ok) {
            throw new Error('Invalid credentials');
        }

        const data = await res.json();

        // Fetch user details BEFORE storing token
        const userRes = await fetch(`${API_BASE}/auth/me`, {
            headers: { Authorization: `Bearer ${data.access_token}` },
        });
        const user: User = await userRes.json();

        // Block DSP access to portal - do NOT store token
        if (user.role_name === 'dsp') {
            throw new Error('DSPs are not authorized to access the management portal. Please use the mobile app.');
        }

        // Only store token after confirming non-DSP role
        sessionStorage.setItem('token', data.access_token);
        setState({ user, token: data.access_token, isAuthenticated: true, isLoading: false });
    };

    const logout = async () => {
        const token = sessionStorage.getItem('token');
        if (token) {
            try {
                await fetch(`${API_BASE}/auth/logout?reason=user_initiated`, {
                    method: 'POST',
                    headers: { Authorization: `Bearer ${token}` },
                });
            } catch (e) {
                console.error("Logout failed", e);
            }
        }
        sessionStorage.removeItem('token');
        setState({ user: null, token: null, isAuthenticated: false, isLoading: false });
    };

    return (
        <AuthContext.Provider value={{ ...state, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth(): AuthContextType {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within AuthProvider');
    }
    return context;
}

export type { User, RoleName, AuthState };
