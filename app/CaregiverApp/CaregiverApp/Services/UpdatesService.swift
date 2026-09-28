import Foundation

// MARK: - Models

struct ClientUpdateResponse: Codable, Identifiable {
    let id: Int
    let clientId: Int
    let createdBy: Int
    let content: String
    let isArchived: Bool
    let createdAt: String
    let authorName: String?
    let isRead: Bool
    
    enum CodingKeys: String, CodingKey {
        case id
        case clientId = "client_id"
        case createdBy = "created_by"
        case content
        case isArchived = "is_archived"
        case createdAt = "created_at"
        case authorName = "author_name"
        case isRead = "is_read"
    }
    
    var formattedDate: String {
        // Parse date and format as: "Aug 26, 8:56 AM"
        let outputFormatter = DateFormatter()
        outputFormatter.dateFormat = "MMM d, h:mm a"
        
        // Try parsing with DateFormatter for format: 2025-11-10T22:00:00
        let inputFormatter = DateFormatter()
        inputFormatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        inputFormatter.locale = Locale(identifier: "en_US_POSIX")
        
        if let date = inputFormatter.date(from: createdAt) {
            return outputFormatter.string(from: date)
        }
        
        // Try with fractional seconds: 2025-11-10T22:00:00.123456
        inputFormatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
        if let date = inputFormatter.date(from: createdAt) {
            return outputFormatter.string(from: date)
        }
        
        // Try ISO8601 with timezone
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime]
        if let date = isoFormatter.date(from: createdAt) {
            return outputFormatter.string(from: date)
        }
        
        return createdAt
    }
}

struct UpdatesCountResponse: Codable {
    let count: Int
}

// MARK: - Service

class UpdatesService {
    static let shared = UpdatesService()
    private init() {}
    
    private let baseURL: String = {
        #if targetEnvironment(simulator)
        return "https://localhost:8443"
        #else
        return "https://\(AuthService.localIP()):8443"
        #endif
    }()
    
    private lazy var urlSession: URLSession = {
        let delegate = SelfSignedCertificateDelegate()
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 10
        return URLSession(configuration: configuration, delegate: delegate, delegateQueue: nil)
    }()
    
    /// Fetch all updates for a client
    func getUpdates(token: String, clientId: Int) async throws -> [ClientUpdateResponse] {
        guard let url = URL(string: "\(baseURL)/clients/\(clientId)/updates") else {
            throw UpdatesServiceError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let (data, response) = try await urlSession.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw UpdatesServiceError.invalidResponse
        }
        if checkSessionExpired(httpResponse) { throw UpdatesServiceError.invalidResponse }
        guard httpResponse.statusCode == 200 else {
            throw UpdatesServiceError.invalidResponse
        }
        
        return try JSONDecoder().decode([ClientUpdateResponse].self, from: data)
    }
    
    /// Create a new update
    func createUpdate(token: String, clientId: Int, content: String) async throws -> ClientUpdateResponse {
        guard let url = URL(string: "\(baseURL)/clients/\(clientId)/updates") else {
            throw UpdatesServiceError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = ["content": content]
        request.httpBody = try JSONEncoder().encode(body)
        
        let (data, response) = try await urlSession.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw UpdatesServiceError.invalidResponse
        }
        if checkSessionExpired(httpResponse) { throw UpdatesServiceError.invalidResponse }
        guard httpResponse.statusCode == 200 || httpResponse.statusCode == 201 else {
            throw UpdatesServiceError.invalidResponse
        }
        
        return try JSONDecoder().decode(ClientUpdateResponse.self, from: data)
    }
    
    /// Get count of updates
    func getUpdatesCount(token: String, clientId: Int) async throws -> Int {
        guard let url = URL(string: "\(baseURL)/clients/\(clientId)/updates/count") else {
            throw UpdatesServiceError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let (data, response) = try await urlSession.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw UpdatesServiceError.invalidResponse
        }
        if checkSessionExpired(httpResponse) { throw UpdatesServiceError.invalidResponse }
        guard httpResponse.statusCode == 200 else {
            throw UpdatesServiceError.invalidResponse
        }
        
        let result = try JSONDecoder().decode(UpdatesCountResponse.self, from: data)
        return result.count
    }
    
    /// Mark an update as read
    func markAsRead(token: String, clientId: Int, updateId: Int) async throws {
        guard let url = URL(string: "\(baseURL)/clients/\(clientId)/updates/\(updateId)/read") else {
            throw UpdatesServiceError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let (_, response) = try await urlSession.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw UpdatesServiceError.invalidResponse
        }
        if checkSessionExpired(httpResponse) { throw UpdatesServiceError.invalidResponse }
        guard httpResponse.statusCode == 200 else {
            throw UpdatesServiceError.invalidResponse
        }
    }
}

// MARK: - Errors

enum UpdatesServiceError: Error, LocalizedError {
    case invalidURL
    case invalidResponse
    
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid URL"
        case .invalidResponse: return "Invalid server response"
        }
    }
}
