import SwiftUI

struct TasksView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @EnvironmentObject var shiftVM: ShiftDataViewModel
    @EnvironmentObject var staffVM: StaffViewModel
    @State private var isUpdating = false
    @State private var showProfile = false
    @State private var showAddTaskSheet = false
    @State private var newTaskName = ""
    @State private var newTaskDescription = ""
    @State private var newTaskDurationMinutes: Int = 0
    @State private var selectedCategoryId: Int = -1 // -1 = placeholder (must choose real category)
    @State private var taskCategories: [TaskCategory] = []
    @State private var addTaskError: String?
    
    private var completedCount: Int {
        shiftVM.current?.tasks.filter { $0.statusId == 2 }.count ?? 0
    }
    
    private var totalCount: Int {
        shiftVM.current?.tasks.count ?? 0
    }
    
    private var progressPercentage: Double {
        guard totalCount > 0 else { return 0 }
        return Double(completedCount) / Double(totalCount)
    }
    
    var body: some View {
        ZStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Progress bar
                    VStack(alignment: .leading, spacing: 8) {
                        progressBar
                    }
                    .padding(.horizontal)
                    
                    // Task list
                    if let tasks = shiftVM.current?.tasks {
                        if tasks.isEmpty {
                            Text("No tasks assigned")
                                .foregroundColor(.secondary)
                                .padding()
                        } else {
                            VStack(spacing: 12) {
                                ForEach(sortedTasks(tasks)) { task in
                                    taskRow(task)
                                        .transition(.move(edge: .bottom).combined(with: .opacity))
                                }
                            }
                            .animation(.easeInOut(duration: 0.5), value: sortedTasks(tasks).map { $0.id })
                            .padding(.horizontal)
                        }
                    } else {
                        Text("No shift data available")
                            .foregroundColor(.secondary)
                            .padding()
                    }
                    
                    // Spacer for floating button
                    Spacer()
                        .frame(height: 80)
                }
                .padding(.vertical)
            }
            
            // Floating add button at fixed position
            VStack {
                Spacer()
                HStack {
                    Spacer()
                    Button {
                        showAddTaskSheet = true
                    } label: {
                        Image(systemName: "plus.circle")
                            .font(.system(size: 60, weight: .bold))
                            .foregroundColor(Color("AccentColor"))
                    }
                    .padding(.trailing, 20)
                    .padding(.bottom, 20)
                }
            }
        }
        .navigationTitle("Tasks")
        .navigationBarTitleDisplayMode(.large)
        .disabled(isUpdating)
        .task {
            await loadTaskCategories()
        }
        .sheet(isPresented: $showAddTaskSheet) {
            addTaskSheet
        }
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
        .background(Color("AppBackground").ignoresSafeArea())

    }



    
    private var progressBar: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                // Background
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color.white)
                    .frame(height: 22)
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color.black, lineWidth: 1)
                    )
                
                // Progress fill
                RoundedRectangle(cornerRadius: 10)
                    .fill(Color("AccentColor"))
                    .frame(width: max(0, progressPercentage * (geometry.size.width - 12)), height: 10)
                    .padding(.leading, 6)
                    .animation(.easeInOut(duration: 0.5), value: progressPercentage)
            }
        }
        .frame(height: 28)
    }
    
    private func sortedTasks(_ tasks: [ShiftTaskItem]) -> [ShiftTaskItem] {
        tasks.sorted { task1, task2 in
            let isCompleted1 = task1.statusId == 2
            let isCompleted2 = task2.statusId == 2
            
            // Pending tasks come before completed tasks
            if isCompleted1 != isCompleted2 {
                return !isCompleted1
            }
            // Keep original order within same status
            return false
        }
    }
    
    private func taskRow(_ task: ShiftTaskItem) -> some View {
        let isCompleted = task.statusId == 2
        let canDelete = task.isCustom && !isCompleted
        
        return Button {
            Task {
                await toggleTaskStatus(task)
            }
        } label: {
            HStack(spacing: 8) {
                // Checkbox
                ZStack {
                    Circle()
                        .strokeBorder(isCompleted ? Color.clear : Color("DefaultTextColor").opacity(0.6), lineWidth: 2)
                        .background(
                            Circle().fill(
                                isCompleted
                                    ? (task.isCustom ? Color("SuccessCustom") : Color("SuccessGreen"))
                                    : Color("AppBackground")
                            )
                        )
                        .frame(width: 32, height: 32)
                    
                    if isCompleted {
                        Image(systemName: "checkmark")
                            .font(.system(size: 16, weight: .bold))
                            .foregroundColor(.white)
                    }
                }
                .frame(width: 32, height: 32, alignment: .center)
                
                // Task text with custom badge
                HStack(spacing: 8) {
                    Text(task.name)
                        .font(.system(size: 15, weight: .medium))
                        .foregroundColor(Color("DefaultTextColor"))
                        .strikethrough(isCompleted, color: Color("DefaultTextColor").opacity(0.6))
                        .opacity(isCompleted ? 0.5 : 1.0)
                    
                    if task.isCustom {
                        Text("Custom")
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundColor(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(
                                Capsule()
                                    .fill(Color(red: 0.91, green: 0.76, blue: 0.63))
                            )
                    }
                    
                    // Spacer()
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                
                // Delete button - only for pending custom tasks
                if canDelete {
                    Button(action: {
                        Task {
                            await deleteCustomTask(task)
                        }
                    }) {
                        Image(systemName: "trash")
                            .font(.system(size: 22, weight: .semibold))
                            .foregroundColor(Color("DeleteColor"))
                            .frame(width: 32, height: 32, alignment: .center)
                    }
                }
            }
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 16)
                    .fill(
                        isCompleted
                            ? Color(red: 0.85, green: 0.95, blue: 0.85)
                            : (task.isCustom
                                ? Color(red: 0.91, green: 0.76, blue: 0.63).opacity(0.7)
                                : Color(red: 0.85, green: 0.82, blue: 0.80))
                    )
            )
        }
        .buttonStyle(PlainButtonStyle())
        .disabled(isUpdating)
            
        
    }
    
    private func toggleTaskStatus(_ task: ShiftTaskItem) async {
        let newStatusId = task.statusId == 2 ? 1 : 2 // Toggle between pending (1) and completed (2)
        await updateTaskStatus(task, to: newStatusId, errorMessage: "Failed to toggle task status")
    }
    
    private func deleteCustomTask(_ task: ShiftTaskItem) async {
        await updateTaskStatus(task, to: 4, errorMessage: "Failed to delete custom task")
    }
    
    private func updateTaskStatus(_ task: ShiftTaskItem, to statusId: Int, errorMessage: String) async {
        guard let token = authVM.currentToken(),
              let shiftId = shiftVM.current?.shift.id,
              let positionId = shiftVM.current?.position.id else { return }
        
        // Prevent double-taps while updating
        guard !isUpdating else { return }
        
        isUpdating = true
        
        // Optimistically update the local model immediately
        let previousStatus = shiftVM.updateTaskStatusLocally(taskId: task.id, newStatusId: statusId)
        
        do {
            let service = TaskService()
            try await service.createOrUpdateTaskStatus(
                token: token,
                shiftId: shiftId,
                taskId: task.id,
                shiftPositionId: positionId,
                statusId: statusId
            )
            
            // Refresh shift data to ensure consistency with server
            await shiftVM.load(token: token)
        } catch {
            print("\(errorMessage): \(error)")
            // Rollback on failure
            shiftVM.rollbackTaskStatus(taskId: task.id, previousStatusId: previousStatus)
        }
        
        isUpdating = false
    }
    
    // MARK: - Add Task Sheet
    private var addTaskSheet: some View {
        NavigationView {
            Form {
                Section(header: Text("Task Details").foregroundColor(Color("DefaultTextColor"))) {
                    TextField("Task name (required)", text: $newTaskName)
                    
                    Picker("Category", selection: $selectedCategoryId) {
                        if taskCategories.isEmpty {
                            Text("Loading…").tag(-1)
                        } else {
                            Text("Select Category").tag(-1)
                            ForEach(taskCategories) { category in
                                Text(category.name).tag(category.id)
                            }
                        }
                    }
                    .pickerStyle(.menu)
                    
                    TextField("Description (optional)", text: $newTaskDescription, axis: .vertical)
                        .lineLimit(3...6)
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Estimated duration")
                            .foregroundColor(Color(UIColor.placeholderText))
                        
                        Picker("Duration", selection: $newTaskDurationMinutes) {
                            ForEach(Array(stride(from: 0, through: 240, by: 5)), id: \.self) { value in
                                Text("\(value) min").tag(value)
                            }
                        }
                        .pickerStyle(.wheel)
                        Button("Reset") { newTaskDurationMinutes = 0 }
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                if let error = addTaskError {
                    Section {
                        Text(error)
                            .foregroundColor(.red)
                            .font(.footnote)
                    }
                }
                if taskCategories.isEmpty {
                    Section {
                        Text("No categories available or failed to load.")
                            .foregroundColor(.secondary)
                            .font(.footnote)
                    }
                }
            }
            .navigationTitle("Add Custom Task")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismissAddTaskSheet()
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        Task {
                            await addCustomTask()
                        }
                    }
                    .disabled(newTaskName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isUpdating || taskCategories.isEmpty || selectedCategoryId == -1)
                }
            }
            .task {
                // Fallback load in case initial .task on parent ran before token existed
                if taskCategories.isEmpty {
                    await loadTaskCategories()
                }
            }
        }
    }
    
    private func dismissAddTaskSheet() {
        showAddTaskSheet = false
        newTaskName = ""
        newTaskDescription = ""
        newTaskDurationMinutes = 0
        selectedCategoryId = -1
        addTaskError = nil
    }
    
    private func loadTaskCategories() async {
        guard let token = authVM.currentToken() else { return }
        do {
            let service = TaskService()
            taskCategories = try await service.fetchTaskCategories(token: token)
            print("[TasksView] Fetched categories count: \(taskCategories.count)")
            // Do not auto-select; user must pick (keep -1 until chosen)
        } catch {
            print("Failed to load task categories: \(error)")
        }
    }
    
    private func addCustomTask() async {
        guard let token = authVM.currentToken(),
                            shiftVM.current?.shift.id != nil else {
                        addTaskError = "Missing current shift info"
            return
        }
        
        let name = newTaskName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty else {
            addTaskError = "Task name is required"
            return
        }
        
        let description = newTaskDescription.trimmingCharacters(in: .whitespacesAndNewlines)
        let durationMinutes = newTaskDurationMinutes > 0 ? newTaskDurationMinutes : nil
        
        isUpdating = true
        defer { isUpdating = false }
        
        do {
            let service = TaskService()
            // Create shift-only custom task (backend attaches to current shift)
            _ = try await service.createCustomTask(
                token: token,
                name: name,
                description: description.isEmpty ? nil : description,
                categoryId: (selectedCategoryId == -1 ? nil : selectedCategoryId),
                estimatedDurationMinutes: durationMinutes
            )
            // Refresh shift data to include new ad-hoc task
            await shiftVM.load(token: token)
            dismissAddTaskSheet()
        } catch {
            addTaskError = "Failed to add task: \(error.localizedDescription)"
        }
    }
}
