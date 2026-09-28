import SwiftUI

struct ShiftView: View {
    @State private var showProfile = false
    @State private var navigateToBehavior = false
    @State private var showEndShift = false
    @EnvironmentObject var staffVM: StaffViewModel
    @EnvironmentObject var authVM: AuthViewModel
    @EnvironmentObject var shiftVM: ShiftDataViewModel
    
    private var greetingName: String {
        if let name = staffVM.staff?.firstName, !name.isEmpty { return name }
        return "there"
    }
    
    private var todayString: String {
        let df = DateFormatter()
        df.dateFormat = "EEEE, MM/dd/yyyy"
        return df.string(from: Date())
    }
    
    private var shiftTimeString: String {
        guard let shift = shiftVM.current?.shift else {
            return ""
        }
        
        let timeFormatter = DateFormatter()
        timeFormatter.dateFormat = "HH:mm:ss"
        
        let displayFormatter = DateFormatter()
        displayFormatter.dateFormat = "ha"
        
        // Parse start time
        let startTimeStr: String
        if let startDate = timeFormatter.date(from: shift.startTime) {
            startTimeStr = displayFormatter.string(from: startDate).lowercased()
        } else {
            startTimeStr = shift.startTime
        }
        
        // Parse end time
        let endTimeStr: String
        if let endDate = timeFormatter.date(from: shift.endTime) {
            endTimeStr = displayFormatter.string(from: endDate).lowercased()
        } else {
            endTimeStr = shift.endTime
        }
        
        return "and your shift goes from \(startTimeStr) until \(endTimeStr)."
    }
    
    private var taskProgress: Double {
        guard let tasks = shiftVM.current?.tasks, !tasks.isEmpty else { return 0 }
        let completed = tasks.filter { $0.statusId == 2 }.count
        return Double(completed) / Double(tasks.count)
    }
    
    private var taskProgressText: String {
        guard let tasks = shiftVM.current?.tasks, !tasks.isEmpty else { return "0% completed" }
        let percentage = Int(taskProgress * 100)
        return "\(percentage)% completed"
    }
    
    // Timer to refresh time display
    @State private var currentTime = Date()
    private let timer = Timer.publish(every: 60, on: .main, in: .common).autoconnect()
    
    // Computed properties for shift status
    private var minutesUntilEnd: Int {
        shiftVM.current?.timeInfo.minutesUntilEnd ?? 0
    }
    
    private var hasEnded: Bool {
        shiftVM.current?.assignment.hasEnded ?? false
    }
    
    private var shiftEnded: Bool {
        shiftVM.current?.timeInfo.shiftEnded ?? false
    }
    
