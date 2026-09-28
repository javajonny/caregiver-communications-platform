import Foundation

struct BehaviorRecordRequest: Codable {
    let shiftId: Int
    let staffId: Int
    let clientId: Int
    let behaviorTypeId: Int
    let recordedValue: Int
    let notes: String?
    
    enum CodingKeys: String, CodingKey {
        case shiftId = "shift_id"
        case staffId = "staff_id"
        case clientId = "client_id"
        case behaviorTypeId = "behavior_type_id"
        case recordedValue = "recorded_value"
        case notes
    }
}

struct BehaviorRecordResponse: Codable {
    let id: Int
    let shiftId: Int
    let staffId: Int
    let clientId: Int
    let behaviorTypeId: Int
    let recordedValue: Int
    let recordedAt: String
    let notes: String?
    
    enum CodingKeys: String, CodingKey {
        case id
        case shiftId = "shift_id"
        case staffId = "staff_id"
        case clientId = "client_id"
        case behaviorTypeId = "behavior_type_id"
        case recordedValue = "recorded_value"
        case recordedAt = "recorded_at"
        case notes
    }
}

final class BehaviorTrackingService {
    private let baseURL: String = {
        #if targetEnvironment(simulator)
        return "https://localhost:8443"
        #else
        return "https://\(AuthService.localIP()):8443"
        #endif
    }()
    private let session: URLSession
    
    init() {
        let delegate = SelfSignedCertificateDelegate()
        self.session = URLSession(configuration: .default, delegate: delegate, delegateQueue: nil)
    }
    
    func recordBehavior(
        token: String,
        shiftId: Int,
        staffId: Int,
        clientId: Int,
        behaviorTypeId: Int,
        recordedValue: Int = 1,
        notes: String? = nil
    ) async throws -> BehaviorRecordResponse {
        guard let url = URL(string: "\(baseURL)/behavior-tracking") else {
            throw URLError(.badURL)
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = BehaviorRecordRequest(
            shiftId: shiftId,
            staffId: staffId,
            clientId: clientId,
            behaviorTypeId: behaviorTypeId,
            recordedValue: recordedValue,
            notes: notes
        )
        
        request.httpBody = try JSONEncoder().encode(body)
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        if checkSessionExpired(httpResponse) { throw URLError(.userAuthenticationRequired) }
        
        guard (200...299).contains(httpResponse.statusCode) else {
            if let errorText = String(data: data, encoding: .utf8) {
                throw NSError(domain: "BehaviorTrackingService", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: errorText])
            }
            throw URLError(.badServerResponse)
        }
        
        return try JSONDecoder().decode(BehaviorRecordResponse.self, from: data)
    }
}
