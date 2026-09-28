import Foundation

// MARK: - API Response Models

struct ClientDocumentAPIResponse: Codable {
    let id: Int
    let clientId: Int
    let templateId: Int
    let templateName: String
    let templateIcon: String
    let subcategoryId: Int?
    let subcategoryName: String?
    let revisionIntervalDays: Int
    let createdAt: String?
    let createdByName: String?
    let lastReviewedAt: String?
    let lastReviewedByName: String?
    let lastReviewChangesMade: Bool?
    let reviewCount: Int
    let formSchema: DocumentSchemaDefinition
    let values: [String: [String: DocumentValue]]
    
    enum CodingKeys: String, CodingKey {
        case id
        case clientId = "client_id"
        case templateId = "template_id"
        case templateName = "template_name"
        case templateIcon = "template_icon"
        case subcategoryId = "subcategory_id"
        case subcategoryName = "subcategory_name"
        case revisionIntervalDays = "revision_interval_days"
        case createdAt = "created_at"
        case createdByName = "created_by_name"
        case lastReviewedAt = "last_reviewed_at"
        case lastReviewedByName = "last_reviewed_by_name"
        case lastReviewChangesMade = "last_review_changes_made"
        case reviewCount = "review_count"
        case formSchema = "form_schema"
        case values
    }
}

struct DocumentSubcategoryAPIResponse: Codable {
    let id: Int
    let name: String
    let icon: String?
}

struct DocumentCategoryAPIResponse: Codable {
    let id: Int
    let name: String
    let description: String?
    let icon: String?
    let subcategories: [DocumentSubcategoryAPIResponse]
}

// MARK: - Document Service

class DocumentService {
    static let shared = DocumentService()
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
    
    /// Fetch all documents for a client, optionally filtered by category
    func getClientDocuments(
        token: String,
        clientId: Int,
        categoryId: Int? = nil
    ) async throws -> [ClientDocumentAPIResponse] {
        var urlString = "\(baseURL)/clients/\(clientId)/documents"
        if let categoryId = categoryId {
            urlString += "?category_id=\(categoryId)"
        }
        
        guard let url = URL(string: urlString) else {
            throw DocumentServiceError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let (data, response) = try await urlSession.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw DocumentServiceError.invalidResponse
        }
        if checkSessionExpired(httpResponse) { throw DocumentServiceError.unhandledStatus(401) }
        
        guard httpResponse.statusCode == 200 else {
            throw DocumentServiceError.unhandledStatus(httpResponse.statusCode)
        }
        
        let decoder = JSONDecoder()
        return try decoder.decode([ClientDocumentAPIResponse].self, from: data)
    }
    

    
    /// Fetch documents by category ID
    func getClientDocumentsByCategory(token: String, clientId: Int, categoryId: Int) async throws -> [ClientDocumentAPIResponse] {
        return try await getClientDocuments(token: token, clientId: clientId, categoryId: categoryId)
    }
    
    /// Fetch all document categories with their subcategories
    func getDocumentCategories(token: String) async throws -> [DocumentCategoryAPIResponse] {
        let urlString = "\(baseURL)/documents/categories?include_subcategories=true"
        
        guard let url = URL(string: urlString) else {
            throw DocumentServiceError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let (data, response) = try await urlSession.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw DocumentServiceError.invalidResponse
        }
        if checkSessionExpired(httpResponse) { throw DocumentServiceError.unhandledStatus(401) }
        
        guard httpResponse.statusCode == 200 else {
            throw DocumentServiceError.unhandledStatus(httpResponse.statusCode)
        }
        
        let decoder = JSONDecoder()
        return try decoder.decode([DocumentCategoryAPIResponse].self, from: data)
    }
}

// MARK: - Errors

enum DocumentServiceError: Error, LocalizedError {
    case invalidURL
    case invalidResponse
    case unhandledStatus(Int)
    
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid document service URL."
        case .invalidResponse: return "Invalid server response."
        case .unhandledStatus(let code): return "Unexpected status code: \(code)."
        }
    }
}
