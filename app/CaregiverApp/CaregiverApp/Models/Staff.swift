import Foundation

struct Staff: Identifiable, Codable {
    let id: Int
    let firstName: String
    let lastName: String
    let email: String
    let workPhone: String?
    let profileImageURL: URL?
    
    enum CodingKeys: String, CodingKey {
        case id
        case firstName = "first_name"
        case lastName = "last_name"
        case email
        case workPhone = "work_phone"
        case profileImageURL = "profile_image_url"
    }
    
    init(id: Int, firstName: String, lastName: String, email: String, workPhone: String?, profileImageURL: URL?) {
        self.id = id
        self.firstName = firstName
        self.lastName = lastName
        self.email = email
        self.workPhone = workPhone
        self.profileImageURL = profileImageURL
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(Int.self, forKey: .id)
        firstName = try container.decode(String.self, forKey: .firstName)
        lastName = try container.decode(String.self, forKey: .lastName)
        email = try container.decode(String.self, forKey: .email)
        workPhone = try container.decodeIfPresent(String.self, forKey: .workPhone)
        
        // Handle profile_image_url -> URL conversion
        if let urlString = try container.decodeIfPresent(String.self, forKey: .profileImageURL),
           !urlString.isEmpty,
           let url = URL(string: urlString) {
            profileImageURL = url
        } else {
            profileImageURL = nil
        }
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(firstName, forKey: .firstName)
        try container.encode(lastName, forKey: .lastName)
        try container.encode(email, forKey: .email)
        try container.encodeIfPresent(workPhone, forKey: .workPhone)
        if let url = profileImageURL {
            try container.encode(url.absoluteString, forKey: .profileImageURL)
        }
    }
}

