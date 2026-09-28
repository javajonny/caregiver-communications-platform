import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

interface Stats {
    totalClients: number;
    totalStaff: number;
    expiredDocuments: number;
}

interface ShiftDashboardStats {
    current_task_status_counts: Record<string, number>;
    past_task_status_counts: Record<string, number>;
    past_shift_status_counts: Record<string, number>;
    current_shift_status_counts: Record<string, number>;
}

interface ExpiredDocument {
    client_id: number;
    client_name: string;
    document_id: number;
    template_name: string;
    last_review_date: string | null;
    created_at: string;
    due_date: string;
}

export function Dashboard() {
    const { user } = useAuth();
    const [stats, setStats] = useState<Stats | null>(null);
    const [shiftStats, setShiftStats] = useState<ShiftDashboardStats | null>(null);
    const [loading, setLoading] = useState(true);

    // Expired Documents Modal
    const [showExpiredModal, setShowExpiredModal] = useState(false);
    const [expiredDocs, setExpiredDocs] = useState<ExpiredDocument[]>([]);
    const [loadingExpired, setLoadingExpired] = useState(false);

    const handleFetchExpiredDocs = () => {
        if (showExpiredModal) return; // Already showing?
        setLoadingExpired(true);
        setShowExpiredModal(true);
        api.getExpiredDocuments()
            .then(data => setExpiredDocs(data))
            .catch(console.error)
            .finally(() => setLoadingExpired(false));
    };

    useEffect(() => {
        Promise.all([
            api.getStats(),
            api.getShiftDashboardStats()
        ])
            .then(([statsData, shiftStatsData]) => {
                setStats(statsData);
                setShiftStats(shiftStatsData);
            })
            .catch(console.error)
            .finally(() => setLoading(false));
    }, []);

    const getTotalAssignments = (counts: Record<string, number>) =>
        Object.values(counts).reduce((a, b) => a + b, 0);

    return (
        <div className="page">
            <h2>Welcome, {user?.first_name}!</h2>

            {loading ? (
                <p>Loading stats...</p>
            ) : (
                <>
                    {/* Basic stats */}
                    {stats && (
                        <div className="stats-grid">
                            <div className="stat-card">
                                <div className="stat-value">{stats.totalClients}</div>
                                <div className="stat-label">Clients</div>
                            </div>
                            <div className="stat-card">
                                <div className="stat-value">{stats.totalStaff}</div>
                                <div className="stat-label">Staff Members</div>
                            </div>
                            <div
                                className="stat-card"
                                style={stats.expiredDocuments > 0 ? { borderLeft: '4px solid #ff4444', cursor: 'pointer' } : {}}
                                onClick={() => stats.expiredDocuments > 0 && handleFetchExpiredDocs()}
                            >
                                <div className="stat-value" style={stats.expiredDocuments > 0 ? { color: '#ff4444' } : {}}>{stats.expiredDocuments}</div>
                                <div className="stat-label">Expired Documents (Click to View)</div>
                            </div>
                        </div>
                    )}

                    {shiftStats && (
                        <>
                            {/* Current Shift Assignments Section */}
                            <h3 style={{ marginTop: '32px' }}>
                                Current Shift Assignments ({getTotalAssignments(shiftStats.current_shift_status_counts)})
                            </h3>

                            {/* Assignment Status */}
                            <h4 style={{ marginTop: '16px', marginBottom: '8px', color: '#666' }}>Assignment Status</h4>
                            <div className="stats-grid">
                                {Object.keys(shiftStats.current_shift_status_counts).length > 0 ? (
                                    Object.entries(shiftStats.current_shift_status_counts).map(([status, count]) => (
                                        <div className="stat-card" key={status}>
                                            <div className="stat-value">{count}</div>
                                            <div className="stat-label">{status}</div>
                                        </div>
                                    ))
                                ) : (
                                    <p style={{ color: '#666' }}>No current shift assignments</p>
                                )}
                            </div>

                            {/* Task Status for Current */}
                            <h4 style={{ marginTop: '16px', marginBottom: '8px', color: '#666' }}>Task Status</h4>
                            <div className="stats-grid">
                                {Object.keys(shiftStats.current_task_status_counts).length > 0 ? (
                                    Object.entries(shiftStats.current_task_status_counts).map(([status, count]) => (
                                        <div className="stat-card" key={status}>
                                            <div className="stat-value">{count}</div>
                                            <div className="stat-label">{status}</div>
                                        </div>
                                    ))
                                ) : (
                                    <p style={{ color: '#666' }}>No tasks</p>
                                )}
                            </div>

                            {/* Past Shift Assignments Section */}
                            <h3 style={{ marginTop: '32px' }}>
                                Past Shift Assignments ({getTotalAssignments(shiftStats.past_shift_status_counts)})
                            </h3>

                            {/* Assignment Status */}
                            <h4 style={{ marginTop: '16px', marginBottom: '8px', color: '#666' }}>Assignment Status</h4>
                            <div className="stats-grid">
                                {Object.keys(shiftStats.past_shift_status_counts).length > 0 ? (
                                    Object.entries(shiftStats.past_shift_status_counts).map(([status, count]) => (
                                        <div className="stat-card" key={status}>
                                            <div className="stat-value">{count}</div>
                                            <div className="stat-label">{status}</div>
                                        </div>
                                    ))
                                ) : (
                                    <p style={{ color: '#666' }}>No past shift assignments</p>
                                )}
                            </div>

                            {/* Task Status for Past */}
                            <h4 style={{ marginTop: '16px', marginBottom: '8px', color: '#666' }}>Task Status</h4>
                            <div className="stats-grid">
                                {Object.keys(shiftStats.past_task_status_counts).length > 0 ? (
                                    Object.entries(shiftStats.past_task_status_counts).map(([status, count]) => (
                                        <div className="stat-card" key={status}>
                                            <div className="stat-value">{count}</div>
                                            <div className="stat-label">{status}</div>
                                        </div>
                                    ))
                                ) : (
                                    <p style={{ color: '#666' }}>No tasks</p>
                                )}
                            </div>
                        </>
                    )}
                </>
            )}

            {/* Expired Documents Modal */}
            {showExpiredModal && (
                <div className="modal-overlay" onClick={() => setShowExpiredModal(false)}>
                    <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '800px', width: '90%' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                            <h3 style={{ margin: 0 }}>Expired Documents</h3>
                            <button onClick={() => setShowExpiredModal(false)} className="btn-secondary" style={{ padding: '4px 8px' }}>X</button>
                        </div>

                        {loadingExpired ? (
                            <p>Loading...</p>
                        ) : (
                            <div style={{ overflowX: 'auto' }}>
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>Client</th>
                                            <th>Document</th>
                                            <th>Created</th>
                                            <th>Last Reviewed</th>
                                            <th>Due Date</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {expiredDocs.length > 0 ? (
                                            expiredDocs.map(doc => (
                                                <tr key={doc.document_id}>
                                                    <td>{doc.client_name}</td>
                                                    <td>{doc.template_name}</td>
                                                    <td>{new Date(doc.created_at).toLocaleDateString()}</td>
                                                    <td>{doc.last_review_date ? new Date(doc.last_review_date).toLocaleDateString() : '-'}</td>
                                                    <td style={{ color: '#dc3545', fontWeight: 500 }}>{new Date(doc.due_date).toLocaleDateString()}</td>
                                                </tr>
                                            ))
                                        ) : (
                                            <tr>
                                                <td colSpan={5} style={{ textAlign: 'center', padding: '20px' }}>No expired documents found.</td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        )}

                        <div style={{ marginTop: '20px', textAlign: 'right' }}>
                            <button className="btn-primary" onClick={() => setShowExpiredModal(false)}>Close</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
