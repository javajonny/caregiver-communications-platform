import SwiftUI

struct UpdatesView: View {
    let client: ShiftClient
    
    @State private var updates: [ClientUpdateResponse] = []
    @State private var isLoading = true
    @State private var showCreateSheet = false
    @State private var newUpdateContent = ""
    @State private var isSubmitting = false
    @State private var showProfile = false
    @State private var readUpdateIds: Set<Int> = []  // Track locally marked as read
    
    @EnvironmentObject var authVM: AuthViewModel
    @EnvironmentObject var staffVM: StaffViewModel
    
    var body: some View {
        ZStack {
            Color("AppBackground").ignoresSafeArea()
            
            if isLoading {
                ProgressView("Loading updates...")
            } else if updates.isEmpty {
                VStack(spacing: 16) {
                    Image(systemName: "megaphone")
                        .font(.system(size: 60))
                        .foregroundColor(.gray.opacity(0.5))
                    Text("No updates yet")
                        .font(.system(size: 18))
                        .foregroundColor(.secondary)
                }
            } else {
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(updates) { update in
                            updateCard(update)
                        }
                    }
                    .padding()
                }
            }
            
            // FAB
            VStack {
                Spacer()
                HStack {
                    Spacer()
                    Button(action: { showCreateSheet = true }) {
                        Image(systemName: "plus.circle")
                            .font(.system(size: 60, weight: .bold))
                            .foregroundColor(Color("AccentColor"))
                    }
                    .padding(.trailing, 20)
                    .padding(.bottom, 20)
                }
            }
        }
        .navigationTitle("Updates")
        .navigationBarTitleDisplayMode(.large)
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
        .sheet(isPresented: $showCreateSheet) {
            createUpdateSheet
        }
        .task {
            await loadUpdates()
        }
    }
    
    // MARK: - Update Card
    
    private func updateCard(_ update: ClientUpdateResponse) -> some View {
        let isRead = update.isRead || readUpdateIds.contains(update.id)
        
        return Button(action: {
            if !isRead {
                Task { await markAsRead(update) }
            }
        }) {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("\(update.authorName ?? "Unknown") · \(update.formattedDate)")
                        .font(.system(size: 15, weight: .bold))
                        .foregroundColor(Color("DefaultTextColor"))
                    
                    Spacer()
                    
                    // Blue dot for unread
                    if !isRead {
                        Circle()
                            .fill(Color("SuccessCustom"))
                            .frame(width: 22, height: 22)
                    }
                }
                
                Text(update.content)
                    .font(.system(size: 15, weight: .regular))
                    .foregroundColor(Color("DefaultTextColor").opacity(0.8))
                    .multilineTextAlignment(.leading)
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 16)
                    .fill(Color("CardBackground"))
            )
        }
        .buttonStyle(PlainButtonStyle())
    }
    
    // MARK: - Create Sheet
    
    private var createUpdateSheet: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 16) {
                Text("New Update for \(client.firstName)")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(Color("DefaultTextColor"))
                
                ZStack(alignment: .topLeading) {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color("GreyBackground"))
                        .frame(minHeight: 150)
                    
                    if newUpdateContent.isEmpty {
                        Text("What's the update?")
                            .foregroundColor(.gray)
                            .padding(.horizontal, 16)
                            .padding(.vertical, 12)
                    }
                    
                    TextEditor(text: $newUpdateContent)
                        .padding(8)
                        .background(Color.clear)
                        .frame(minHeight: 150)
                        .scrollContentBackground(.hidden)
                }
                
                Spacer()
            }
            .padding()
            .background(Color("AppBackground").ignoresSafeArea())
            .navigationTitle("New Update")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        newUpdateContent = ""
                        showCreateSheet = false
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Post") {
                        Task { await submitUpdate() }
                    }
                    .disabled(newUpdateContent.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isSubmitting)
                }
            }
        }
        .presentationDetents([.medium])
    }
    
    // MARK: - Actions
    
    private func loadUpdates() async {
        guard let token = authVM.currentToken() else {
            isLoading = false
            return
        }
        
        do {
            updates = try await UpdatesService.shared.getUpdates(token: token, clientId: client.id)
        } catch {
            print("Failed to load updates: \(error)")
        }
        
        isLoading = false
    }
    
    private func submitUpdate() async {
        guard let token = authVM.currentToken() else { return }
        
        let content = newUpdateContent.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !content.isEmpty else { return }
        
        isSubmitting = true
        
        do {
            let newUpdate = try await UpdatesService.shared.createUpdate(
                token: token,
                clientId: client.id,
                content: content
            )
            updates.insert(newUpdate, at: 0)
            newUpdateContent = ""
            showCreateSheet = false
        } catch {
            print("Failed to create update: \(error)")
        }
        
        isSubmitting = false
    }
    
    private func markAsRead(_ update: ClientUpdateResponse) async {
        guard let token = authVM.currentToken() else { return }
        
        do {
            try await UpdatesService.shared.markAsRead(
                token: token,
                clientId: client.id,
                updateId: update.id
            )
            // Update local state immediately for responsive UI
            readUpdateIds.insert(update.id)
            
            // Notify other views to refresh counts
            await MainActor.run {
                NotificationCenter.default.post(name: .updatesReadStatusChanged, object: nil)
            }
        } catch {
            print("Failed to mark as read: \(error)")
        }
    }
}

// MARK: - Notification Names

extension Notification.Name {
    static let updatesReadStatusChanged = Notification.Name("updatesReadStatusChanged")
}
