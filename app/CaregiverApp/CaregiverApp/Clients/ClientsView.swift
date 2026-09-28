import SwiftUI

struct ClientsView: View {
    @State private var showProfile = false
    @State private var unreadCounts: [Int: Int] = [:]  // clientId -> unread count
    @EnvironmentObject var staffVM: StaffViewModel
    @EnvironmentObject var shiftVM: ShiftDataViewModel
    @EnvironmentObject var authVM: AuthViewModel
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let current = shiftVM.current {
                        ForEach(current.clients) { client in
                            NavigationLink(destination: ClientDetailView(client: client)) {
                                clientCard(client, unreadCount: unreadCounts[client.id] ?? 0)
                            }
                            .buttonStyle(PlainButtonStyle())
                        }
                    } else if shiftVM.isLoading {
                        ProgressView("Loading clients...")
                            .padding()
                    } else {
                        Text("No clients assigned")
                            .foregroundColor(.secondary)
                            .padding()
                    }
                }
                .padding()
            }
            .background(Color("AppBackground").ignoresSafeArea())
            .navigationTitle("Clients")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button(action: { showProfile = true }) {
                        Image(systemName: "person.crop.circle")
                            .font(.title2)
                            .foregroundColor(Color("AccentColor"))
                    }
                }
            }
            .navigationDestination(isPresented: $showProfile) {
                if let staff = staffVM.staff {
                    ProfileView(staff: staff)
                } else {
                    ProgressView("Loading profile...")
                }
            }
            .task {
                await loadUnreadCounts()
            }
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.willEnterForegroundNotification)) { _ in
                Task { await loadUnreadCounts() }
            }
            .onReceive(NotificationCenter.default.publisher(for: .updatesReadStatusChanged)) { _ in
                Task { await loadUnreadCounts() }
            }
        }
    }
    
    private func loadUnreadCounts() async {
        guard let token = authVM.currentToken(),
              let clients = shiftVM.current?.clients else { return }
        
        for client in clients {
            do {
                let count = try await UpdatesService.shared.getUpdatesCount(token: token, clientId: client.id)
                await MainActor.run {
                    unreadCounts[client.id] = count
                }
            } catch {
                print("Failed to get unread count for client \(client.id): \(error)")
            }
        }
    }
    
    private func clientCard(_ client: ShiftClient, unreadCount: Int) -> some View {
        HStack(spacing: 16) {
            RemoteImageView(url: client.profileImageURL)
                .aspectRatio(contentMode: .fill)
                .frame(width: 70, height: 70)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            
            Text("\(client.firstName) \(client.lastName)")
                .font(.system(size: 25, weight: .bold))
                .foregroundColor(Color("DefaultTextColor"))
            
            Spacer()
            
            // Unread updates badge
            if unreadCount > 0 {
                Text("\(unreadCount)")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(.white)
                    .frame(width: 24, height: 24)
                    .background(Circle().fill(Color("SuccessCustom")))
            }
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 20)
                .fill(Color("CardBackground"))
        )
    }
}
