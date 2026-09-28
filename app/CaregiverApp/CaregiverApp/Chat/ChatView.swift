import SwiftUI

struct ChatView: View {
    @State private var showProfile = false
    @EnvironmentObject var staffVM: StaffViewModel

    var body: some View {
        NavigationStack {
            VStack {
                Text("Chat Screen")
                    .navigationTitle("Chat")
            }
            .navigationTitle("Chat")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button(action: {
                        showProfile = true
                    }) {
                        Image(systemName: "person.crop.circle")
                            .font(.title2)
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
                /*
                    .navigationBarBackButtonHidden(true)
                    .toolbar{
                        ToolbarItem(placement: .navigationBarLeading) {
                            Button(action: {
                                // go back
                                showProfile = false
                            }) {
                                HStack {
                                    Image(systemName: "chevron.backward")
                                    Text("Back")
                                }
                            }
                        }
                    }
                 */
            }
        }
}
