import Foundation

struct ShiftSummary: Codable, Identifiable {
    let id: Int
    let programLocationId: Int?
    let groupNumber: Int?
    let startDate: String
    let startTime: String
    let endDate: String
    let endTime: String

    enum CodingKeys: String, CodingKey {
        case id
        case programLocationId = "program_location_id"
        case groupNumber = "group_number"
        case startDate = "start_date"
        case startTime = "start_time"
        case endDate = "end_date"
        case endTime = "end_time"
    }
}

struct PositionSummary: Codable {
    let id: Int
    let name: String?
}

struct ShiftTaskItem: Codable, Identifiable {
    let id: Int
    let name: String
    let statusId: Int?
    let scheduledStartTime: String?
    let scheduledEndTime: String?
    let isCustom: Bool

    enum CodingKeys: String, CodingKey {
        case id, name
        case statusId = "status_id"
        case scheduledStartTime = "scheduled_start_time"
        case scheduledEndTime = "scheduled_end_time"
        case isCustom = "is_custom"
    }
}

struct BehaviorConfigItem: Codable, Identifiable {
    let id: Int
    let behaviorTypeId: Int
    let behaviorName: String
    let targetValue: Int?
    let currentCount: Int

    enum CodingKeys: String, CodingKey {
        case id
        case behaviorTypeId = "behavior_type_id"
        case behaviorName = "behavior_name"
        case targetValue = "target_value"
        case currentCount = "current_count"
    }
}

struct ShiftClient: Codable, Identifiable {
    let id: Int
    let firstName: String
    let lastName: String
    let profileImageURL: URL?
    let behaviors: [BehaviorConfigItem]

    enum CodingKeys: String, CodingKey {
        case id
        case firstName = "first_name"
        case lastName = "last_name"
        case profileImageURL = "profile_image_url"
        case behaviors
    }
}

struct TaskCategory: Codable, Identifiable {
    let id: Int
    let name: String
    let description: String?
    let isActive: Bool

    enum CodingKeys: String, CodingKey {
        case id, name, description
        case isActive = "is_active"
    }
}

struct FormField: Codable, Identifiable {
    let id: String
    let type: String
    let label: String
    let required: Bool
    let fieldType: String?
    let showFieldsIf: String?
    let childFields: [FormField]?

    enum CodingKeys: String, CodingKey {
        case id, type, label, required
        case fieldType = "field_type"
        case showFieldsIf = "show_fields_if"
        case childFields = "child_fields"
    }
}

struct FormSchema: Codable {
    let type: String
    let fields: [FormField]
}

struct LogCategory: Codable, Identifiable {
    let id: Int
    let key: String
    let name: String
    let description: String?
    let displayOrder: Int
    let isActive: Bool
    let formSchema: FormSchema?
    let icon: String

    enum CodingKeys: String, CodingKey {
        case id, key, name, description, icon
        case displayOrder = "display_order"
        case isActive = "is_active"
        case formSchema = "form_schema"
    }
}

struct ShiftDailyLog: Codable, Identifiable {
    let id: Int
    let shiftId: Int
    let staffId: Int?
    let staffName: String?
    let categoryId: Int?
    let payload: [String: JSONValue]?
    let createdAt: String?
    let shiftStartTime: String?
    let shiftEndTime: String?
    let shiftDate: String?

    enum CodingKeys: String, CodingKey {
        case id
        case shiftId = "shift_id"
        case staffId = "staff_id"
        case staffName = "staff_name"
        case categoryId = "category_id"
        case payload
        case createdAt = "created_at"
        case shiftStartTime = "shift_start_time"
        case shiftEndTime = "shift_end_time"
        case shiftDate = "shift_date"
    }
}

