import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { usePermission } from './hooks/usePermission';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { Clients } from './pages/Clients';
import { Staff } from './pages/Staff';
import { Shifts } from './pages/Shifts';

import { Documents } from './pages/Documents';
import './App.css';

function LoginPage() {
  const { login, isLoading } = useAuth();

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const email = (form.elements.namedItem('email') as HTMLInputElement).value;
    const password = (form.elements.namedItem('password') as HTMLInputElement).value;

    try {
      await login(email, password);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed. Check credentials.';
      alert(message);
    }
  };

  return (
    <div className="login-container">
      <h1>Management Portal</h1>
      <form onSubmit={handleSubmit}>
        <input type="email" name="email" placeholder="Email" required />
        <input type="password" name="password" placeholder="Password" required />
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Logging in...' : 'Login'}
        </button>
      </form>
    </div>
  );
}

function ProtectedRoute({ children, module }: { children: React.ReactNode; module?: string }) {
  const { isAuthenticated, isLoading } = useAuth();
  const { hasModuleAccess } = usePermission();

  if (isLoading) return <div className="loading">Loading...</div>;
  if (!isAuthenticated) return <Navigate to="/login" />;
  if (module && !hasModuleAccess(module)) return <Navigate to="/" />;

  return <>{children}</>;
}

function AppRoutes() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) return <div className="loading">Loading...</div>;

  return (
    <Routes>
      <Route path="/login" element={isAuthenticated ? <Navigate to="/" /> : <LoginPage />} />

      <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route index element={<Dashboard />} />
        <Route path="clients" element={<ProtectedRoute module="clients"><Clients /></ProtectedRoute>} />
        <Route path="staff" element={<ProtectedRoute module="staff"><Staff /></ProtectedRoute>} />
        <Route path="shifts" element={<ProtectedRoute module="shifts"><Shifts /></ProtectedRoute>} />

        <Route path="documents" element={<ProtectedRoute module="documents"><Documents /></ProtectedRoute>} />
      </Route>
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
