import SwiftUI

struct ContentView: View {
    @StateObject private var staffVM = StaffViewModel()
    @StateObject private var authVM = AuthViewModel()
    @StateObject private var sessionManager = SessionTimeoutManager()
    @State private var showUnreadShifts = false
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        ZStack {
            Group {
                if authVM.isAuthenticated {
                    MainTabView()
                        .environmentObject(staffVM)
                        .environmentObject(authVM)
                        .environmentObject(sessionManager)
                        .task {
                            staffVM.authVM = authVM
                            await staffVM.loadStaff(token: authVM.currentToken())
                            // Start session timeout monitoring
                            sessionManager.startMonitoring()
                            // Show unread shifts modal after login
                            showUnreadShifts = true
                        }
                        .sheet(isPresented: $showUnreadShifts) {
                            UnreadShiftsView()
                                .environmentObject(authVM)
                        }
                } else {
                    NavigationView { LoginView() }
                        .environmentObject(authVM)
                        .onAppear { sessionManager.stopMonitoring() }
                }
            }
            
            // Timeout warning overlay
            if sessionManager.showTimeoutWarning {
                TimeoutWarningView(
                    remainingSeconds: sessionManager.remainingSeconds,
                    onContinue: { sessionManager.recordActivity() }
                )
            }
        }
        // Handle app lifecycle for background timeout
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active {
                sessionManager.handleAppDidBecomeActive()
            } else if newPhase == .inactive || newPhase == .background {
                sessionManager.handleAppWillResignActive()
            }
        }
        // Listen for session expiration from API calls (401) or client timer
        .onReceive(NotificationCenter.default.publisher(for: .sessionDidExpire)) { _ in
            Task { await authVM.logout(reason: "session_expired") }
        }
        .onReceive(NotificationCenter.default.publisher(for: .sessionDidTimeout)) { _ in
            Task { await authVM.logout(reason: "client_timeout") }
        }
    }
}

// MARK: - Timeout Warning View

struct TimeoutWarningView: View {
    let remainingSeconds: Int
    let onContinue: () -> Void
        
    var body: some View {
        ZStack {
            Color.black.opacity(0.75)
                .ignoresSafeArea()
            
            VStack(spacing: 24) {
                Image(systemName: "clock.badge.exclamationmark")
                    .font(.system(size: 56))
                    .foregroundColor(.orange)
                
                Text("Session Timeout Warning")
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundColor(.primary)
                
                Text("You will be logged out in **\(remainingSeconds)** seconds due to inactivity.")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                
                Button(action: onContinue) {
                    Text("Continue Session")
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(Color("AccentColor"))
                        .cornerRadius(12)
                }
                .padding(.top, 8)
            }
            .padding(32)
            .background(
                RoundedRectangle(cornerRadius: 24)
                    .fill(Color(.systemBackground))
            )
            .padding(.horizontal, 40)
        }
    }
}

#Preview {
    ContentView()
}
