import Foundation

final class StaffService {
    // Environment-based URL (matches AuthService)
    private let baseURL: String = {
        #if targetEnvironment(simulator)
        return "https://localhost:8443"
        #else
        return "https://\(AuthService.localIP()):8443"
        #endif
    }()
    
    // Custom URLSession that accepts self-signed certificates
    private lazy var urlSession: URLSession = {
        let delegate = SelfSignedCertificateDelegate()
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 10
        return URLSession(configuration: configuration, delegate: delegate, delegateQueue: nil)
    }()
    
    func fetchCurrentStaff(token: String) async throws -> Staff {
        guard let url = URL(string: "\(baseURL)/auth/me") else {
            throw StaffServiceError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 10
        
        let (data, response) = try await urlSession.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw StaffServiceError.invalidResponse
        }
        
        switch httpResponse.statusCode {
        case 200:
            return try JSONDecoder().decode(Staff.self, from: data)
        case 401:
            _ = checkSessionExpired(httpResponse)  // Post notification for global logout
            throw StaffServiceError.unauthorized
        default:
            throw StaffServiceError.unhandledStatus(httpResponse.statusCode)
        }
    }
}

enum StaffServiceError: Error, LocalizedError {
    case invalidURL
    case invalidResponse
    case unauthorized
    case unhandledStatus(Int)
    
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid staff service URL."
        case .invalidResponse: return "Invalid server response."
        case .unauthorized: return "Unauthorized staff request."
        case .unhandledStatus(let code): return "Unexpected status code: \(code)."
        }
    }
}
