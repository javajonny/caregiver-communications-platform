import SwiftUI

struct CategoryDocumentsView: View {
    let client: ShiftClient
    let category: DocumentCategoryAPIResponse
    
    @State private var documents: [ClientDocumentAPIResponse] = []
    @State private var showProfile = false
    @State private var isLoading = true
    @State private var errorMessage: String?
    
    @EnvironmentObject var staffVM: StaffViewModel
    @EnvironmentObject var authVM: AuthViewModel
    @EnvironmentObject var shiftVM: ShiftDataViewModel
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                if isLoading {
                    ProgressView("Loading documents...")
                        .padding()
                } else if let error = errorMessage {
                    Text(error)
                        .foregroundColor(.red)
                        .padding()
                } else if documents.isEmpty {
                    Text("No documents available")
                        .foregroundColor(.secondary)
                        .padding()
                } else {
                    // Group documents by subcategory
                    let grouped = Dictionary(grouping: documents) { doc in
                        doc.subcategoryName ?? "Other"
                    }
                    
                    // Sort subcategory keys alphabetically
                    let sortedKeys = grouped.keys.sorted()
                    
                    ForEach(sortedKeys, id: \.self) { subcategoryName in
                        // Subcategory header
                        Text(subcategoryName)
                            .font(.system(size: 18, weight: .semibold))
                            .foregroundColor(Color("DefaultTextColor").opacity(0.7))
                            .padding(.top, 8)
                        
                        // Documents in this subcategory (sorted alphabetically by name)
                        if let docs = grouped[subcategoryName] {
                            VStack(spacing: 12) {
                                ForEach(docs.sorted { $0.templateName < $1.templateName }, id: \.id) { doc in
                                    NavigationLink(destination: documentView(for: doc)) {
                                        documentButton(icon: doc.templateIcon, title: doc.templateName)
                                    }
                                    .buttonStyle(PlainButtonStyle())
                                }
                            }
                        }
                    }
                }
            }
            .padding()
        }
        .background(Color("AppBackground").ignoresSafeArea())
        .navigationTitle(category.name)
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
        .task {
            await loadDocuments()
        }
    }
    
    // MARK: - Dynamic Document View
    
    private func documentView(for doc: ClientDocumentAPIResponse) -> some View {
        DocumentView(
            title: doc.templateName,
            client: client,
            schema: doc.formSchema,
            values: doc.values,
            createdAt: doc.createdAt,
            createdByName: doc.createdByName,
            lastReviewedAt: doc.lastReviewedAt,
            lastReviewedByName: doc.lastReviewedByName,
            lastReviewChangesMade: doc.lastReviewChangesMade,
            revisionIntervalDays: doc.revisionIntervalDays
        )
    }
    
    // MARK: - Load Documents from API
    
    private func loadDocuments() async {
        guard let token = authVM.currentToken() else {
            errorMessage = "Not authenticated"
            isLoading = false
            return
        }
        
        do {
            documents = try await DocumentService.shared.getClientDocumentsByCategory(
                token: token,
                clientId: client.id,
                categoryId: category.id
            )
            isLoading = false
        } catch {
            print("Failed to load documents: \(error)")
            errorMessage = "Failed to load documents"
            isLoading = false
        }
    }
    
    // MARK: - UI Components
    
    private func documentButton(icon: String, title: String) -> some View {
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
                .fill(Color("CardBackground"))
        )
    }
}
