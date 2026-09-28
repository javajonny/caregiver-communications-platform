import SwiftUI

@MainActor
final class AuthViewModel: ObservableObject {
    // Secure storage keys
    private let keychainService = "com.caregiverApp.service"
    private let keychainAccount = "authToken"
    
    // Insecure storage for non-sensitive data
    @AppStorage("tokenExpiresAt") private var storedExpiresAt: String?
    @AppStorage("idleTimeoutMinutes") private var idleTimeoutMinutes: Int = 10
    @AppStorage("staffId") private var storedStaffId: Int = 0

    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    @Published var mustChangePassword: Bool = false
    
    // Temporary storage for force-change flow
    private var tempToken: String?
    private var tempPassword: String?

    private let service = AuthService()

    var isAuthenticated: Bool {
        guard let token = currentToken(), !token.isEmpty else { return false }
        
        // Check if token has expired
        if let expiresAtString = storedExpiresAt,
           let expiresAt = ISO8601DateFormatter().date(from: expiresAtString),
           Date() >= expiresAt {
            // Token has expired
            clearSession()
            return false
        }
        
        // If we are pending a password change, we are not fully authenticated for the UI
        if mustChangePassword {
            return false
        }
        
        return true
    }

    func login(email: String, password: String) async {
        errorMessage = nil
        isLoading = true
        mustChangePassword = false
        tempToken = nil
        tempPassword = nil
        
        defer { isLoading = false }

        do {
            let response = try await service.login(email: email, password: password)
            
            if response.mustChangePassword {
                // Do NOT save to keychain yet. Trigger force change UI.
                mustChangePassword = true
                tempToken = response.accessToken
                tempPassword = password // Cache old password for calculation
                
                // Store non-sensitive metadata for when we eventually complete login
                storedExpiresAt = response.absoluteExpiresAt
                idleTimeoutMinutes = response.idleTimeoutMinutes
            } else {
                // Standard login
                finalizeLogin(response.accessToken, expiresAt: response.absoluteExpiresAt, idleTimeout: response.idleTimeoutMinutes)
            }
        } catch {
            if let err = error as? LocalizedError, let desc = err.errorDescription {
                errorMessage = desc
            } else {
                errorMessage = "Login failed. Please try again."
            }
        }
    }
    
    func changePassword(old: String, new: String) async {
        // determine if this is a forced change (using tempToken) or voluntary (using keychain token)
        let tokenToUse = tempToken ?? currentToken()
        
        guard let token = tokenToUse else {
            errorMessage = "Session error. Please login again."
            return
        }
        
        isLoading = true
        errorMessage = nil
        
        do {
            try await service.changePassword(token: token, old: old, new: new)
            
            if mustChangePassword {
                // Success! Finalize the login.
                if let t = tempToken {
                    finalizeLogin(t, expiresAt: storedExpiresAt ?? "", idleTimeout: idleTimeoutMinutes)
                }
                mustChangePassword = false
                tempToken = nil
                tempPassword = nil
            } else {
                // Voluntary change. Stay logged in.
            }
            
        } catch {
             if let err = error as? LocalizedError, let desc = err.errorDescription {
                errorMessage = desc
            } else {
                errorMessage = "Password change failed."
            }
        }
        
        isLoading = false
    }
    
    // Helper to supply the cached password for forced updates
    func getTempPassword() -> String? {
        return tempPassword
    }

    private func finalizeLogin(_ token: String, expiresAt: String, idleTimeout: Int) {
        // Save securely to Keychain
        KeychainHelper.standard.save(token, service: keychainService, account: keychainAccount)
        storedExpiresAt = expiresAt
        idleTimeoutMinutes = idleTimeout
    }

    func logout(reason: String? = nil) async {
        // Try to logout on server
        if let token = currentToken() {
            try? await service.logout(token: token, reason: reason)
        }
        clearSession()
    }
    
    private func clearSession() {
        // Remove from Keychain
        KeychainHelper.standard.delete(service: keychainService, account: keychainAccount)
        
        storedExpiresAt = nil
        storedStaffId = 0
        errorMessage = nil
        mustChangePassword = false
        tempToken = nil
        tempPassword = nil
    }
    
    func currentToken() -> String? {
        return KeychainHelper.standard.read(service: keychainService, account: keychainAccount)
    }
    func currentStaffId() -> Int { storedStaffId }
    func setStaffId(_ id: Int) { storedStaffId = id }
}
