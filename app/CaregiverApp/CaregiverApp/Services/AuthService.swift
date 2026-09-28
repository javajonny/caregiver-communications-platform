import Foundation

enum AuthError: LocalizedError {
    case invalidCredentials
    case network(Error)
    case invalidResponse
    case unknown

    case custom(String)

    var errorDescription: String? {
        switch self {
        case .invalidCredentials: return "Invalid email or password."
        case .network(let error): return "Network error: \(error.localizedDescription)"
        case .invalidResponse: return "Invalid server response."
        case .custom(let message): return message
        case .unknown: return "Something went wrong."
        }
    }
}

struct LoginResponse: Codable {
    let accessToken: String
    let tokenType: String
    let idleTimeoutMinutes: Int
    let absoluteExpiresAt: String
    let mustChangePassword: Bool
    
    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case tokenType = "token_type"
        case idleTimeoutMinutes = "idle_timeout_minutes"
        case absoluteExpiresAt = "absolute_expires_at"
        case mustChangePassword = "must_change_password"
    }
}

struct LoginRequest: Codable {
    let email: String
    let password: String
}

final class AuthService {
    static func localIP() -> String {
        // Physical device only. Set this to your Mac's LAN IP (`ipconfig getifaddr en0`).
        return "YOUR_MAC_IP"
    }
    
    // Environment-based URL configuration
    // Simulator: Uses localhost (shares Mac's network stack)
    // Physical Device: Uses Mac's IP on local network
    private let baseURL: String = {
        #if targetEnvironment(simulator)
        return "https://localhost:8443"
        #else
        return "https://\(AuthService.localIP()):8443"
        #endif
    }()
    
    // Custom URLSession that accepts self-signed certificates for local development
    private lazy var urlSession: URLSession = {
        let delegate = SelfSignedCertificateDelegate()
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 10
        return URLSession(configuration: configuration, delegate: delegate, delegateQueue: nil)
    }()
    
    func login(email: String, password: String) async throws -> LoginResponse {
        print("Starting login request...")
        
        guard let url = URL(string: "\(baseURL)/auth/login") else {
            print("Invalid URL")
            throw AuthError.network(NSError(domain: "Invalid URL", code: -1))
        }
        
        print("URL: \(url.absoluteString)")
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 10
        
        let loginRequest = LoginRequest(email: email, password: password)
        request.httpBody = try JSONEncoder().encode(loginRequest)
        
        print("Sending request with email: \(email)")
        
        do {
            let (data, response) = try await urlSession.data(for: request)
            
            print("Response received!")
            
            guard let httpResponse = response as? HTTPURLResponse else {
                print("Not an HTTP response")
                throw AuthError.invalidResponse
            }
            
            print("Status code: \(httpResponse.statusCode)")
            
            if let responseString = String(data: data, encoding: .utf8) {
                print("Response body: \(responseString)")
            }
            
            switch httpResponse.statusCode {
            case 200:
                let loginResponse = try JSONDecoder().decode(LoginResponse.self, from: data)
                print("Login successful!")
                return loginResponse
            case 401:
                print("Invalid credentials")
                throw AuthError.invalidCredentials
            default:
                print("Unexpected status code: \(httpResponse.statusCode)")
                throw AuthError.unknown
            }
        } catch let error as AuthError {
            throw error
        } catch {
            print("Network error: \(error.localizedDescription)")
            print("Error details: \(error)")
            throw AuthError.network(error)
        }
    }
    
    func logout(token: String, reason: String? = nil) async throws {
        var urlComponents = URLComponents(string: "\(baseURL)/auth/logout")
        
        if let reason = reason {
            urlComponents?.queryItems = [URLQueryItem(name: "reason", value: reason)]
        }
        
        guard let url = urlComponents?.url else {
            throw AuthError.network(NSError(domain: "Invalid URL", code: -1))
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let (_, response) = try await urlSession.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw AuthError.invalidResponse
        }
        
        guard httpResponse.statusCode == 204 else {
            throw AuthError.unknown
        }
    }
    
    func changePassword(token: String, old: String, new: String) async throws {
        guard let url = URL(string: "\(baseURL)/auth/change-password") else {
            throw AuthError.network(NSError(domain: "Invalid URL", code: -1))
        }
        
        struct ChangeRequest: Codable {
            let old_password: String
            let new_password: String
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let payload = ChangeRequest(old_password: old, new_password: new)
        request.httpBody = try JSONEncoder().encode(payload)
        
        let (data, response) = try await urlSession.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw AuthError.invalidResponse
        }
        
        if httpResponse.statusCode != 204 {
            // Try to parse error message from backend
            if let errorJson = try? JSONDecoder().decode([String: String].self, from: data),
               let detail = errorJson["detail"] {
                throw AuthError.custom(detail)
            }
            
            if httpResponse.statusCode == 401 {
                throw AuthError.invalidCredentials
            }
            
            throw AuthError.unknown
        }
    }
}
