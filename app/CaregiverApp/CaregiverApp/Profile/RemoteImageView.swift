import SwiftUI
import Foundation

final class ImageLoader: ObservableObject {
    @Published var image: UIImage?
    @Published var isLoading = false

    private var task: URLSessionDataTask?

    func load(from url: URL) {
        guard task == nil else { return }
        isLoading = true

        let config = URLSessionConfiguration.default
        let delegate = SelfSignedCertificateDelegate()
        let session = URLSession(configuration: config, delegate: delegate, delegateQueue: nil)

        task = session.dataTask(with: url) { [weak self] data, response, error in
            DispatchQueue.main.async {
                defer { self?.isLoading = false }
                guard let self = self else { return }
                if let data = data, let uiImage = UIImage(data: data) {
                    self.image = uiImage
                } else {
                    self.image = nil
                }
            }
        }
        task?.resume()
    }

    deinit {
        task?.cancel()
    }
}

struct RemoteImageView: View {
    let url: URL?
    @StateObject private var loader = ImageLoader()

    var body: some View {
        Group {
            if let url = url {
                content(for: url)
            } else {
                placeholder
            }
        }
    }

    private func content(for url: URL) -> some View {
        ZStack {
            if let image = loader.image {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
            } else if loader.isLoading {
                ProgressView()
            } else {
                placeholder
            }
        }
        .onAppear {
            if loader.image == nil && !loader.isLoading {
                loader.load(from: url)
            }
        }
    }

    private var placeholder: some View {
        Image("image_placeholder")
            .resizable()
            .scaledToFill()
            .foregroundColor(.gray)
    }
}
