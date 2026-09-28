import SwiftUI

struct LoginView: View {
    @EnvironmentObject var authVM: AuthViewModel

    @State private var email: String = ""
    @State private var password: String = ""
    @State private var showPassword: Bool = false

    private var formValid: Bool {
        email.contains("@") && password.count >= 6
    }

    var body: some View {
        ZStack {
            // Background decorative circles
            Circle()
                .fill(Color.blue.opacity(0.3))
                .frame(width: 200, height: 200)
                .offset(x: -150, y: -350)
            
            Circle()
                .fill(Color.green.opacity(0.3))
                .frame(width: 180, height: 180)
                .offset(x: 120, y: -300)
            
            Circle()
                .fill(Color.orange.opacity(0.2))
                .frame(width: 220, height: 220)
                .offset(x: -100, y: 450)
            
            Circle()
                .fill(Color.green.opacity(0.25))
                .frame(width: 190, height: 190)
                .offset(x: 130, y: 400)
            
            VStack(spacing: 30) {
                Spacer()
                
                // Login card
                VStack(spacing: 20) {
                    Text("Welcome Back")
                        .font(.system(size: 32, weight: .bold))
                        .foregroundColor(Color("DefaultTextColor"))
                        .padding(.bottom, 10)
                    
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Email")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(Color("DefaultTextColor"))

                        TextField("user@company.com", text: $email)
                            .textInputAutocapitalization(.never)
                            .keyboardType(.emailAddress)
                            .autocorrectionDisabled()
                            .padding()
                            .background(Color.white)
                            .cornerRadius(40)
                            .foregroundColor(.red.opacity(0.7))
                    }
                    
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Password")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(Color("DefaultTextColor"))

                        
                        HStack {
                            Group {
                                if showPassword {
                                    TextField("", text: $password)
                                } else {
                                    SecureField("", text: $password)
                                }
                            }
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .foregroundColor(.red.opacity(0.7))
                            
                            Button {
                                showPassword.toggle()
                            } label: {
                                Image(systemName: showPassword ? "eye.slash" : "eye")
                                    .foregroundColor(.secondary)
                            }
                        }
                        .padding()
                        .background(Color.white)
                        .cornerRadius(40)
                    }
                }
                .padding(20)
                .background(Color("CardBackground"))
                .cornerRadius(20)
                .padding(.horizontal, 20)
                
                // Login button
                Button {
                    Task { await authVM.login(email: email.trimmingCharacters(in: .whitespaces), password: password) }
                } label: {
                    HStack(spacing: 12) {
                        if authVM.isLoading {
                            ProgressView()
                                .tint(.white)
                        } else {
                            Image(systemName: "lock.open")
                                .font(.system(size: 20))
                            Text("Login")
                                .font(.system(size: 20, weight: .semibold))
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 18)
                    .background(formValid && !authVM.isLoading ? Color("AccentColor") : Color.gray)
                    .foregroundColor(.white)
                    .cornerRadius(30)
                }
                .disabled(!formValid || authVM.isLoading)
                .padding(.horizontal, 80)
                
                // Forgot password button
                Button { /* TODO: forgot password */ } label: {
                    Text("Forgot password?")
                        .font(.footnote)
                        .foregroundColor(Color("AccentColor"))
                }
                
                // Fixed height container for error message
                Group {
                    if let error = authVM.errorMessage {
                        Text(error)
                            .foregroundColor(.red)
                            .font(.footnote)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 40)
                    } else {
                        Text(" ")
                            .font(.footnote)
                    }
                }
                .frame(minHeight: 20)
                
                Spacer()
            }
        }
        .background(Color("AppBackground").ignoresSafeArea())
        .sheet(isPresented: $authVM.mustChangePassword) {
            ChangePasswordView() // EnvironmentObject authVM is inherited
                .interactiveDismissDisabled()
        }
    }
}

#Preview {
    LoginView()
        .environmentObject(AuthViewModel())
}
