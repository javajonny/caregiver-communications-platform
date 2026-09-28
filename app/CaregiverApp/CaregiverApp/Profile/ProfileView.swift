
import SwiftUI

struct ProfileView: View {
    let staff: Staff
    @EnvironmentObject var authVM: AuthViewModel
    @State private var showChangePasswordSheet = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            Text("Profile")
                .font(.system(size: 30, weight: .bold))
                .foregroundColor(Color("DefaultTextColor"))
                .padding(.horizontal)
            
            ProfileHeaderCard(
                profileImageURL: staff.profileImageURL,
                firstName: staff.firstName,
                lastName: staff.lastName,
                email: staff.email,
                phone: staff.workPhone
            )

            Button("Change Password", systemImage: "lock.rotation") {
                showChangePasswordSheet = true
            }
            .font(.system(size: 20, weight: .semibold))
            .frame(maxWidth: .infinity)
            .padding()
            .background(Color("DefaultTextColor"))
            .foregroundColor(.white)
            .cornerRadius(16)
            .padding(.horizontal)

            Button("Logout", systemImage: "rectangle.portrait.and.arrow.right") {
                Task {
                    await authVM.logout()
                }
            }
                .font(.system(size: 20, weight: .semibold))
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color("AccentColor"))
                .foregroundColor(.white)
                .cornerRadius(16)
                .padding(.horizontal)

            Spacer()
        }
        .padding(.top, 7)
        .navigationTitle("Your Profile")
        .navigationBarTitleDisplayMode(.inline)
        .background(Color("AppBackground").ignoresSafeArea())
        .sheet(isPresented: $showChangePasswordSheet) {
            ChangePasswordView()
        }
    }
}