// Lightweight JSON value to decode payloads with arbitrary shapes
enum JSONValue: Codable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let b = try? container.decode(Bool.self) {
            self = .bool(b)
        } else if let n = try? container.decode(Double.self) {
            self = .number(n)
        } else if let s = try? container.decode(String.self) {
            self = .string(s)
        } else if let arr = try? container.decode([JSONValue].self) {
            self = .array(arr)
        } else if let obj = try? container.decode([String: JSONValue].self) {
            self = .object(obj)
        } else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported JSON value")
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let s): try container.encode(s)
        case .number(let n): try container.encode(n)
        case .bool(let b): try container.encode(b)
        case .object(let obj): try container.encode(obj)
        case .array(let arr): try container.encode(arr)
        case .null: try container.encodeNil()
        }
    }
}

// MARK: - Shift Assignment and Time Info

struct AssignmentInfo: Codable {
    let id: Int
    let endedAt: String?
    let endStatusId: Int?
    let hasEnded: Bool
    
    enum CodingKeys: String, CodingKey {
        case id
        case endedAt = "ended_at"
        case endStatusId = "end_status_id"
        case hasEnded = "has_ended"
    }
}

struct TimeInfo: Codable {
    let minutesUntilEnd: Int
    let shiftEnded: Bool
    let inGracePeriod: Bool
    
    enum CodingKeys: String, CodingKey {
        case minutesUntilEnd = "minutes_until_end"
        case shiftEnded = "shift_ended"
        case inGracePeriod = "in_grace_period"
    }
}

struct CurrentShiftResponse: Codable {
    let shift: ShiftSummary
    let position: PositionSummary
    let assignment: AssignmentInfo
    let timeInfo: TimeInfo
    let tasks: [ShiftTaskItem]
    let clients: [ShiftClient]
    
    enum CodingKeys: String, CodingKey {
        case shift, position, assignment
        case timeInfo = "time_info"
        case tasks, clients
    }
}
struct UnreadShift: Codable, Identifiable {
    let shiftId: Int
    let programLocationId: Int
    let programLocationName: String
    let startDate: String
    let startTime: String
    let endDate: String
    let endTime: String
    let logCount: Int
    let hoursSinceEnded: Double
    
    var id: Int { shiftId }
    
    enum CodingKeys: String, CodingKey {
        case shiftId = "shift_id"
        case programLocationId = "program_location_id"
        case programLocationName = "program_location_name"
        case startDate = "start_date"
        case startTime = "start_time"
        case endDate = "end_date"
        case endTime = "end_time"
        case logCount = "log_count"
        case hoursSinceEnded = "hours_since_ended"
    }
}

struct MarkLogReadRequest: Codable {
    let logShiftId: Int
    let readDuringShiftId: Int?
    
    enum CodingKeys: String, CodingKey {
        case logShiftId = "log_shift_id"
        case readDuringShiftId = "read_during_shift_id"
    }
}

// MARK: - End Shift Models

struct EndShiftTaskExplanation: Codable {
    let taskId: Int
    let explanation: String
    
    enum CodingKeys: String, CodingKey {
        case taskId = "task_id"
        case explanation
    }
}

struct EndShiftRequest: Codable {
    let taskExplanations: [EndShiftTaskExplanation]
    
    enum CodingKeys: String, CodingKey {
        case taskExplanations = "task_explanations"
    }
}

struct EndShiftTaskSummary: Codable, Identifiable {
    let taskId: Int
    let taskName: String
    let isCompleted: Bool
    let explanation: String?
    
    var id: Int { taskId }
    
    enum CodingKeys: String, CodingKey {
        case taskId = "task_id"
        case taskName = "task_name"
        case isCompleted = "is_completed"
        case explanation
    }
}

struct EndShiftResponse: Codable {
    let success: Bool
    let message: String
    let shiftId: Int
    let totalTasks: Int
    let completedTasks: Int
    let incompleteTasks: Int
    let tasks: [EndShiftTaskSummary]
    
    enum CodingKeys: String, CodingKey {
        case success, message
        case shiftId = "shift_id"
        case totalTasks = "total_tasks"
        case completedTasks = "completed_tasks"
        case incompleteTasks = "incomplete_tasks"
        case tasks
    }
}