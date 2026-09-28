import Foundation

final class ShiftService {
    private let session: URLSession
    private let baseURL: URL

    init() {
        let config = URLSessionConfiguration.default
        let delegate = SelfSignedCertificateDelegate()
        self.session = URLSession(configuration: config, delegate: delegate, delegateQueue: nil)
        #if targetEnvironment(simulator)
        self.baseURL = URL(string: "https://localhost:8443")!
        #else
        // Use LAN IP when running on device
        let ip = AuthService.localIP() // You may have a helper; otherwise hardcode your LAN IP
        self.baseURL = URL(string: "https://\(ip):8443") ?? URL(string: "https://localhost:8443")!
        #endif
    }

    func fetchCurrentShift(token: String, isBackgroundCall: Bool = false) async throws -> CurrentShiftResponse {
        var url = baseURL
        url.append(path: "/shifts/current")

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 10
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        if checkSessionExpired(http, isBackgroundCall: isBackgroundCall) {
            throw URLError(.userAuthenticationRequired)
        }
        guard 200..<300 ~= http.statusCode else {
            if http.statusCode == 404 { throw URLError(.fileDoesNotExist) }
            throw URLError(.badServerResponse)
        }
        let decoder = JSONDecoder()
        return try decoder.decode(CurrentShiftResponse.self, from: data)
    }

    func fetchLogCategories(token: String) async throws -> [LogCategory] {
        var url = baseURL
        url.append(path: "/shifts/log-categories")

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 10
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        if checkSessionExpired(http) { throw URLError(.userAuthenticationRequired) }
        guard 200..<300 ~= http.statusCode else {
            throw URLError(.badServerResponse)
        }

        let decoder = JSONDecoder()
        return try decoder.decode([LogCategory].self, from: data)
    }

    func fetchShiftLogs(token: String, shiftId: Int) async throws -> [ShiftDailyLog] {
        var url = baseURL
        url.append(path: "/shifts/\(shiftId)/logs")

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 10
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        if checkSessionExpired(http) { throw URLError(.userAuthenticationRequired) }
        guard 200..<300 ~= http.statusCode else {
            throw URLError(.badServerResponse)
        }

        let decoder = JSONDecoder()
        return try decoder.decode([ShiftDailyLog].self, from: data)
    }

    func createShiftLog(token: String, shiftId: Int, staffId: Int?, categoryId: Int, payload: [String: JSONValue]) async throws {
        var url = baseURL
        url.append(path: "/shifts/logs")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 10
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = CreateLogRequest(
            shiftId: shiftId,
            staffId: staffId,
            categoryId: categoryId,
            payload: payload
        )

        request.httpBody = try JSONEncoder().encode(body)

        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        if checkSessionExpired(http) { throw URLError(.userAuthenticationRequired) }
        guard 200..<300 ~= http.statusCode else {
            throw URLError(.badServerResponse)
        }
    }
    
    func fetchLocationLogs(token: String, locationId: Int, groupNumber: Int?) async throws -> [ShiftDailyLog] {
        var url = baseURL
        url.append(path: "/shifts/location/\(locationId)/logs")
                
        // Add group_number as query parameter if provided
        if let groupNumber = groupNumber {
            url.append(queryItems: [URLQueryItem(name: "group_number", value: "\(groupNumber)")])
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 10
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        if checkSessionExpired(http) { throw URLError(.userAuthenticationRequired) }
        guard 200..<300 ~= http.statusCode else {
            throw URLError(.badServerResponse)
        }

        let decoder = JSONDecoder()
        let logs = try decoder.decode([ShiftDailyLog].self, from: data)
        return logs
    }
    
    func fetchUnreadShifts(token: String) async throws -> [UnreadShift] {
        var url = baseURL
        url.append(path: "/shifts/unread")
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 10
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        if checkSessionExpired(http) { throw URLError(.userAuthenticationRequired) }
        guard 200..<300 ~= http.statusCode else {
            throw URLError(.badServerResponse)
        }
        
        let decoder = JSONDecoder()
        return try decoder.decode([UnreadShift].self, from: data)
    }
    
    func markShiftAsRead(token: String, logShiftId: Int, readDuringShiftId: Int?) async throws {
        var url = baseURL
        url.append(path: "/shifts/mark-read")
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 10
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = MarkLogReadRequest(
            logShiftId: logShiftId,
            readDuringShiftId: readDuringShiftId
        )
        
        request.httpBody = try JSONEncoder().encode(body)
        
        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        if checkSessionExpired(http) { throw URLError(.userAuthenticationRequired) }
        guard 200..<300 ~= http.statusCode else {
            throw URLError(.badServerResponse)
        }
    }
    
    func endShift(token: String, shiftId: Int, explanations: [EndShiftTaskExplanation]) async throws -> EndShiftResponse {
        var url = baseURL
        url.append(path: "/shifts/\(shiftId)/end")
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 15
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = EndShiftRequest(taskExplanations: explanations)
        request.httpBody = try JSONEncoder().encode(body)
        
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        if checkSessionExpired(http) { throw URLError(.userAuthenticationRequired) }
        guard 200..<300 ~= http.statusCode else {
            throw URLError(.badServerResponse)
        }
        
        let decoder = JSONDecoder()
        return try decoder.decode(EndShiftResponse.self, from: data)
    }
}

private struct CreateLogRequest: Codable {
    let shiftId: Int
    let staffId: Int?
    let categoryId: Int
    let payload: [String: JSONValue]

    enum CodingKeys: String, CodingKey {
        case shiftId = "shift_id"
        case staffId = "staff_id"
        case categoryId = "category_id"
        case payload
    }
}
