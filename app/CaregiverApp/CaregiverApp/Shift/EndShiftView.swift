import SwiftUI

struct EndShiftView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @EnvironmentObject var shiftVM: ShiftDataViewModel
    @EnvironmentObject var staffVM: StaffViewModel
    @Environment(\.dismiss) private var dismiss
    
    @State private var explanations: [Int: String] = [:]  // taskId -> explanation
    @State private var isSubmitting = false
    @State private var errorMessage: String?
    @State private var showSuccessAlert = false
    @State private var currentTime = Date()
    @State private var behaviorConfirmed = false
    
    private let shiftService = ShiftService()
    private let timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()
    
    private var tasks: [ShiftTaskItem] {
        shiftVM.current?.tasks ?? []
    }
    
    private var completedTasks: [ShiftTaskItem] {
        tasks.filter { $0.statusId == 2 }
    }
    
    private var incompleteTasks: [ShiftTaskItem] {
        tasks.filter { $0.statusId != 2 }
    }
    
    // Only non-custom tasks require explanations
    private var requiredExplanationTasks: [ShiftTaskItem] {
        incompleteTasks.filter { !$0.isCustom }
    }
    
    private var allExplanationsFilled: Bool {
        requiredExplanationTasks.allSatisfy { task in
            let explanation = explanations[task.id]?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            return !explanation.isEmpty
        }
    }
    
    // Clients that have behaviors configured
    private var clientsWithBehaviors: [ShiftClient] {
        (shiftVM.current?.clients ?? []).filter { !$0.behaviors.isEmpty }
    }
    
    private var hasBehaviors: Bool {
        !clientsWithBehaviors.isEmpty
    }
    
    private var canSubmit: Bool {
        let explanationsOk = requiredExplanationTasks.isEmpty || allExplanationsFilled
        let behaviorOk = !hasBehaviors || behaviorConfirmed
        return explanationsOk && behaviorOk
    }
    
    // Grace period countdown (10 min = 600 sec from shift end)
    private var minutesRemaining: Int {
        // minutesUntilEnd is negative when shift has ended
        // e.g., -3 means 3 minutes past shift end, so 7 minutes remaining in 10 min grace
        let minutesPast = -(shiftVM.current?.timeInfo.minutesUntilEnd ?? 0)
        return max(0, 10 - minutesPast)
    }
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                // Countdown banner for grace period
                if minutesRemaining <= 30 {
                    HStack {
                        Image(systemName: "exclamationmark.triangle.fill")
                        Text("Submit within \(minutesRemaining) minute\(minutesRemaining == 1 ? "" : "s") or shift will timeout")
                            .font(.system(size: 14, weight: .semibold))
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                    .padding(.horizontal)
                    .background(Color.red.opacity(0.9))
                    .foregroundColor(.white)
                    .cornerRadius(12)
                }
                
                // Summary header
                summaryHeader
                
                // Completed tasks section
                if !completedTasks.isEmpty {
                    taskSection(title: "Completed Tasks", tasks: completedTasks, isCompleted: true)
                }
                
                // Incomplete tasks section with explanations
                if !incompleteTasks.isEmpty {
                    incompleteTasksSection
                }
                
                // Behavior tracking confirmation section
                if hasBehaviors {
                    behaviorConfirmationSection
                }
                
                // Error message
                if let error = errorMessage {
                    Text(error)
                        .font(.system(size: 14))
                        .foregroundColor(.red)
                        .padding(.horizontal)
                }
                
                // Submit button
                Button {
                    Task {
                        await submitEndShift()
                    }
                } label: {
                    HStack {
                        if isSubmitting {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .white))
                                .padding(.trailing, 8)
                        }
                        Text(isSubmitting ? "Submitting..." : "Submit & End Shift")
                            .font(.system(size: 20, weight: .bold))
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(canSubmit && !isSubmitting ? Color("AccentColor") : Color.gray)
                    .foregroundColor(.white)
                    .cornerRadius(16)
                }
                .disabled(!canSubmit || isSubmitting)
                .padding(.top, 8)
            }
            .padding()
        }
        .navigationTitle("End Shift")
        .navigationBarTitleDisplayMode(.large)
        .background(Color("AppBackground").ignoresSafeArea())
        .alert("Shift Ended", isPresented: $showSuccessAlert) {
            Button("OK") {
                Task {
                    await authVM.logout()
                }
            }
        } message: {
            Text("Your shift has been successfully ended. You will now be logged out.")
        }
    }
    
    private var summaryHeader: some View {
        HStack {
    VStack {
        Text("\(completedTasks.count)")
            .font(.system(size: 36, weight: .bold))
            .foregroundColor(Color("SuccessGreen"))
        Text("Completed")
            .font(.system(size: 14, weight: .medium))
            .foregroundColor(Color("DefaultTextColor").opacity(0.7))
    }
    .frame(maxWidth: .infinity)

    VStack {
        Text("\(incompleteTasks.count)")
            .font(.system(size: 36, weight: .bold))
            .foregroundColor(incompleteTasks.isEmpty ? Color("DefaultTextColor") : Color.orange)
        Text("Incomplete")
            .font(.system(size: 14, weight: .medium))
            .foregroundColor(Color("DefaultTextColor").opacity(0.7))
    }
    .frame(maxWidth: .infinity)

    VStack {
        Text("\(tasks.count)")
            .font(.system(size: 36, weight: .bold))
            .foregroundColor(Color("DefaultTextColor"))
        Text("Total")
            .font(.system(size: 14, weight: .medium))
            .foregroundColor(Color("DefaultTextColor").opacity(0.7))
    }
    .frame(maxWidth: .infinity)
}
.frame(maxWidth: .infinity)
.padding(.vertical, 16)
.background(
    RoundedRectangle(cornerRadius: 16)
        .fill(Color("CardBackground"))
)

    }
    
    private func taskSection(title: String, tasks: [ShiftTaskItem], isCompleted: Bool) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title)
                .font(.system(size: 20, weight: .semibold))
                .foregroundColor(Color("DefaultTextColor"))
            
            ForEach(tasks) { task in
                HStack(spacing: 12) {
                    Image(systemName: isCompleted ? "checkmark.circle.fill" : "circle")
                        .font(.system(size: 22))
                        .foregroundColor(isCompleted ? Color("SuccessGreen") : Color.gray)
                    
                    Text(task.name)
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(Color("DefaultTextColor"))
                        .strikethrough(isCompleted)
                        .opacity(isCompleted ? 0.7 : 1.0)
                    
                    Spacer()
                    
                    if task.isCustom {
                        Text("Custom")
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundColor(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Capsule().fill(Color(red: 0.91, green: 0.76, blue: 0.63)))
                    }
                }
                .padding(12)
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(isCompleted ? Color(red: 0.85, green: 0.95, blue: 0.85) : Color("CardBackground"))
                )
            }
        }
    }
    
    private var incompleteTasksSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Incomplete Tasks")
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundColor(Color("DefaultTextColor"))
                
                if requiredExplanationTasks.isEmpty {
                    Text("Only custom tasks remain - no explanations required")
                        .font(.system(size: 14))
                        .foregroundColor(Color("DefaultTextColor").opacity(0.6))
                } else {
                    Text("Please explain why required tasks were not completed")
                        .font(.system(size: 14))
                        .foregroundColor(Color("DefaultTextColor").opacity(0.6))
                }
            }
            
            ForEach(incompleteTasks) { task in
                VStack(alignment: .leading, spacing: 8) {
                    HStack(spacing: 12) {
                        Image(systemName: "circle")
                            .font(.system(size: 22))
                            .foregroundColor(.orange)
                        
                        Text(task.name)
                            .font(.system(size: 16, weight: .medium))
                            .foregroundColor(Color("DefaultTextColor"))
                        
                        Spacer()
                        
                        if task.isCustom {
                            Text("Custom")
                                .font(.system(size: 10, weight: .semibold))
                                .foregroundColor(.white)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Capsule().fill(Color(red: 0.91, green: 0.76, blue: 0.63)))
                        }
                    }
                    
                    // Only show text field for non-custom tasks
                    if !task.isCustom {
                        TextField("Why was this task not completed?", text: Binding(
                            get: { explanations[task.id] ?? "" },
                            set: { explanations[task.id] = $0 }
                        ), axis: .vertical)
                        .lineLimit(2...4)
                        .textFieldStyle(.roundedBorder)
                        .font(.system(size: 14))
                    } else {
                        Text("Optional - no explanation required")
                            .font(.system(size: 12, weight: .regular))
                            .foregroundColor(Color("DefaultTextColor").opacity(0.5))
                            .italic()
                    }
                }
                .padding(12)
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color(red: 1.0, green: 0.95, blue: 0.85))
                )
            }
        }
    }
    
    private var behaviorConfirmationSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Verify Behavior Tracking")
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundColor(Color("DefaultTextColor"))
                
                Text("Please confirm these counts are correct before ending your shift.")
                    .font(.system(size: 14))
                    .foregroundColor(Color("DefaultTextColor").opacity(0.6))
            }
            
            // Show each client's behaviors
            ForEach(clientsWithBehaviors) { client in
                VStack(alignment: .leading, spacing: 8) {
                    Text("\(client.firstName) \(client.lastName)")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(Color("DefaultTextColor"))
                    
                    ForEach(client.behaviors) { behavior in
                        HStack {
                            Text(behavior.behaviorName)
                                .font(.system(size: 14))
                                .foregroundColor(Color("DefaultTextColor"))
                            
                            Spacer()
                            
                            Text("\(behavior.currentCount)")
                                .font(.system(size: 14, weight: .medium))
                                .foregroundColor(Color("AccentColor"))
                        }
                        .padding(.vertical, 4)
                    }
                }
                .padding(12)
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color("CardBackground"))
                )
            }
            
            // Go Back & Fix button - navigates to BehaviorTrackingView
            NavigationLink(destination: BehaviorTrackingView()
                .environmentObject(authVM)
                .environmentObject(shiftVM)
                .environmentObject(staffVM)
            ) {
                HStack {
                    Image(systemName: "arrow.left.circle")
                    Text("Go Back & Fix")
                }
                .font(.system(size: 16, weight: .medium))
                .foregroundColor(Color("AccentColor"))
            }
            .padding(.top, 4)
            
            // Confirmation toggle
            Toggle(isOn: $behaviorConfirmed) {
                Text("I confirm behavior tracking is accurate")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundColor(Color("DefaultTextColor"))
            }
            .toggleStyle(CheckboxToggleStyle())
            .padding(.top, 8)
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color(red: 0.95, green: 0.97, blue: 1.0))
        )
    }
    
    private func submitEndShift() async {
        guard let token = authVM.currentToken(),
              let shiftId = shiftVM.current?.shift.id else {
            errorMessage = "Unable to get shift information"
            return
        }
        
        isSubmitting = true
        errorMessage = nil
        
        // Build explanations array for incomplete tasks
        let taskExplanations = incompleteTasks.compactMap { task -> EndShiftTaskExplanation? in
            guard let explanation = explanations[task.id]?.trimmingCharacters(in: .whitespacesAndNewlines),
                  !explanation.isEmpty else {
                return nil
            }
            return EndShiftTaskExplanation(taskId: task.id, explanation: explanation)
        }
        
        do {
            _ = try await shiftService.endShift(token: token, shiftId: shiftId, explanations: taskExplanations)
            showSuccessAlert = true
        } catch {
            errorMessage = "Failed to end shift: \(error.localizedDescription)"
        }
        
        isSubmitting = false
    }
}

// MARK: - Checkbox Toggle Style

struct CheckboxToggleStyle: ToggleStyle {
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 12) {
            Image(systemName: configuration.isOn ? "checkmark.square.fill" : "square")
                .font(.system(size: 22))
                .foregroundColor(configuration.isOn ? Color("AccentColor") : Color.gray)
                .onTapGesture { configuration.isOn.toggle() }
            
            configuration.label
        }
    }
}
