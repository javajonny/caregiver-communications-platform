import Foundation

/// Global notification for session expiration
extension Notification.Name {
    static let sessionDidExpire = Notification.Name("sessionDidExpire")
    static let userDidMakeAPICall = Notification.Name("userDidMakeAPICall")
}

/// Check HTTP response for 401 and post session expiration notification
/// Also posts activity notification for successful user-initiated calls to reset session timer
/// - Parameters:
///   - response: The HTTP response to check
///   - isBackgroundCall: Set to true for auto-refresh/background calls that shouldn't reset the session timer
/// - Returns: true if session expired (401), caller should stop processing
func checkSessionExpired(_ response: HTTPURLResponse, isBackgroundCall: Bool = false) -> Bool {
    if response.statusCode == 401 {
        Task { @MainActor in
            NotificationCenter.default.post(name: .sessionDidExpire, object: nil)
        }
        return true
    }
    
    // Only reset timer for user-initiated calls, not background auto-refresh
    if !isBackgroundCall && (200...299).contains(response.statusCode) {
        Task { @MainActor in
            NotificationCenter.default.post(name: .userDidMakeAPICall, object: nil)
        }
    }
    
    return false
}
