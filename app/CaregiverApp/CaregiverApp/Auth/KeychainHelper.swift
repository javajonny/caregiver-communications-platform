import Foundation
import Security

final class KeychainHelper {
    static let standard = KeychainHelper()
    private init() {}
    
    // MARK: - Generic Methods
    
    func save(_ data: Data, service: String, account: String) {
        let query = [
            kSecValueData: data,
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
            kSecAttrAccessible: kSecAttrAccessibleAfterFirstUnlock
        ] as [CFString: Any]
        
        // Add item to keychain
        let status = SecItemAdd(query as CFDictionary, nil)
        
        if status == errSecDuplicateItem {
            // Item already currently exists, so update it
            let query = [
                kSecAttrService: service,
                kSecAttrAccount: account,
                kSecClass: kSecClassGenericPassword,
            ] as [CFString: Any]
            
            let attributesToUpdate = [kSecValueData: data] as [CFString: Any]
            
            SecItemUpdate(query as CFDictionary, attributesToUpdate as CFDictionary)
        }
    }
    
    func readData(service: String, account: String) -> Data? {
        let query = [
            kSecAttrService: service,
            kSecAttrAccount: account,
            kSecClass: kSecClassGenericPassword,
            kSecReturnData: true
        ] as [CFString: Any]
        
        var result: AnyObject?
        SecItemCopyMatching(query as CFDictionary, &result)
        
        return result as? Data
    }
    
    func delete(service: String, account: String) {
        let query = [
            kSecAttrService: service,
            kSecAttrAccount: account,
            kSecClass: kSecClassGenericPassword
        ] as [CFString: Any]
        
        SecItemDelete(query as CFDictionary)
    }
    
    // MARK: - Convenience Methods (String)
    
    func save(_ value: String, service: String, account: String) {
        if let data = value.data(using: .utf8) {
            save(data, service: service, account: account)
        }
    }
    
    func read(service: String, account: String) -> String? {
        guard let data = readData(service: service, account: account) else { return nil }
        return String(data: data, encoding: .utf8)
    }
}
