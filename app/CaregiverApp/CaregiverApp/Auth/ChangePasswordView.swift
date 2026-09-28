import SwiftUI

struct ChangePasswordView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @Environment(\.dismiss) var dismiss
    
    // Voluntary mode
    @State private var oldPassword: String = ""
    @State private var newPassword: String = ""
    @State private var confirmPassword: String = ""
    
    var isForced: Bool {
        return authVM.mustChangePassword
    }
    
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Instructions")) {
                    Text(isForced 
                         ? "For security, you must change your password.\nNew password must be at least 8 characters and include uppercase, lowercase, digit, and special character."
                         : "Enter your current password and a new secure password.\nNew password must be at least 8 characters and include uppercase, lowercase, digit, and special character.).")
                        .font(.body)
                        .foregroundColor(Color("DefaultTextColor"))
                        //.foregroundColor(.secondary)
                }
                .foregroundColor(Color("DefaultTextColor"))
                
                Section(header: Text("Current Password")) {
                    SecureField("Old Password", text: $oldPassword)
                }
                .foregroundColor(Color("DefaultTextColor"))
                
                Section(header: Text("New Password")) {
                    SecureField("New Password", text: $newPassword)
                    SecureField("Confirm New Password", text: $confirmPassword)
                }
                .foregroundColor(Color("DefaultTextColor"))
                
                if let error = authVM.errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.red)
                    }
                }
                
                // Button Section - positioned under fields but custom styled
                Section {
                    Button(action: changePassword) {
                        if authVM.isLoading {
                            ProgressView()
                                .tint(.white)
                        } else {
                            Text("Change Password")
                                .bold()
                        }
                    }
                    .font(.system(size: 20, weight: .semibold))
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(isValid ? Color("DefaultTextColor") : Color.gray)
                    .foregroundColor(.white)
                    .cornerRadius(16)
                }
                .listRowBackground(Color.clear) // Removes the white cell background
                .listRowInsets(EdgeInsets()) // Removes default cell padding allowing full width
                .disabled(authVM.isLoading || !isValid)
            }
            .navigationTitle(isForced ? "Update Password" : "Change Password")
            .interactiveDismissDisabled(isForced)
            .toolbar {
                if !isForced {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") {
                            dismiss()
                        }
                    }
                }
            }
        }
    }
    
    var isValid: Bool {
        if oldPassword.isEmpty { return false }
        return !newPassword.isEmpty && newPassword == confirmPassword && newPassword.count >= 6
    }
    
    func changePassword() {
        Task {
            // Always use the user-entered old password
            await authVM.changePassword(old: oldPassword, new: newPassword)
            if !authVM.mustChangePassword && authVM.errorMessage == nil {
                dismiss()
            }
        }
    }
}
