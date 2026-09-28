import Foundation

final class TaskService {
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
    
    struct TaskStatusRequest: Codable {
        let shiftId: Int
        let taskId: Int
        let shiftPositionId: Int
        let statusId: Int
        let scheduledStartTime: String?
        let scheduledEndTime: String?
        
        enum CodingKeys: String, CodingKey {
            case shiftId = "shift_id"
            case taskId = "task_id"
            case shiftPositionId = "shift_position_id"
            case statusId = "status_id"
            case scheduledStartTime = "scheduled_start_time"
            case scheduledEndTime = "scheduled_end_time"
        }
    }
    
    struct TaskStatusUpdateRequest: Codable {
        let statusId: Int
        
        enum CodingKeys: String, CodingKey {
            case statusId = "status_id"
        }
    }
    
    func createOrUpdateTaskStatus(token: String, shiftId: Int, taskId: Int, shiftPositionId: Int, statusId: Int) async throws {
        // Task statuses are auto-created when shifts are created or staff are assigned
        // This function only updates existing task statuses
        guard let getUrl = URL(string: "\(baseURL)/shifts/\(shiftId)/task-status") else {
            throw TaskServiceError.invalidURL
        }
        
        var getRequest = URLRequest(url: getUrl)
        getRequest.httpMethod = "GET"
        getRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let (data, response) = try await urlSession.data(for: getRequest)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw TaskServiceError.invalidResponse
        }
        if checkSessionExpired(httpResponse) { throw TaskServiceError.unhandledStatus(401) }
        
        // Parse existing statuses
        let statuses = try JSONDecoder().decode([TaskStatusResponse].self, from: data)
        
        // Find status matching BOTH taskId AND shiftPositionId (a task can exist for multiple positions)
        guard let existingStatus = statuses.first(where: { $0.taskId == taskId && $0.shiftPositionId == shiftPositionId }) else {
            throw TaskServiceError.taskStatusNotFound
        }
        