    private var bannerInfo: (message: String, color: Color)? {
        // Don't show banner if there's an error or no shift
        guard shiftVM.current != nil, shiftVM.errorMessage == nil else {
            return nil
        }
        if hasEnded {
            return nil
        }
        if minutesUntilEnd <= 0 {
            return ("Shift has ended - please submit your end-of-shift report", Color.red)
        } else if minutesUntilEnd <= 5 {
            return ("Only \(minutesUntilEnd) minutes left!", Color.red)
        } else if minutesUntilEnd <= 15 {
            return ("\(minutesUntilEnd) minutes remaining", Color.orange)
        } else if minutesUntilEnd <= 30 {
            return ("Shift ending in \(minutesUntilEnd) minutes", Color.yellow)
        }
        return nil
    }
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    // Time-based banner
                    if let info = bannerInfo {
                        HStack {
                            Image(systemName: hasEnded ? "checkmark.circle.fill" : "clock.fill")
                            Text(info.message)
                                .font(.system(size: 14, weight: .semibold))
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .padding(.horizontal)
                        .background(info.color.opacity(0.9))
                        .foregroundColor(info.color == .yellow ? .black : .white)
                        .cornerRadius(12)
                    }
                    
                    header

                    if shiftVM.isLoading {
                        ProgressView("Loading shift...")
                    } else if shiftVM.errorMessage != nil {
                        // No shift found - show polished message and logout
                        VStack(spacing: 24) {
                            VStack(spacing: 12) {
                                Image(systemName: "calendar.badge.exclamationmark")
                                    .font(.system(size: 60))
                                    .foregroundColor(Color("AccentColor"))
                                
                                Text("No Shift Found")
                                    .font(.system(size: 24, weight: .bold))
                                    .foregroundColor(Color("DefaultTextColor"))
                                
                                Text("You don't have an active shift scheduled right now.")
                                    .font(.system(size: 16))
                                    .foregroundColor(Color("DefaultTextColor").opacity(0.7))
                                    .multilineTextAlignment(.center)
                            }
                            .padding(.vertical, 40)
                            
                            Button("Logout", systemImage: "rectangle.portrait.and.arrow.right") {
                                Task {
                                    await authVM.logout()
                                }
                            }
                            .font(.system(size: 20, weight: .semibold))
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color("AccentColor"))
                            .foregroundColor(.white)
                            .cornerRadius(16)
                        }
                    } else if hasEnded {
                        // Shift already ended - show only message and logout
                        VStack(spacing: 24) {
                            VStack(spacing: 12) {
                                Image(systemName: "checkmark.circle.fill")
                                    .font(.system(size: 60))
                                    .foregroundColor(Color("SuccessGreen"))
                                
                                Text("Shift Submitted")
                                    .font(.system(size: 24, weight: .bold))
                                    .foregroundColor(Color("DefaultTextColor"))
                                
                                Text("You have already submitted your end-of-shift report. No further changes can be made.")
                                    .font(.system(size: 16))
                                    .foregroundColor(Color("DefaultTextColor").opacity(0.7))
                                    .multilineTextAlignment(.center)
                            }
                            .padding(.vertical, 40)
                            
                            Button("Logout", systemImage: "rectangle.portrait.and.arrow.right") {
                                Task {
                                    await authVM.logout()
                                }
                            }
                            .font(.system(size: 20, weight: .semibold))
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color("AccentColor"))
                            .foregroundColor(.white)
                            .cornerRadius(16)
                        }
                    } else {
                        // Normal shift content
                        NavigationLink(destination: TasksView()
                            .environmentObject(authVM)
                            .environmentObject(shiftVM)
                            .environmentObject(staffVM)) {
                            featureCard(title: "Tasks", subtitle: taskProgressText) {
                                progressBar(progress: taskProgress)
                            }
                        }
                        .buttonStyle(PlainButtonStyle())
                        
                        NavigationLink(destination: BehaviorTrackingView()
                            .environmentObject(authVM)
                            .environmentObject(shiftVM)
                            .environmentObject(staffVM)) {
                            featureCard(title: "Behavior\nTracking") {
                            }
                        }
                        .buttonStyle(PlainButtonStyle())
                        
                        NavigationLink(destination: DailyLogView()
                            .environmentObject(authVM)
                            .environmentObject(shiftVM)
                            .environmentObject(staffVM)) {
                            featureCard(title: "Daily Log") {
                            }
                        }
                        .buttonStyle(PlainButtonStyle())
                        
                        NavigationLink(destination: EndShiftView()
                            .environmentObject(authVM)
                            .environmentObject(shiftVM)
                            .environmentObject(staffVM)) {
                            Text("End shift")
                                .font(.system(size: 28, weight: .bold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 16)
                                .background(Color(red: 1.0, green: 0.45, blue: 0.42))
                                .foregroundColor(.white)
                                .cornerRadius(20)
                        }
                        .buttonStyle(PlainButtonStyle())
                        .padding(.top, 8)
                        
                        /*
                        // Testing button - simple logout
                        Button {
                            Task {
                                await authVM.logout()
                            }
                        } label: {
                            Text("Logout (Testing)")
                                .font(.system(size: 16, weight: .medium))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                                .foregroundColor(.gray)
                        }
                        .padding(.top, 4)
                         */
                    }
                }
                .padding(.horizontal)
                .padding(.vertical, 8)
            }
            .navigationTitle("Shift")
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
            .task {
                await shiftVM.load(token: authVM.currentToken())
            }
            .onReceive(timer) { _ in
                currentTime = Date()
                // Refresh shift data every minute (background call - doesn't reset session timer)
                Task {
                    await shiftVM.load(token: authVM.currentToken(), isBackgroundCall: true)
                }
            }
            .background(Color("AppBackground").ignoresSafeArea())
        }
    }
    
    private var header: some View {
        VStack(alignment: .leading) {
    Text("Hello \(greetingName)!")
        .font(.system(size: 28, weight: .bold))
        .foregroundColor(Color("DefaultTextColor"))

    Text("Today is \(todayString) \(shiftTimeString)")
        .font(.system(size: 22, weight: .regular))
        .foregroundColor(Color("DefaultTextColor"))
        .fixedSize(horizontal: false, vertical: true)
}
.frame(maxWidth: .infinity, alignment: .leading)
    }
    
    private func featureCard<Content: View>(title: String, subtitle: String? = nil, @ViewBuilder content: () -> Content) -> some View {
        HStack(spacing: 30) {
            if(title=="Tasks") {
                Image(systemName: "checklist")
                    .font(.system(size: 55, weight: .regular))
                    .foregroundColor(Color("DefaultTextColor"))
            } else if (title=="Behavior\nTracking") {
                Image("BehaviorIcon")
                    .font(.system(size: 55, weight: .regular))
                    .foregroundColor(Color("DefaultTextColor"))
            } else if (title=="Daily Log") {
                Image(systemName: "book.pages")
                    .font(.system(size: 55, weight: .regular))
                    .foregroundColor(Color("DefaultTextColor"))
            }

        VStack(alignment: .leading) {
            Text(title)
                .font(.system(size: 32, weight: .bold))
                .foregroundColor(Color("DefaultTextColor"))
            if let subtitle = subtitle {
                Text(subtitle)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(Color("BrightTextColor"))
            }
            content()
        }
        
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 24)
                .fill(Color("CardBackground"))
        )
    }
    
    private func progressBar(progress: CGFloat) -> some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color.white)
                    .frame(height: 22)
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color.black, lineWidth: 1)
                    )
                
                RoundedRectangle(cornerRadius: 10)
                    .fill(Color("AccentColor"))
                    .frame(width: max(0, min(progress * (geometry.size.width - 12), geometry.size.width - 12)), height: 10)
                    .padding(.leading, 6)
            }
        }
        .frame(height: 22)
    }
}
