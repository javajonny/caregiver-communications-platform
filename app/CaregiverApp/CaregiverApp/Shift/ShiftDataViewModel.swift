import Foundation
import SwiftUI

@MainActor
final class ShiftDataViewModel: ObservableObject {
    @Published var current: CurrentShiftResponse?
    @Published var isLoading = false
    @Published var errorMessage: String?

    private let service = ShiftService()

    func load(token: String?, isBackgroundCall: Bool = false) async {
        guard let token = token, !token.isEmpty else {
            errorMessage = "Missing auth token"
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let resp = try await service.fetchCurrentShift(token: token, isBackgroundCall: isBackgroundCall)
            self.current = resp
        } catch {
            self.errorMessage = "Failed to load shift: \(error.localizedDescription)"
        }
    }
    
    /// Optimistically update a task's status in the local model.
    /// Returns the previous status for potential rollback.
    func updateTaskStatusLocally(taskId: Int, newStatusId: Int) -> Int? {
        guard var currentData = current else { return nil }
        
        // Find and update the task in the local model
        if let index = currentData.tasks.firstIndex(where: { $0.id == taskId }) {
            let previousStatus = currentData.tasks[index].statusId
            
            // Create updated task with new status
            let updatedTask = ShiftTaskItem(
                id: currentData.tasks[index].id,
                name: currentData.tasks[index].name,
                statusId: newStatusId,
                scheduledStartTime: currentData.tasks[index].scheduledStartTime,
                scheduledEndTime: currentData.tasks[index].scheduledEndTime,
                isCustom: currentData.tasks[index].isCustom
            )
            
            // Update the array
            var updatedTasks = currentData.tasks
            updatedTasks[index] = updatedTask
            
            // Create new response with updated tasks
            self.current = CurrentShiftResponse(
                shift: currentData.shift,
                position: currentData.position,
                assignment: currentData.assignment,
                timeInfo: currentData.timeInfo,
                tasks: updatedTasks,
                clients: currentData.clients
            )
            
            return previousStatus
        }
        return nil
    }
    
    /// Rollback a task's status to the previous value
    func rollbackTaskStatus(taskId: Int, previousStatusId: Int?) {
        guard let previousStatusId = previousStatusId else { return }
        _ = updateTaskStatusLocally(taskId: taskId, newStatusId: previousStatusId)
    }
}
