import SwiftUI

struct MainTabView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @EnvironmentObject var staffVM: StaffViewModel
    @StateObject private var shiftVM = ShiftDataViewModel()
    @State private var totalUnreadUpdates: Int = 0
    
    
    private var hasEnded: Bool {
        shiftVM.current?.assignment.hasEnded ?? false
    }
    
    private var inGracePeriod: Bool {
        // Shift time has passed but user hasn't submitted yet
        guard let timeInfo = shiftVM.current?.timeInfo else { return false }
        return timeInfo.shiftEnded && !hasEnded
    }
    
    var body: some View {
        Group {
            if hasEnded {
                // No tab bar - just show shift submitted view
                ShiftView()
                    .environmentObject(shiftVM)
            } else if inGracePeriod {
                // No tab bar - force EndShiftView during grace period
                EndShiftView()
                    .environmentObject(authVM)
                    .environmentObject(shiftVM)
                    .environmentObject(staffVM)
            } else {
                // Normal tab bar
                TabView {
                    ShiftView()
                        .environmentObject(shiftVM)
                        .tabItem { Label("Shift", systemImage: "pencil.and.list.clipboard") }
                    ClientsView()
                        .environmentObject(shiftVM)
                        .tabItem { Label("Clients", systemImage: "person.3.sequence") }
                        .badge(totalUnreadUpdates)
                    ChatView().tabItem { Label("Chat", systemImage: "bubble.left.and.bubble.right") }
                    EmergencyView().tabItem { Label("Emergency", systemImage: "light.beacon.max") }
                }
            }
        }
        .task {
            await shiftVM.load(token: authVM.currentToken())
            await loadTotalUnreadUpdates()
        }
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.willEnterForegroundNotification)) { _ in
            Task { await loadTotalUnreadUpdates() }
        }
        .onReceive(NotificationCenter.default.publisher(for: .updatesReadStatusChanged)) { _ in
            Task { await loadTotalUnreadUpdates() }
        }
    }
    
    private func loadTotalUnreadUpdates() async {
        guard let token = authVM.currentToken(),
              let clients = shiftVM.current?.clients else { return }
        
        var total = 0
        for client in clients {
            do {
                let count = try await UpdatesService.shared.getUpdatesCount(token: token, clientId: client.id)
                total += count
            } catch {
                print("Failed to get unread count for client \(client.id): \(error)")
            }
        }
        
        await MainActor.run {
            totalUnreadUpdates = total
        }
    }
}
