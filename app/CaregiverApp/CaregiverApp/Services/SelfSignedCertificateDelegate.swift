import Foundation

class SelfSignedCertificateDelegate: NSObject, URLSessionDelegate {
    func urlSession(_ session: URLSession, didReceive challenge: URLAuthenticationChallenge, completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        if challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
           let serverTrust = challenge.protectionSpace.serverTrust {
            // Only accept self-signed certificates for localhost and local IP addresses
            let host = challenge.protectionSpace.host
            if host == "localhost" || host == "127.0.0.1" || host.starts(with: "10.") || host.starts(with: "192.168.") || host.starts(with: "172.") {
                let credential = URLCredential(trust: serverTrust)
                completionHandler(.useCredential, credential)
                return
            }
        }
        completionHandler(.performDefaultHandling, nil)
    }
}
