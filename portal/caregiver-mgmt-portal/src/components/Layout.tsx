import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { usePermission } from '../hooks/usePermission';

export function Layout() {
    const { user, logout } = useAuth();
    const { hasModuleAccess } = usePermission();
    const navigate = useNavigate();

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    if (!user) return null;

    return (
        <div className="layout">
            <header className="header">
                <h1>Caregiver Management</h1>
                <div className="user-info">
                    <span>{user.first_name} {user.last_name}</span>
                    <span className="role-badge">{user.role_name}</span>
                    <button onClick={handleLogout}>Logout</button>
                </div>
            </header>

            <nav className="sidebar">
                <ul>
                    <li><NavLink to="/">Dashboard</NavLink></li>
                    {hasModuleAccess('clients') && <li><NavLink to="/clients">Clients</NavLink></li>}
                    {hasModuleAccess('staff') && <li><NavLink to="/staff">Staff</NavLink></li>}
                    {hasModuleAccess('shifts') && <li><NavLink to="/shifts">Shifts</NavLink></li>}

                    {hasModuleAccess('documents') && <li><NavLink to="/documents">Documents</NavLink></li>}
                </ul>
            </nav>

            <main className="main-content">
                <Outlet />
            </main>
        </div>
    );
}
