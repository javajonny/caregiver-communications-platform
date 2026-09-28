import SwiftUI

struct UnreadShiftsView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @Environment(\.dismiss) var dismiss
    
    @State private var unreadShifts: [UnreadShift] = []
    @State private var isLoading = true
    @State private var errorMessage: String?
    
    private let shiftService = ShiftService()
    
    var body: some View {
        NavigationView {
            ZStack {
                Color("AppBackground").ignoresSafeArea()
                
                if isLoading {
                    ProgressView("Loading unread shifts...")
                        .padding()
                } else if let error = errorMessage {
                    VStack(spacing: 20) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.system(size: 50))
                            .foregroundColor(.orange)
                        
                        Text("Unable to load shifts")
                            .font(.headline)
                        
                        Text(error)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                        
                        Button("Retry") {
                            Task { await loadUnreadShifts() }
                        }
                        .buttonStyle(.borderedProminent)
                        
                        Button("Continue Anyway") {
                            dismiss()
                        }
                        .buttonStyle(.bordered)
                    }
                    .padding()
                } else if unreadShifts.isEmpty {
                    VStack(spacing: 20) {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 60))
                            .foregroundColor(Color("SuccessGreen"))
                        
                        Text("All Caught Up!")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(Color("DefaultTextColor"))
                        
                        Text("You've read all shift logs")
                            .font(.subheadline)
                            .foregroundColor(.gray)
                        
                        Button("Continue") {
                            dismiss()
                        }
                        .buttonStyle(.borderedProminent)
                        .padding(.top, 10)
                    }
                    .padding()
                } else {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 16) {
                            // Header
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Unread Shift Logs")
                                    .font(.title)
                                    .fontWeight(.bold)
                                    .foregroundColor(Color("DefaultTextColor"))
                                
                                Text("Please review the following shifts before continuing")
                                    .font(.subheadline)
                                    .foregroundColor(Color("DefaultTextColor"))
                            }
                            .padding(.horizontal)
                            .padding(.top, 20)
                            
                            // Unread shifts list
                            ForEach(unreadShifts) { shift in
                                NavigationLink(destination: ShiftLogsDetailView(
                                    shift: shift,
                                    onMarkAsRead: {
                                        await markAsRead(shift)
                                    }
                                )) {
                                    UnreadShiftCard(shift: shift)
                                }
                                .buttonStyle(PlainButtonStyle())
                            }
                            .padding(.horizontal)
                            
                            // Continue button (only if all shifts are read)
                            if unreadShifts.isEmpty {
                                Button {
                                    dismiss()
                                } label: {
                                    Text("Continue to App")
                                        .font(.headline)
                                        .frame(maxWidth: .infinity)
                                        .padding()
                                        .background(Color("AccentColor"))
                                        .foregroundColor(.white)
                                        .cornerRadius(12)
                                }
                                .padding(.horizontal)
                                .padding(.vertical, 20)
                            }
                        }
                    }
                }
            }
            .navigationBarTitleDisplayMode(.inline)
        }
        .interactiveDismissDisabled()
        .task {
            await loadUnreadShifts()
        }
    }
    
    private func loadUnreadShifts() async {
        isLoading = true
        errorMessage = nil
        
        guard let token = authVM.currentToken() else {
            errorMessage = "Not authenticated"
            isLoading = false
            return
        }
        
        do {
            unreadShifts = try await shiftService.fetchUnreadShifts(token: token)
            isLoading = false
        } catch {
            errorMessage = "Failed to load unread shifts: \(error.localizedDescription)"
            isLoading = false
        }
    }
    
    private func markAsRead(_ shift: UnreadShift) async {
        guard let token = authVM.currentToken() else { return }
        
        do {
            try await shiftService.markShiftAsRead(
                token: token,
                logShiftId: shift.shiftId,
                readDuringShiftId: nil
            )
            
            // Remove from list
            withAnimation {
                unreadShifts.removeAll { $0.shiftId == shift.shiftId }
            }
        } catch {
            errorMessage = "Failed to mark shift as read: \(error.localizedDescription)"
        }
    }
}

struct UnreadShiftCard: View {
    let shift: UnreadShift
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(shift.programLocationName)
                        .font(.headline)
                    HStack {
                        Image(systemName: "calendar")
                            .font(.caption)
                            .foregroundColor(Color(.white))
                        Text(formatShiftDate(shift.startDate, shift.startTime, shift.endDate, shift.endTime))
                            .font(.subheadline)
                    }
                    .foregroundColor(Color(.white))
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    Text("\(shift.logCount)")
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundColor(Color("AccentColor"))
                    
                    Text("log\(shift.logCount == 1 ? "" : "s")")
                        .font(.caption)
                        .foregroundColor(Color(.white))
                }
            }
            
            HStack {
                Image(systemName: "clock")
                    .font(.caption)
                    .foregroundColor(Color("AccentColor"))
                Text(formatTimeSince(hours: shift.hoursSinceEnded))
                    .font(.caption)
                    .foregroundColor(Color("AccentColor"))
                
                Spacer()
                
                HStack {
                    Text("Tap to review")
                        .font(.caption)
                        .foregroundColor(Color("AccentColor"))
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundColor(Color("AccentColor"))
                }
            }
            .foregroundColor(.orange)
        }
        .padding()
        .background(Color("CardBackground"))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.1), radius: 4, x: 0, y: 2)
    }
    
    private func formatShiftDate(_ startDate: String, _ startTime: String, _ endDate: String, _ endTime: String) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        
        if let date = formatter.date(from: startDate) {
            formatter.dateFormat = "MMM d"
            let dateStr = formatter.string(from: date)
            
            // Format times
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
    
    private func formatTimeSince(hours: Double) -> String {
        if hours < 1 {
            return "Less than 1 hour ago"
        } else if hours < 24 {
            let roundedHours = Int(hours)
            return "\(roundedHours) hour\(roundedHours == 1 ? "" : "s") ago"
        } else {
            let days = Int(hours / 24)
            return "\(days) day\(days == 1 ? "" : "s") ago"
        }
    }
}

#Preview {
    UnreadShiftsView()
        .environmentObject(AuthViewModel())
}
