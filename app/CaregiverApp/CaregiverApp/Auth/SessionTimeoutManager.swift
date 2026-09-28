import SwiftUI
import Combine

/// HIPAA-compliant client-side session timeout manager
/// Proactively clears PHI after inactivity - doesn't wait for server 401
@MainActor
final class SessionTimeoutManager: ObservableObject {
    /// Session timeout in minutes - read from shared storage (updated by AuthViewModel)
    @AppStorage("idleTimeoutMinutes") private var idleTimeoutMinutes: Int = 10
    
    @Published var showTimeoutWarning = false
    @Published var remainingSeconds: Int = 60
    
    private var lastActivityDate = Date()
    private var checkTimer: Timer?
    private var countdownTimer: Timer?
    private var apiActivityCancellable: AnyCancellable?
    
    /// Warning shown 60 seconds before logout
    private let warningBeforeLogoutSeconds = 60
    
    // MARK: - Activity Tracking
    
    /// Call this on any user interaction to reset the inactivity timer
    func recordActivity() {
        lastActivityDate = Date()
        
        // If warning was showing, hide it and stop countdown
        if showTimeoutWarning {
            showTimeoutWarning = false
            stopCountdown()
        }
    }
    
    // MARK: - Timer Control
    
    func startMonitoring() {
        recordActivity()
        
        // Listen for API activity to reset timer
        apiActivityCancellable = NotificationCenter.default
            .publisher(for: .userDidMakeAPICall)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in
                self?.recordActivity()
            }
        
        // Check every 5 seconds for inactivity
        checkTimer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.checkInactivity()
            }
        }
    }
    
    func stopMonitoring() {
        checkTimer?.invalidate()
        checkTimer = nil
        stopCountdown()
        showTimeoutWarning = false
    }
    
    private func stopCountdown() {
        countdownTimer?.invalidate()
        countdownTimer = nil
    }
    
    // MARK: - Inactivity Check
    
    private func checkInactivity() {
        let idleSeconds = Date().timeIntervalSince(lastActivityDate)
        let timeoutSeconds = Double(idleTimeoutMinutes * 60)
        let warningThreshold = timeoutSeconds - Double(warningBeforeLogoutSeconds)
        
        if idleSeconds >= timeoutSeconds {
            // Time's up - trigger logout
            triggerTimeout()
        } else if idleSeconds >= warningThreshold && !showTimeoutWarning {
            // Show warning with countdown
            showWarning(secondsRemaining: Int(timeoutSeconds - idleSeconds))
        }
    }
    
    private func showWarning(secondsRemaining: Int) {
        showTimeoutWarning = true
        remainingSeconds = secondsRemaining
        
        // Start countdown
        countdownTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self = self else { return }
                self.remainingSeconds -= 1
                if self.remainingSeconds <= 0 {
                    self.triggerTimeout()
                }
            }
        }
    }
    
    private func triggerTimeout() {
        stopMonitoring()
        
        // Post notification - ContentView will handle logout
        NotificationCenter.default.post(name: .sessionDidTimeout, object: nil)
    }
    
    // MARK: - App Lifecycle (background handling)
    
    func handleAppWillResignActive() {
        // Store current activity time when going to background
        // (already stored in lastActivityDate)
    }
    
    func handleAppDidBecomeActive() {
        // Check if we should have timed out while in background
        checkInactivity()
    }
}

// MARK: - Notification

extension Notification.Name {
    static let sessionDidTimeout = Notification.Name("sessionDidTimeout")
}
