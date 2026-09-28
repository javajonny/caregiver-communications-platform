import type { ReactNode } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { usePermission } from '../hooks/usePermission';
import type { RoleName } from '../types/auth';

interface ProtectedRouteProps {
    children: ReactNode;
    requiredModule?: string;
    requiredRoles?: RoleName[];
    fallback?: ReactNode;
}

export function ProtectedRoute({
    children,
    requiredModule,
    requiredRoles,
    fallback = <div>Access Denied</div>
}: ProtectedRouteProps) {
    const { isAuthenticated, isLoading } = useAuth();
    const { hasModuleAccess, hasRole } = usePermission();

    if (isLoading) {
        return <div>Loading...</div>;
    }

    if (!isAuthenticated) {
        // Redirect to login or show login form
        return <div>Please log in</div>;
    }

    // Check module access
    if (requiredModule && !hasModuleAccess(requiredModule)) {
        return <>{fallback}</>;
    }

    // Check role access
    if (requiredRoles && !hasRole(requiredRoles)) {
        return <>{fallback}</>;
    }

    return <>{children}</>;
}
