

interface ConfirmationModalProps {
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
    onCancel: () => void;
    confirmText?: string;
    cancelText?: string;
    variant?: 'danger' | 'primary' | 'warning';
    isLoading?: boolean;
    error?: string;
    disableConfirm?: boolean;
}

export function ConfirmationModal({
    isOpen,
    title,
    message,
    onConfirm,
    onCancel,
    confirmText = 'Confirm',
    cancelText = 'Cancel',
    variant = 'primary',
    isLoading = false,
    error,
    disableConfirm = false
}: ConfirmationModalProps) {
    if (!isOpen) return null;

    const getBtnClass = () => {
        switch (variant) {
            case 'danger': return 'btn-danger-solid';
            case 'warning': return 'btn-warning';
            default: return 'btn-primary';
        }
    };

    return (
        <div className="modal-overlay" onClick={isLoading ? undefined : onCancel}>
            <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '400px' }}>
                <h3 style={{ marginTop: 0, color: variant === 'danger' ? '#d32f2f' : 'inherit' }}>
                    {title}
                </h3>
                <p style={{ color: '#555', lineHeight: '1.5' }}>
                    {message}
                </p>

                {error && (
                    <div className="alert-danger" style={{ marginTop: '16px', fontSize: '14px' }}>
                        {error}
                    </div>
                )}

                <div className="form-actions" style={{ marginTop: '24px' }}>
                    <button
                        type="button"
                        className="btn-secondary"
                        onClick={onCancel}
                        disabled={isLoading}
                    >
                        {cancelText}
                    </button>
                    <button
                        type="button"
                        className={`btn ${getBtnClass()}`}
                        onClick={onConfirm}
                        disabled={isLoading || disableConfirm}
                    >
                        {isLoading ? 'Processing...' : confirmText}
                    </button>
                </div>
            </div>
        </div>
    );
}
