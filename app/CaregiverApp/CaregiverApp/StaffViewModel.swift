import SwiftUI

@MainActor
final class StaffViewModel: ObservableObject {
    @Published var staff: Staff? = nil
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    
    private let service = StaffService()
    weak var authVM: AuthViewModel?

    func loadStaff(token: String?) async {
        guard let token = token, !token.isEmpty else {
            errorMessage = "No authentication token available"
            return
        }
        
        isLoading = true
        errorMessage = nil
        
        defer { isLoading = false }
        
        do {
            let fetchedStaff = try await service.fetchCurrentStaff(token: token)
            self.staff = fetchedStaff
            // Store staff ID for behavior tracking
            authVM?.setStaffId(fetchedStaff.id)
        } catch StaffServiceError.unauthorized {
            // Session expired on backend - trigger logout
            print("Session expired (401) - logging out")
            await authVM?.logout()
        } catch {
            errorMessage = "Failed to load profile: \(error.localizedDescription)"
            print("Failed to load staff: \(error)")
        }
    }
}

