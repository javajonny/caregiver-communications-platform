import SwiftUI

// MARK: - Dynamic Document Renderer
// This view dynamically renders any document based on its JSONB form_schema
// Similar to SchemaFormView but read-only for viewing documents

struct DocumentView: View {
    let title: String
    let client: ShiftClient
    let schema: DocumentSchemaDefinition
    let values: [String: [String: DocumentValue]]
    let createdAt: String?
    let createdByName: String?
    let lastReviewedAt: String?
    let lastReviewedByName: String?

    let lastReviewChangesMade: Bool?
    let revisionIntervalDays: Int?
    
    @State private var showProfile = false
    @EnvironmentObject var staffVM: StaffViewModel
    @EnvironmentObject var shiftVM: ShiftDataViewModel
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Document Information Card
                documentInfoCard
                
                // Render each section from the schema
                ForEach(schema.sections) { section in
                    DocumentSectionView(
                        section: section,
                        values: values[section.key] ?? [:]
                    )
                }
            }
            .padding()
        }
        .background(Color("AppBackground").ignoresSafeArea())
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button(action: { showProfile = true }) {
                    Image(systemName: "person.crop.circle")
                        .font(.title2)
                        .foregroundColor(Color("AccentColor"))
                }
            }
        }
        .navigationDestination(isPresented: $showProfile) {
            if let staff = staffVM.staff {
                ProfileView(staff: staff)
            } else {
                ProgressView("Loading profile...")
            }
        }
    }
    
    // MARK: - Document Information Card
    
    private var documentInfoCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack(spacing: 12) {
                Image(systemName: "info.circle")
                    .font(.system(size: 30))
                    .foregroundColor(Color("DefaultTextColor"))
                Text("Document Information")
                    .font(.system(size: 25, weight: .bold))
                    .foregroundColor(Color("DefaultTextColor"))
            }
            
            // Client Name
            infoRow(label: "Individual Name", value: "\(client.firstName) \(client.lastName)")
            
            // Creation info
            infoRow(label: "Created", value: formatDateTime(createdAt))
            infoRow(label: "Created By", value: createdByName ?? "Unknown")
            
            Divider()
                .background(Color("DefaultTextColor").opacity(0.7))
            
            // Review info - always show
            // Interval info
            if let interval = revisionIntervalDays {
                infoRow(label: "Required Review Interval", value: "Every \(interval) Days")
                
                if let (dueDate, isOverdue) = nextRevisionInfo {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(isOverdue ? "Overdue Since" : "Next Revision Due")
                            .font(.system(size: 16, weight: .medium))
                            .foregroundColor(isOverdue ? Color("DeleteColor")  : Color("DefaultTextColor").opacity(0.7))
                        Text(formatDate(dueDate))
                            .font(.system(size: 16, weight: isOverdue ? .bold : .regular))
                            .foregroundColor(isOverdue ? Color("DeleteColor") : Color("DefaultTextColor"))
                    }
                }
            }
            
            
            if let reviewedAt = lastReviewedAt {
                infoRow(label: "Last Reviewed", value: formatDateTime(reviewedAt))
                infoRow(label: "Reviewed By", value: lastReviewedByName ?? "Unknown")
                
                // Show if changes were made
                if let changesMade = lastReviewChangesMade {
                    HStack(spacing: 8) {
                        Image(systemName: "pencil.circle.fill")
                            .font(.system(size: 16))
                            .foregroundColor(changesMade ? Color("OrangeColor") : Color("SuccessGreen"))
                        Text(changesMade ? "Changes were made" : "No changes were made")
                            .font(.system(size: 16, weight: .medium))
                            .foregroundColor(changesMade ? Color("OrangeColor") : Color("SuccessGreen"))
                    }
                    .padding(.top, 4)
                }
            } else {
                Text("Not yet reviewed")
                    .font(.system(size: 16))
                    .foregroundColor(Color("DefaultTextColor").opacity(0.6))
                    .italic()
            }
        }
        .padding(20)
        .background(
            RoundedRectangle(cornerRadius: 20)
                .fill(Color("CardBackground"))
        )
    }
    
    private func infoRow(label: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.system(size: 16, weight: .medium))
                .foregroundColor(Color("DefaultTextColor").opacity(0.7))
            Text(value)
                .font(.system(size: 16))
                .foregroundColor(Color("DefaultTextColor"))
        }
    }
    
    private func formatDateTime(_ isoString: String?) -> String {
        guard let isoString = isoString else { return "Unknown" }
        
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        
        // Try with fractional seconds first
        if let date = isoFormatter.date(from: isoString) {
            return formatDate(date)
        }
        
        // Try without fractional seconds
        isoFormatter.formatOptions = [.withInternetDateTime]
        if let date = isoFormatter.date(from: isoString) {
            return formatDate(date)
        }
        
        // Try simple format
        let simpleFormatter = DateFormatter()
        simpleFormatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        if let date = simpleFormatter.date(from: isoString) {
            return formatDate(date)
        }
        
        return isoString
    }
    
    private func formatDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .none
        return formatter.string(from: date)
    }
    
    private var nextRevisionInfo: (date: Date, isOverdue: Bool)? {
        guard let interval = revisionIntervalDays else { return nil }
        
        // Use last reviewed date, or created date if never reviewed
        let baseDateString = lastReviewedAt ?? createdAt
        guard let baseDate = parseDate(baseDateString) else { return nil }
        
        // Add interval
        guard let dueDate = Calendar.current.date(byAdding: .day, value: interval, to: baseDate) else { return nil }
        
        // Check if overdue (compare with now)
        let isOverdue = dueDate < Date()
        
        return (dueDate, isOverdue)
    }
    
    private func parseDate(_ isoString: String?) -> Date? {
        guard let isoString = isoString else { return nil }
        
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = isoFormatter.date(from: isoString) { return date }
        
        isoFormatter.formatOptions = [.withInternetDateTime]
        if let date = isoFormatter.date(from: isoString) { return date }
        
        let simpleFormatter = DateFormatter()
        simpleFormatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return simpleFormatter.date(from: isoString)
    }
}

