import SwiftUI


struct ProfileHeaderCard: View {
    let profileImageURL: URL?
    let firstName: String
    let lastName: String
    let email: String
    let phone: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 16){
            HStack(alignment: .center, spacing: 16) {
                RemoteImageView(url: profileImageURL)
                .aspectRatio(contentMode: .fill)
                .frame(width: 90, height: 90)
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .shadow(radius: 4)
                
                VStack(alignment: .leading) {
                    Text(firstName)
                        .font(.system(size: 30, weight: .bold))
                        .foregroundColor(Color("DefaultTextColor"))
                    Text(lastName)
                        .font(.system(size: 30, weight: .bold))
                        .foregroundColor(Color("DefaultTextColor"))
                }
            }
            VStack(alignment: .leading, spacing: 16) { // spacing between groups
                // Name group
                VStack(alignment: .leading, spacing: 2) { // close spacing inside group
                    Label("Name", systemImage: "person")
                        .foregroundColor(Color("DefaultTextColor"))
                        .fontWeight(.medium)
                        .font(.system(size: 18))
                    Text(firstName + " " + lastName)
                        .foregroundColor(.white)
                        .fontWeight(.medium)
                        .font(.system(size: 18))
                }
                
                // Email group
                VStack(alignment: .leading, spacing: 2) {
                    Label("Work Email", systemImage: "envelope")
                        .foregroundColor(Color("DefaultTextColor"))
                        .fontWeight(.medium)
                        .font(.system(size: 18))
                    Text(email)
                        .foregroundColor(Color(.white))
                        .fontWeight(.medium)
                        .font(.system(size: 18))
                }
                
                // Phone group
                VStack(alignment: .leading, spacing: 2) {
                    Label("Work Phone Number", systemImage: "phone")
                        .foregroundColor(Color("DefaultTextColor"))
                        .fontWeight(.medium)
                        .font(.system(size: 18))
                    Text(phone ?? "Not provided")
                        .foregroundColor(Color(.white))
                        .fontWeight(.medium)
                        .font(.system(size: 18))
                }
            }
                    .font(.system(size: 14))
                    .foregroundColor(.secondary)
                
                
                // Spacer()
            }
        
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 24)
                .fill(Color("CardBackground").opacity(0.70))
        )
        .padding(.horizontal)
    }
}

