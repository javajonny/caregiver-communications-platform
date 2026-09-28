import SwiftUI

struct ClientDetailView: View {
    let client: ShiftClient
    @State private var showProfile = false
    @State private var updatesCount: Int = 0
    @State private var categories: [DocumentCategoryAPIResponse] = []
    @State private var isLoadingCategories = true
    @EnvironmentObject var staffVM: StaffViewModel
    @EnvironmentObject var authVM: AuthViewModel
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                // Client header
                HStack(spacing: 12) {
                    RemoteImageView(url: client.profileImageURL)
                        .aspectRatio(contentMode: .fill)
                        .frame(width: 60, height: 60)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    
                    Text("\(client.firstName) \(client.lastName)")
                        .font(.system(size: 28, weight: .bold))
                        .foregroundColor(Color("DefaultTextColor"))
                    
                    Spacer()
                }
                .padding(.bottom, 8)
                
                // Document category buttons
                VStack(spacing: 12) {
                    // Updates (highlighted - always shown)
                    NavigationLink(destination: UpdatesView(client: client)) {
                        updatesButton
                    }
                    .buttonStyle(PlainButtonStyle())
                    
                    // Loading state for categories
                    if isLoadingCategories {
                        ProgressView("Loading categories...")
                            .padding()
                    } else {
                        // Dynamic category buttons from API
                        ForEach(categories, id: \.id) { category in
                            NavigationLink(destination: CategoryDocumentsView(client: client, category: category)) {
                                categoryButton(
                                    icon: category.icon ?? "folder",
                                    title: category.name,
                                    color: Color("CardBackground")
                                )
                            }
                            .buttonStyle(PlainButtonStyle())
                        }
                    }
                }
            }
            .padding()
        }
        .background(Color("AppBackground").ignoresSafeArea())
        .navigationTitle(client.firstName)
        .navigationBarTitleDisplayMode(.inline)
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
            await loadUpdatesCount()
            await loadCategories()
        }
    }
    

    
    // MARK: - Updates Button (highlighted style)
    
    private var updatesButton: some View {
        HStack(spacing: 16) {
            Image(systemName: "megaphone")
                .font(.system(size: 30, weight: .bold))
                .foregroundColor(Color("DefaultTextColor"))
                .frame(width: 40)
            
            Text("Updates")
                .font(.system(size: 25, weight: .bold))
                .foregroundColor(Color("DefaultTextColor"))
            
            Spacer()
            
            // Badge
            if updatesCount > 0 {
                Text("\(updatesCount)")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(.white)
                    .frame(width: 24, height: 24)
                    .background(Circle().fill(Color("SuccessCustom")))
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 20)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(updatesCount > 0 ? Color("AccentColor").opacity(0.7) : Color("CardBackground"))
        )
    }
    
    private func categoryButton(icon: String, title: String, color: Color) -> some View {
        HStack(spacing: 16) {
            Image(systemName: icon)
                .font(.system(size: 30, weight: .bold))
                .foregroundColor(Color("DefaultTextColor"))
                .frame(width: 40)
            
            Text(title)
                .font(.system(size: 25, weight: .bold))
                .foregroundColor(Color("DefaultTextColor"))
            
            Spacer()
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 20)
        .background(
            RoundedRectangle(cornerRadius: 16)
            .fill(color)
            /*
                .fill(title == "Individual" ? Color(.white).opacity(0.5) : title == "Forms" ? Color(.blue).opacity(0.5) : title == "Medical Records" ? Color(.red).opacity(0.5) : title == "Legal Records" ? Color(.black).opacity(0.5) : Color("CardBackground"))
             */
            
        )
    }
    
    private func loadUpdatesCount() async {
        guard let token = authVM.currentToken() else { return }
        
        do {
            updatesCount = try await UpdatesService.shared.getUpdatesCount(token: token, clientId: client.id)
        } catch {
            print("Failed to load updates count: \(error)")
        }
    }
    
    private func loadCategories() async {
        guard let token = authVM.currentToken() else {
            isLoadingCategories = false
            return
        }
        
        do {
            categories = try await DocumentService.shared.getDocumentCategories(token: token)
            isLoadingCategories = false
        } catch {
            print("Failed to load categories: \(error)")
            isLoadingCategories = false
        }
    }
}
