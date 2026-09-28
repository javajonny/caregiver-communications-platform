import SwiftUI

struct BehaviorTrackingView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @EnvironmentObject var shiftVM: ShiftDataViewModel
    @EnvironmentObject var staffVM: StaffViewModel
    @State private var isUpdating = false
    @State private var showProfile = false
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if let current = shiftVM.current {
                    ForEach(current.clients) { client in
                        clientCard(client)
                    }
                } else {
                    Text("No shift data available")
                        .foregroundColor(.secondary)
                        .padding()
                }
            }
            .padding()
        }
        .navigationTitle("Behavior Tracking")
        .navigationBarTitleDisplayMode(.large)
        .disabled(isUpdating)
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
    
    private func clientCard(_ client: ShiftClient) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            // Client header
            HStack(spacing: 12) {
                RemoteImageView(url: client.profileImageURL)
                    .aspectRatio(contentMode: .fill)
                    .frame(width: 90, height: 90)
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                    .shadow(radius: 4)
                
                VStack(alignment: .leading) {
                    Text(client.firstName)
                        .font(.system(size: 30, weight: .bold))
                        .foregroundColor(Color("DefaultTextColor"))
                    Text(client.lastName)
                        .font(.system(size: 30, weight: .bold))
                        .foregroundColor(Color("DefaultTextColor"))
                }
                Spacer()
            }
            
            // Behavior list
            if client.behaviors.isEmpty {
                Text("No behaviors configured")
                    .foregroundColor(.secondary)
                    .italic()
            } else {
                VStack(spacing: 12) {
                    ForEach(client.behaviors) { behavior in
                        behaviorRow(client: client, behavior: behavior)
                    }
                }
            }
        }
        .padding(20)
        .background(
            RoundedRectangle(cornerRadius: 24)
                .fill(Color("CardBackground"))
        )
    }
    
    private func behaviorRow(client: ShiftClient, behavior: BehaviorConfigItem) -> some View {
        HStack(spacing: 16) {
            Text(behavior.behaviorName)
                .font(.system(size: 15, weight: .regular))
                .foregroundColor(Color("DefaultTextColor"))
            
            Spacer()
            
            HStack(spacing:2){
                // Minus button
                Button {
                    Task {
                        await updateCount(client: client, behavior: behavior, increment: false)
                    }
                } label: {
                    Image(systemName: "minus")
                        .font(.system(size: 18, weight: .bold))
                        .foregroundColor(Color("DefaultTextColor"))
                        .frame(width: 18, height: 18)
                        // .background(Circle().fill(Color("DefaultTextColor")))
                }
                .disabled(behavior.currentCount <= 0 || isUpdating)
                
                // Count
                Text("\(behavior.currentCount)")
                    .font(.system(size: 18, weight: .bold))
                    .foregroundColor(Color("AccentColor"))
                    .frame(minWidth: 40)
                
                // Plus button
                Button {
                    Task {
                        await updateCount(client: client, behavior: behavior, increment: true)
                    }
                } label: {
                    Image(systemName: "plus")
                        .font(.system(size: 18, weight: .bold))
                        .foregroundColor(Color("DefaultTextColor"))
                        .frame(width: 18, height: 18)
                        // .background(Circle().fill(Color("DefaultTextColor")))
                }
                .disabled(isUpdating)
                
        }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 10)
        .background(
            RoundedRectangle(cornerRadius: 40)
                .fill(Color("GreyBackground"))
        )
    }
    
    private func updateCount(client: ShiftClient, behavior: BehaviorConfigItem, increment: Bool) async {
        guard let token = authVM.currentToken() else { return }
        let staffId = authVM.currentStaffId()
        let shiftId = shiftVM.current?.shift.id ?? 0
        
        guard staffId > 0, shiftId > 0 else { return }
        
        isUpdating = true
        defer { isUpdating = false }
        
        do {
            let service = BehaviorTrackingService()
            
            // Record either +1 or -1
            try await service.recordBehavior(
                token: token,
                shiftId: shiftId,
                staffId: staffId,
                clientId: client.id,
                behaviorTypeId: behavior.behaviorTypeId,
                recordedValue: increment ? 1 : -1,
                notes: nil
            )
            
            // Refresh shift data to get updated counts
            await shiftVM.load(token: token)
        } catch {
            print("Failed to update count: \(error)")
        }
    }
}