        // Update existing task status
        try await updateTaskStatus(token: token, statusId: existingStatus.id, newStatusId: statusId)
    }
    
    private func updateTaskStatus(token: String, statusId: Int, newStatusId: Int) async throws {
        guard let url = URL(string: "\(baseURL)/shifts/task-status/\(statusId)") else {
            throw TaskServiceError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = TaskStatusUpdateRequest(statusId: newStatusId)
        request.httpBody = try JSONEncoder().encode(body)
        
        let (_, response) = try await urlSession.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw TaskServiceError.invalidResponse
        }
        if checkSessionExpired(httpResponse) { throw TaskServiceError.unhandledStatus(401) }
        
        guard httpResponse.statusCode == 200 else {
            throw TaskServiceError.unhandledStatus(httpResponse.statusCode)
        }
    }
    
    struct TaskStatusResponse: Codable {
        let id: Int
        let taskId: Int
        let shiftPositionId: Int
        
        enum CodingKeys: String, CodingKey {
            case id
            case taskId = "task_id"
            case shiftPositionId = "shift_position_id"
        }
    }
    
    // MARK: - Custom Task Creation
    
    struct TaskCreateRequest: Codable {
        let name: String
        let description: String?
        let categoryId: Int?
        let estimatedDurationMinutes: Int?
        
        enum CodingKeys: String, CodingKey {
            case name, description
            case categoryId = "category_id"
            case estimatedDurationMinutes = "estimated_duration_minutes"
        }
    }
    
    struct TaskCreateResponse: Codable {
        let id: Int
        let name: String
    }
    
    struct AssignTaskRequest: Codable {
        let shiftPositionId: Int
        let taskId: Int
        let isCustom: Bool
        
        enum CodingKeys: String, CodingKey {
            case shiftPositionId = "shift_position_id"
            case taskId = "task_id"
            case isCustom = "is_custom"
        }
    }
    
    func fetchTaskCategories(token: String) async throws -> [TaskCategory] {
        // Backend router has prefix /shifts, so categories live at /shifts/task-categories
        guard let url = URL(string: "\(baseURL)/shifts/task-categories") else {
            throw TaskServiceError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let (data, response) = try await urlSession.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw TaskServiceError.invalidResponse
        }
        if checkSessionExpired(httpResponse) { throw TaskServiceError.unhandledStatus(401) }
        
        guard httpResponse.statusCode == 200 else {
            throw TaskServiceError.unhandledStatus(httpResponse.statusCode)
        }
                
        return try JSONDecoder().decode([TaskCategory].self, from: data)
    }
    
    func createTask(token: String, name: String, description: String?, categoryId: Int?, estimatedDurationMinutes: Int?) async throws -> Int {
        // Task creation endpoint is /shifts/tasks due to router prefix
        guard let url = URL(string: "\(baseURL)/shifts/tasks") else {
            throw TaskServiceError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = TaskCreateRequest(
            name: name,
            description: description,
            categoryId: categoryId,
            estimatedDurationMinutes: estimatedDurationMinutes
        )
        request.httpBody = try JSONEncoder().encode(body)
        
        let (data, response) = try await urlSession.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw TaskServiceError.invalidResponse
        }
        if checkSessionExpired(httpResponse) { throw TaskServiceError.unhandledStatus(401) }
        
        guard httpResponse.statusCode == 201 || httpResponse.statusCode == 200 else {
            throw TaskServiceError.unhandledStatus(httpResponse.statusCode)
        }
        
        let result = try JSONDecoder().decode(TaskCreateResponse.self, from: data)
        return result.id
    }
    
    func assignTaskToPosition(token: String, positionId: Int, taskId: Int, isCustom: Bool = false) async throws {
        // Position assignment endpoint is /shifts/position-tasks due to router prefix
        guard let url = URL(string: "\(baseURL)/shifts/position-tasks") else {
            throw TaskServiceError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = AssignTaskRequest(
            shiftPositionId: positionId,
            taskId: taskId,
            isCustom: isCustom
        )
        request.httpBody = try JSONEncoder().encode(body)
        
        let (_, response) = try await urlSession.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw TaskServiceError.invalidResponse
        }
        if checkSessionExpired(httpResponse) { throw TaskServiceError.unhandledStatus(401) }
        
        guard httpResponse.statusCode == 201 || httpResponse.statusCode == 200 else {
            throw TaskServiceError.unhandledStatus(httpResponse.statusCode)
        }
    }

    // MARK: - Shift-only Custom Task
    // Creates a task and immediately links it to the current shift via backend logic (non-recurring)
    func createCustomTask(token: String, name: String, description: String?, categoryId: Int?, estimatedDurationMinutes: Int?) async throws -> Int {
        guard let url = URL(string: "\(baseURL)/shifts/custom-tasks") else {
            throw TaskServiceError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = TaskCreateRequest(
            name: name,
            description: description,
            categoryId: categoryId,
            estimatedDurationMinutes: estimatedDurationMinutes
        )
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await urlSession.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else { throw TaskServiceError.invalidResponse }
        if checkSessionExpired(httpResponse) { throw TaskServiceError.unhandledStatus(401) }
        guard (200...201).contains(httpResponse.statusCode) else { throw TaskServiceError.unhandledStatus(httpResponse.statusCode) }
        let result = try JSONDecoder().decode(TaskCreateResponse.self, from: data)
        return result.id
    }
    
    // MARK: - Delete Custom Task
    func deleteCustomTask(token: String, statusId: Int) async throws {
        guard let url = URL(string: "\(baseURL)/shifts/task-status/\(statusId)") else {
            throw TaskServiceError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Change status to "deleted" (status_id = 4)
        // Only send status_id to avoid updating other fields with invalid values
        let body: [String: Int] = ["status_id": 4]
        request.httpBody = try JSONEncoder().encode(body)
        
        let (_, response) = try await urlSession.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw TaskServiceError.invalidResponse
        }
        if checkSessionExpired(httpResponse) { throw TaskServiceError.unhandledStatus(401) }
        
        guard httpResponse.statusCode == 200 else {
            throw TaskServiceError.unhandledStatus(httpResponse.statusCode)
        }
    }
}

enum TaskServiceError: Error, LocalizedError {
    case invalidURL
    case invalidResponse
    case unhandledStatus(Int)
    case taskStatusNotFound
    
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid task service URL."
        case .invalidResponse: return "Invalid server response."
        case .unhandledStatus(let code): return "Unexpected status code: \(code)."
        case .taskStatusNotFound: return "Task status not found. This task may not be assigned to your position."
        }
    }
}
