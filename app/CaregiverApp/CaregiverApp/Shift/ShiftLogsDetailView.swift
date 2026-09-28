import SwiftUI

struct ShiftLogsDetailView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @Environment(\.dismiss) var dismiss
    
    let shift: UnreadShift
    let onMarkAsRead: () async -> Void
    
    @State private var logs: [ShiftDailyLog] = []
    @State private var categories: [LogCategory] = []
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var sliderOffset: CGFloat = 0
    @State private var isMarking = false
    
    private let shiftService = ShiftService()
    private let sliderWidth: CGFloat = 300
    private let sliderHeight: CGFloat = 60
    
    var body: some View {
        ZStack {
            Color("AppBackground").ignoresSafeArea()
            
            VStack(spacing: 0) {
                // Header
                VStack(alignment: .leading, spacing: 8) {
                    Text(shift.programLocationName)
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundColor(Color("DefaultTextColor"))
                    
                    HStack {
                        Image(systemName: "calendar")
                            .font(.subheadline)
                        Text(formatShiftDate(shift.startDate, shift.startTime, shift.endDate, shift.endTime))
                            .font(.subheadline)
                    }
                    .foregroundColor(Color(.white))
                    
                    HStack {
                        Image(systemName: "doc.text")
                            .font(.subheadline)
                        Text("\(shift.logCount) log\(shift.logCount == 1 ? "" : "s")")
                            .font(.subheadline)
                    }
                    .foregroundColor(Color("AccentColor"))
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(Color("CardBackground"))
                
                Divider()
                
                // Logs content
                if isLoading {
                    Spacer()
                    ProgressView("Loading logs...")
                    Spacer()
                } else if let error = errorMessage {
                    Spacer()
                    VStack(spacing: 16) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.system(size: 40))
                            .foregroundColor(.orange)
                        Text("Failed to load logs")
                            .font(.headline)
                        Text(error)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                    Spacer()
                } else if logs.isEmpty {
                    Spacer()
                    Text("No logs found")
                        .foregroundColor(.secondary)
                    Spacer()
                } else {
                    ScrollView {
                        VStack(spacing: 12) {
                            ForEach(logs) { log in
                                LogEntryCard(log: log, categories: categories)
                            }
                        }
                        .padding()
                        .padding(.bottom, 100) // Space for slider
                    }
                }
                
                Spacer()
            }
            
            // Slider to mark as read at bottom
            VStack {
                Spacer()
                
                SlideToMarkReadButton(
                    sliderOffset: $sliderOffset,
                    isMarking: $isMarking,
                    onComplete: {
                        Task {
                            await onMarkAsRead()
                            dismiss()
                        }
                    }
                )
                .padding(.horizontal)
                .padding(.bottom, 30)
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await loadLogs()
        }
    }
    
    private func loadLogs() async {
        isLoading = true
        errorMessage = nil
        
        guard let token = authVM.currentToken() else {
            errorMessage = "Not authenticated"
            isLoading = false
            return
        }
        
        do {
            async let logsData = shiftService.fetchShiftLogs(token: token, shiftId: shift.shiftId)
            async let categoriesData = shiftService.fetchLogCategories(token: token)
            
            logs = try await logsData
            categories = try await categoriesData
            isLoading = false
        } catch {
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }
    
    private func formatShiftDate(_ startDate: String, _ startTime: String, _ endDate: String, _ endTime: String) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        
        if let date = formatter.date(from: startDate) {
            formatter.dateFormat = "MMM d"
            let dateStr = formatter.string(from: date)
            
            let timeFormatter = DateFormatter()
            timeFormatter.dateFormat = "HH:mm:ss"
            
            if let start = timeFormatter.date(from: startTime),
               let end = timeFormatter.date(from: endTime) {
                timeFormatter.dateFormat = "h:mm a"
                let startStr = timeFormatter.string(from: start)
                let endStr = timeFormatter.string(from: end)
                return "\(dateStr), \(startStr) - \(endStr)"
            }
            
            return dateStr
        }
        
        return "\(startDate) \(startTime)"
    }
}

struct SlideToMarkReadButton: View {
    @Binding var sliderOffset: CGFloat
    @Binding var isMarking: Bool
    let onComplete: () -> Void
    
    private let sliderWidth: CGFloat = UIScreen.main.bounds.width - 60
    private let sliderHeight: CGFloat = 60
    private let thumbSize: CGFloat = 50
    