// MARK: - Section View

struct DocumentSectionView: View {
    let section: DocumentSchemaSection
    let values: [String: DocumentValue]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Section header
            HStack(spacing: 12) {
                if let icon = section.icon {
                    Image(systemName: icon)
                        .font(.system(size: 30))
                        .foregroundColor(Color("DefaultTextColor"))
                }
                Text(section.title)
                    .font(.system(size: 25, weight: .bold))
                    .foregroundColor(Color("DefaultTextColor"))
            }
            
            // Render all fields from schema
            ForEach(section.fields) { field in
                DocumentFieldView(field: field, values: values)
            }
        }
        .padding(20)
        .background(
            RoundedRectangle(cornerRadius: 20)
                .fill(Color("CardBackground"))
        )
    }
}

// MARK: - Field View

struct DocumentFieldView: View {
    let field: DocumentSchemaField
    let values: [String: DocumentValue]
    
    // Check if this conditional field should be shown
    private var shouldShow: Bool {
        guard let conditional = field.conditional else { return true }
        if case .bool(let parentValue) = values[conditional] {
            return parentValue
        }
        return false
    }
    
    var body: some View {
        if shouldShow {
            VStack(alignment: .leading, spacing: 8) {
                if !field.label.isEmpty {
                    Text(field.label)
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(Color("DefaultTextColor"))
                }
                
                switch field.type {
                case "boolean":
                    booleanField
                case "text":
                    textField
                    // multilineField
                case "date":
                    dateField
                case "number":
                    numberField
                default:
                    Text("Unknown field type")
                        .foregroundColor(.secondary)
                }
            }
        }
    }
    
    private var booleanField: some View {
        let value: Bool = {
            if case .bool(let v) = values[field.key] {
                return v
            }
            return false
        }()
        
        return HStack(spacing: 8) {
            Text("Yes")
                .font(.system(size: 15, weight: .medium))
                .foregroundColor(Color("DefaultTextColor"))
                .frame(maxWidth: .infinity)
                .frame(height: 30)
                .background(value ? Color("SelectedButton") : Color("UnselectedButton"))
                .cornerRadius(20)
            
            Text("No")
                .font(.system(size: 15, weight: .medium))
                .foregroundColor(Color("DefaultTextColor"))
                .frame(maxWidth: .infinity)
                .frame(height: 30)
                .background(!value ? Color("SelectedButton") : Color("UnselectedButton"))
                .cornerRadius(20)
        }
    }
    
    private var textField: some View {
        let value: String = {
            if case .string(let v) = values[field.key] {
                return v
            }
            return ""
        }()
        
        return Text(value)
            .font(.system(size: 16))
            .foregroundColor(Color("DefaultTextColor").opacity(0.7))
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color("GreyBackground"))
            )
    }
    
    private var multilineField: some View {
        let value: String = {
            if case .string(let v) = values[field.key] {
                return v
            }
            return ""
        }()
        
        return Text(value)
            .font(.system(size: 16))
            .foregroundColor(Color("DefaultTextColor").opacity(0.8))
            .lineSpacing(4)
    }
    
    private var dateField: some View {
        let value: String = {
            if case .string(let v) = values[field.key] {
                return v
            }
            return ""
        }()
        
        return Text(value)
            .font(.system(size: 16))
            .foregroundColor(Color("DefaultTextColor").opacity(0.7))
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color("GreyBackground"))
            )
    }
    
    private var numberField: some View {
        let valueText: String = {
            if case .number(let d) = values[field.key] {
                // Display without trailing .0 for whole numbers
                if d.rounded() == d {
                    return String(Int(d))
                } else {
                    return String(d)
                }
            } else if case .string(let v) = values[field.key] {
                return v
            }
            return ""
        }()
        
        return Text(valueText)
            .font(.system(size: 16))
            .foregroundColor(Color("DefaultTextColor").opacity(0.7))
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color("GreyBackground"))
            )
    }
}

// MARK: - Schema Models (matching database JSONB structure)

struct DocumentSchemaDefinition: Codable {
    let sections: [DocumentSchemaSection]
}

struct DocumentSchemaSection: Codable, Identifiable {
    let key: String
    let title: String
    let icon: String?
    let fields: [DocumentSchemaField]
    
    var id: String { key }
}

struct DocumentSchemaField: Codable, Identifiable {
    let key: String
    let label: String
    let type: String
    let readonly: Bool?
    let source: String?
    let conditional: String?
    
    var id: String { key }
}

// MARK: - Value type for document data

enum DocumentValue: Codable {
    case string(String)
    case bool(Bool)
    case number(Double)
    
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let boolValue = try? container.decode(Bool.self) {
            self = .bool(boolValue)
        } else if let stringValue = try? container.decode(String.self) {
            self = .string(stringValue)
        } else if let doubleValue = try? container.decode(Double.self) {
            self = .number(doubleValue)
        } else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Cannot decode DocumentValue")
        }
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .number(let value): try container.encode(value)
        }
    }
}

