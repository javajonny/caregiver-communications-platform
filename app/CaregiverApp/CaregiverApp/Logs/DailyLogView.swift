import SwiftUI

struct DailyLogView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @EnvironmentObject var shiftVM: ShiftDataViewModel
    @EnvironmentObject var staffVM: StaffViewModel

    @State private var categories: [LogCategory] = []
    @State private var logs: [ShiftDailyLog] = []
    @State private var logsByShift: [(shiftKey: String, shiftLabel: String, logs: [ShiftDailyLog])] = [] // Grouped by shift
    @State private var inputs: [Int: String] = [:] // categoryId -> text
    @State private var formData: [Int: [String: FormValue]] = [:] // categoryId -> form fields
    @State private var previousEntries: [Int: [ShiftDailyLog]] = [:] // categoryId -> all previous entries (read-only)
    @State private var expandedCategories: Set<Int> = [] // categoryId -> whether history is shown
    @State private var expandedShifts: Set<String> = [] // shiftKey -> whether logs are shown
    @State private var isLoading = false
    @State private var showAllLogs = false
    @State private var showProfile = false
    @State private var errorMessage: String?

    //TODO: use assets
    private let cardBackground = Color("CardBackground")
    private let headerTextColor = Color("DefaultTextColor")

    var body: some View {
        GeometryReader { geometry in // prevents horizontal scrolling
            ScrollView(.vertical, showsIndicators: true) {
                VStack(alignment: .leading, spacing: 20) {
                    Button(action: { withAnimation { showAllLogs.toggle() } }) {
                        HStack(spacing: 12) {
                            Image(systemName: "folder")
                                .font(.system(size: 26, weight: .semibold))
                                .foregroundColor(headerTextColor)
                            VStack(alignment: .leading, spacing: 4) {
                                Text("See All Log Notes")
                                    .font(.system(size: 22, weight: .bold))
                                    .foregroundColor(headerTextColor)
                                Text("Tap to show or hide previous entries")
                                    .font(.system(size: 14, weight: .medium))
                                    .foregroundColor(headerTextColor.opacity(0.7))
                            }
                            Spacer()
                            Image(systemName: showAllLogs ? "chevron.up" : "chevron.down")
                                .foregroundColor(headerTextColor)
                        }
                        .padding()
                        .frame(maxWidth: .infinity)
                        .background(Color("AllLogNotesCardColor"))
                        .cornerRadius(18)
                    }

                    if showAllLogs {
                        if logsByShift.isEmpty {
                            Text("No log notes yet.")
                                .foregroundColor(.secondary)
                                .padding(.horizontal)
                        } else {
                            VStack(spacing: 20) {
                                ForEach(logsByShift, id: \.shiftKey) { shiftGroup in
                                    VStack(alignment: .leading, spacing: 12) {
                                        // Shift header - clickable
                                        Button(action: { 
                                            withAnimation {
                                                if expandedShifts.contains(shiftGroup.shiftKey) {
                                                    expandedShifts.remove(shiftGroup.shiftKey)
                                                } else {
                                                    expandedShifts.insert(shiftGroup.shiftKey)
                                                }
                                            }
                                        }) {
                                            HStack(spacing: 12) {
                                                Image(systemName: "calendar")
                                                    .font(.system(size: 26, weight: .semibold))
                                                    .foregroundColor(Color("DefaultTextColor"))
                                                VStack(alignment: .leading, spacing: 2) {
                                                    Text(getShiftDate(from: shiftGroup.shiftLabel))
                                                        .font(.system(size: 22, weight: .bold))
                                                    .foregroundColor(Color("DefaultTextColor"))
                                                    Text(getShiftTime(from: shiftGroup.shiftLabel))
                                                        .font(.system(size: 16, weight: .medium))
                                                        .foregroundColor(Color("DefaultTextColor").opacity(0.8))
                                                }
                                                Spacer()
                                                Image(systemName: expandedShifts.contains(shiftGroup.shiftKey) ? "chevron.up" : "chevron.down")
                                                    .foregroundColor(Color("DefaultTextColor"))
                                            }
                                            .padding()
                                            .frame(maxWidth: .infinity, alignment: .leading)
                                            .background(Color("GreyBackground"))
                                            .cornerRadius(12)
                                        }
                                        
                                        // Logs for this shift - only show when expanded
                                        if expandedShifts.contains(shiftGroup.shiftKey) {
                                            ForEach(shiftGroup.logs) { log in
                                                logRow(log)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    if let msg = errorMessage {
                        Text(msg)
                            .foregroundColor(Color("DeleteColor"))
                            .padding(.horizontal)
                    }

                    ForEach(categories.sorted(by: { $0.displayOrder < $1.displayOrder })) { category in
                        categoryCard(category)
                    }
                }
                .padding(.horizontal)
                .padding(.vertical, 16)
                .frame(width: geometry.size.width, alignment: .leading)
            }
        }
        .navigationTitle("Daily Log Notes")
        .navigationBarTitleDisplayMode(.large)
        .task { await loadData() }
        .refreshable { await loadData() }
        .disabled(isLoading)
        .background(Color("AppBackground"))
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
                    .environmentObject(authVM)
            } else {
                ProgressView("Loading profile...")
            }
        }
    }

    private func categoryCard(_ category: LogCategory) -> some View {
        let allPreviousEntries = previousEntries[category.id] ?? []
        let currentInput = inputs[category.id] ?? ""
        let isExpanded = expandedCategories.contains(category.id)

        return VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 20) {
                Image(systemName: category.icon.isEmpty ? "folder" : category.icon)
                    .font(.system(size: 35, weight: .bold))
                    .foregroundColor(headerTextColor)
                Text(category.name)
                    .font(.system(size: 30, weight: .bold))
                    .foregroundColor(headerTextColor)
                Spacer()
            }

            if let desc = category.description {
                Text(desc)
                    .font(.system(size: 15, weight: .medium))
                    .foregroundColor(headerTextColor)
                    .fixedSize(horizontal: false, vertical: true)
            }

            
            // Dynamic form or text input
            SchemaFormView(
                category: category,
                input: Binding(
                    get: { currentInput },
                    set: { inputs[category.id] = $0 }
                ),
                formData: Binding(
                    get: { formData[category.id] ?? [:] },
                    set: { formData[category.id] = $0 }
                ),
                onSubmit: {
                    Task { await submit(category) }
                },
                isLoading: isLoading
            )

            // Show previous entries toggle
            if !allPreviousEntries.isEmpty {
                Button(action: { withAnimation { 
                    if isExpanded {
                        expandedCategories.remove(category.id)
                    } else {
                        expandedCategories.insert(category.id)
                    }
                }}) {
                    HStack(spacing: 8) {
                        Text("Previous Entries (\(allPreviousEntries.count))")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(Color("DefaultTextColor"))
                        Spacer()
                        Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(Color("DefaultTextColor"))
                    }
                    .padding(10)
                    .background(Color("GreyBackground"))
                    .cornerRadius(8)
                }

                if isExpanded {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(allPreviousEntries) { entry in
                            VStack(alignment: .leading, spacing: 4) {
                                if let payload = entry.payload {
                                    Text(formatPayloadForDisplay(payload))
                                        .font(.system(size: 14, weight: .regular))
                                        .foregroundColor(Color("DefaultTextColor"))
                                }
                                HStack {
                                    if let staffName = entry.staffName {
                                        Text(staffName)
                                            .font(.system(size: 11, weight: .medium))
                                            .foregroundColor(.gray)
                                    }
                                    Spacer()
                                    if let ts = entry.createdAt {
                                        Text(formattedDate(ts))
                                            .font(.system(size: 11, weight: .light))
                                            .foregroundColor(.gray)
                                    }
                                }
                            }
                            .padding(10)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color("GreyBackground"))
                            .cornerRadius(8)
                        }
                    }
                }
            }
        }
        .padding(16)
        .background(cardBackground)
        .cornerRadius(20)
    }
    private func logRow(_ log: ShiftDailyLog) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            if let category = categories.first(where: { $0.id == log.categoryId }) {
                Text(category.name)
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(headerTextColor)
            }
            if let payload = log.payload {
                Text(formatPayloadForDisplay(payload))
                    .font(.system(size: 15))
                    .foregroundColor(Color("DefaultTextColor"))
            }
            HStack {
                if let staffName = log.staffName {
                    Text(staffName)
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(.secondary)
                }
                Spacer()
                if let ts = log.createdAt {
                    Text(formattedDate(ts))
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(Color("GreyBackground")))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.gray.opacity(0.2), lineWidth: 1)
        )
    }

    // MARK: - Data
    private func loadData() async {
        guard let token = authVM.currentToken(), 
              let shift = shiftVM.current?.shift,
              let locationId = shift.programLocationId else {
            return
        }
                
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        
        do {
            async let cats = ShiftService().fetchLogCategories(token: token)
            async let currentShiftLogs = ShiftService().fetchShiftLogs(token: token, shiftId: shift.id)
            async let allLocationLogs = ShiftService().fetchLocationLogs(token: token, locationId: locationId, groupNumber: shift.groupNumber)
            
            categories = try await cats
            let currentLogs = try await currentShiftLogs
            logs = try await allLocationLogs
            
            // Group current shift entries by category for "Previous Entries" in each category card
            var entriesByCategory: [Int: [ShiftDailyLog]] = [:]
            let sortedCurrentLogs = currentLogs.sorted { ($0.createdAt ?? "") > ($1.createdAt ?? "") }
            for log in sortedCurrentLogs {
                if let cid = log.categoryId {
                    if entriesByCategory[cid] == nil {
                        entriesByCategory[cid] = []
                    }
                    entriesByCategory[cid]?.append(log)
                }
            }
            previousEntries = entriesByCategory
            
            // Group all location logs by shift for "See All Log Notes"
            groupLogsByShift(logs)
            
        } catch is CancellationError {
            // Ignore cancellation errors - these occur when user refreshes while loading
            return
        } catch {
            errorMessage = "Failed to load logs: \(error.localizedDescription)"
        }
    }
    
    private func groupLogsByShift(_ logs: [ShiftDailyLog]) {        
        var grouped: [Int: [ShiftDailyLog]] = [:]
        
        for log in logs {
            if grouped[log.shiftId] == nil {
                grouped[log.shiftId] = []
            }
            grouped[log.shiftId]?.append(log)
        }
        
        // Convert to array with shift labels, sorted by shift start date/time descending
        logsByShift = grouped.compactMap { shiftId, logs -> (String, String, [ShiftDailyLog])? in
            guard let firstLog = logs.first else { return nil }
            
            let shiftKey = "\(shiftId)"
            let shiftLabel = formatShiftLabel(firstLog)
            
            return (shiftKey, shiftLabel, logs)
        }.sorted { first, second in
            // Sort by the shift's actual start date/time
            guard let log1 = first.logs.first,
                  let log2 = second.logs.first,
                  let date1Str = log1.shiftDate,
                  let date2Str = log2.shiftDate,
                  let time1Str = log1.shiftStartTime,
                  let time2Str = log2.shiftStartTime else {
                return false
            }
            
            // Combine date and time for comparison
            let dateTimeFormatter = DateFormatter()
            dateTimeFormatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
            
            let dateTime1 = "\(date1Str) \(time1Str)"
            let dateTime2 = "\(date2Str) \(time2Str)"
            
            guard let dt1 = dateTimeFormatter.date(from: dateTime1),
                  let dt2 = dateTimeFormatter.date(from: dateTime2) else {
                return false
            }
            
            return dt1 > dt2
        }
    }
    
    private func formatShiftLabel(_ log: ShiftDailyLog) -> String {
        guard let shiftDate = log.shiftDate,
              let startTime = log.shiftStartTime,
              let endTime = log.shiftEndTime else {
            return "Shift \(log.shiftId)"
        }
        
        // Parse date
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        guard let date = dateFormatter.date(from: shiftDate) else {
            return "Shift \(log.shiftId)"
        }
        
        // Format date
        let displayDateFormatter = DateFormatter()
        displayDateFormatter.dateFormat = "EEEE, MMM d"
        let dateString = displayDateFormatter.string(from: date)
        
        // Format times (extract hour from HH:MM:SS)
        let timeFormatter = DateFormatter()
        timeFormatter.dateFormat = "HH:mm:ss"
        
        let displayTimeFormatter = DateFormatter()
        displayTimeFormatter.dateFormat = "ha"
        
        var startDisplay = ""
        var endDisplay = ""
        
        if let start = timeFormatter.date(from: startTime) {
            startDisplay = displayTimeFormatter.string(from: start).lowercased()
        }
        if let end = timeFormatter.date(from: endTime) {
            endDisplay = displayTimeFormatter.string(from: end).lowercased()
        }
        
        return "\(dateString) · \(startDisplay) - \(endDisplay)"
    }
    
    // Extract date part from shift label
    private func getShiftDate(from label: String) -> String {
        let components = label.split(separator: "·")
        return components.first?.trimmingCharacters(in: .whitespaces) ?? label
    }
    
    // Extract time part from shift label
    private func getShiftTime(from label: String) -> String {
        let components = label.split(separator: "·")
        if components.count > 1 {
            return components[1].trimmingCharacters(in: .whitespaces)
        }
        return ""
    }

    private func submit(_ category: LogCategory) async {
        guard let token = authVM.currentToken(), let shiftId = shiftVM.current?.shift.id else { return }
        
        let fields = formData[category.id] ?? [:]
        
        // Require form data
        guard !fields.isEmpty else { return }
        
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        
        do {
            let staffId = staffVM.staff?.id
            
            // Convert form data to JSONValue for payload
            var jsonPayload: [String: JSONValue] = [:]
            for (key, value) in fields {
                switch value {
                case .string(let s):
                    jsonPayload[key] = .string(s)
                case .bool(let b):
                    // Convert boolean to Yes/No string for backend compatibility
                    jsonPayload[key] = .string(b ? "Yes" : "No")
                case .date(let d):
                    jsonPayload[key] = .string(d)
                case .number(let n):
                    jsonPayload[key] = .number(n)
                }
            }
            
            try await ShiftService().createShiftLog(
                token: token,
                shiftId: shiftId,
                staffId: staffId,
                categoryId: category.id,
                payload: jsonPayload
            )
            
            inputs[category.id] = ""
            formData[category.id] = [:]
            await loadData()
        } catch {
            errorMessage = "Failed to save entry: \(error.localizedDescription)"
        }
    }
    
    // Format ISO8601 date string to hh:mm am/pm with robust parsing (handles microseconds)
    private func formattedDate(_ isoString: String) -> String {
        // Primary: ISO8601 with fractional seconds
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = isoFormatter.date(from: isoString) {
            return displayTime(from: date)
        }

        // Fallback: ISO8601 without fractional seconds
        isoFormatter.formatOptions = [.withInternetDateTime]
        if let date = isoFormatter.date(from: isoString) {
            return displayTime(from: date)
        }

        // Fallback: manual formatter for microseconds (e.g., 2025-12-10T20:53:46.030325)
        let microFormatter = DateFormatter()
        microFormatter.locale = Locale(identifier: "en_US_POSIX")
        microFormatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
        if let date = microFormatter.date(from: isoString) {
            return displayTime(from: date)
        }

        return isoString
    }

    // Convert Date to MM/dd/yy h:mma format (e.g., 01/02/26 3:30pm)
    private func displayTime(from date: Date) -> String {
        let displayFormatter = DateFormatter()
        displayFormatter.dateFormat = "MM/dd/yy h:mma"
        return displayFormatter.string(from: date).lowercased()
    }
    
    // Format payload dictionary for human-readable display
    private func formatPayloadForDisplay(_ payload: [String: JSONValue]) -> String {
        var lines: [String] = []
        
        for (key, value) in payload.sorted(by: { $0.key < $1.key }) {
            let label = key.replacingOccurrences(of: "_", with: " ").capitalized
            let formattedValue = formatJSONValue(value)
            lines.append("\(label): \(formattedValue)")
        }
        
        return lines.joined(separator: "\n")
    }
    
    // Recursively format JSONValue for display
    private func formatJSONValue(_ value: JSONValue) -> String {
        switch value {
        case .string(let s):
            // Handle Yes/No strings
            if s == "Yes" || s == "No" {
                return s
            }
            // Try to format as date/time if it looks like ISO8601
            if s.contains("T") || s.contains(":") {
                if let date = parseDateTime(s) {
                    let formatter = DateFormatter()
                    formatter.dateStyle = .short
                    formatter.timeStyle = .short
                    return formatter.string(from: date)
                }
            }
            return s
        case .number(let n):
            return String(n)
        case .bool(let b):
            return b ? "Yes" : "No"
        case .object(let obj):
            var parts: [String] = []
            for (k, v) in obj.sorted(by: { $0.key < $1.key }) {
                let label = k.replacingOccurrences(of: "_", with: " ").capitalized
                parts.append("\(label): \(formatJSONValue(v))")
            }
            return parts.joined(separator: ", ")
        case .array(let arr):
            return arr.map { formatJSONValue($0) }.joined(separator: ", ")
        case .null:
            return "N/A"
        }
    }
    
    // Parse datetime string
    private func parseDateTime(_ str: String) -> Date? {
        let isoFormatter = ISO8601DateFormatter()
        
        // Try with fractional seconds and timezone
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = isoFormatter.date(from: str) {
            return date
        }
        
        // Try with timezone but no fractional seconds
        isoFormatter.formatOptions = [.withInternetDateTime]
        if let date = isoFormatter.date(from: str) {
            return date
        }
        
        // Try without timezone - add Z to make it UTC
        let hasTZ = str.contains("Z") || str.contains("+") || (str.count > 10 && str.dropFirst(10).contains("-"))
        if !hasTZ {
            let withZ = str + "Z"
            if let date = isoFormatter.date(from: withZ) {
                return date
            }
        }
        
        return nil
    }
}

#Preview {
    DailyLogView()
        .environmentObject(AuthViewModel())
        .environmentObject(ShiftDataViewModel())
        .environmentObject(StaffViewModel())
}