    var body: some View {
        ZStack(alignment: .leading) {
            // Background track
            RoundedRectangle(cornerRadius: sliderHeight / 2)
                .fill(Color("AccentColor").opacity(0.2))
                .frame(height: sliderHeight)
            
            // Progress fill
            RoundedRectangle(cornerRadius: sliderHeight / 2)
                .fill(Color("AccentColor").opacity(0.4))
                .frame(width: sliderOffset + thumbSize, height: sliderHeight)
            
            // Text
            HStack {
                Spacer()
                Text(sliderOffset > sliderWidth - thumbSize - 20 ? "Release to Mark as Read" : "Slide to Mark as Read")
                    .font(.headline)
                    .foregroundColor(sliderOffset > sliderWidth / 2 ? .white : Color("AccentColor"))
                Spacer()
            }
            
            // Slider thumb
            HStack {
                ZStack {
                    Circle()
                        .fill(Color("AccentColor"))
                        .frame(width: thumbSize, height: thumbSize)
                        .shadow(color: .black.opacity(0.2), radius: 4, x: 0, y: 2)
                    
                    if isMarking {
                        ProgressView()
                            .tint(.white)
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: sliderOffset > sliderWidth - thumbSize - 20 ? "checkmark" : "chevron.right")
                            .foregroundColor(.white)
                            .font(.system(size: 20, weight: .bold))
                    }
                }
                .offset(x: sliderOffset)
                .gesture(
                    DragGesture()
                        .onChanged { value in
                            let newOffset = max(0, min(value.translation.width, sliderWidth - thumbSize))
                            sliderOffset = newOffset
                        }
                        .onEnded { _ in
                            if sliderOffset > sliderWidth - thumbSize - 20 {
                                isMarking = true
                                onComplete()
                            } else {
                                withAnimation(.spring()) {
                                    sliderOffset = 0
                                }
                            }
                        }
                )
                
                Spacer()
            }
        }
        .frame(height: sliderHeight)
    }
}

struct LogEntryCard: View {
    let log: ShiftDailyLog
    let categories: [LogCategory]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            if let category = categories.first(where: { $0.id == log.categoryId }) {
                Text(category.name)
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(Color("DefaultTextColor"))
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
                        .foregroundColor(.gray)
                }
                Spacer()
                if let ts = log.createdAt {
                    Text(formattedDate(ts))
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(.gray)
                }
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color("GreyBackground"))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.gray.opacity(0.2), lineWidth: 1)
        )
    }
    
    private func formatPayloadForDisplay(_ payload: [String: JSONValue]) -> String {
        payload.map { key, value in
            let formattedKey = key.replacingOccurrences(of: "_", with: " ").capitalized
            let formattedValue = formatValue(value)
            return "\(formattedKey): \(formattedValue)"
        }.joined(separator: "\n")
    }
    
    private func formatValue(_ value: JSONValue) -> String {
        switch value {
        case .string(let s): return s
        case .number(let n): return String(format: "%.0f", n)
        case .bool(let b): return b ? "Yes" : "No"
        case .null: return "N/A"
        case .array(let arr): return arr.map { formatValue($0) }.joined(separator: ", ")
        case .object(let obj): return obj.map { "\($0.key): \(formatValue($0.value))" }.joined(separator: ", ")
        }
    }
    
    private func formattedDate(_ timestamp: String) -> String {
        // Primary: ISO8601 with fractional seconds
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = isoFormatter.date(from: timestamp) {
            return displayTime(from: date)
        }

        // Fallback: ISO8601 without fractional seconds
        isoFormatter.formatOptions = [.withInternetDateTime]
        if let date = isoFormatter.date(from: timestamp) {
            return displayTime(from: date)
        }

        // Fallback: manual formatter for microseconds (e.g., 2025-12-10T20:53:46.030325)
        let microFormatter = DateFormatter()
        microFormatter.locale = Locale(identifier: "en_US_POSIX")
        microFormatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
        if let date = microFormatter.date(from: timestamp) {
            return displayTime(from: date)
        }

        return timestamp
    }
    
    private func displayTime(from date: Date) -> String {
        let displayFormatter = DateFormatter()
        displayFormatter.dateFormat = "MM/dd/yy h:mma"
        return displayFormatter.string(from: date).lowercased()
    }
}

#Preview {
    NavigationView {
        ShiftLogsDetailView(
            shift: UnreadShift(
                shiftId: 1,
                programLocationId: 1,
                programLocationName: "Scott House",
                startDate: "2026-01-01",
                startTime: "15:00:00",
                endDate: "2026-01-01",
                endTime: "23:00:00",
                logCount: 2,
                hoursSinceEnded: 21
            ),
            onMarkAsRead: {}
        )
        .environmentObject(AuthViewModel())
    }
}
