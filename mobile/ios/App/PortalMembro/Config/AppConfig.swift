import Foundation

/// Ambientes da Fase 0. Debug aponta para o stack Docker local.
enum AppConfig {
    enum Environment {
        case debug
        case release
    }

    static var environment: Environment {
        #if DEBUG
        .debug
        #else
        .release
        #endif
    }

    /// Simulador: localhost. Device físico na mesma LAN: troque pelo IP do Mac.
    static var apiBaseURL: URL {
        switch environment {
        case .debug:
            URL(string: ProcessInfo.processInfo.environment["PORTAL_API_BASE_URL"]
                ?? "http://127.0.0.1:8000")!
        case .release:
            URL(string: ProcessInfo.processInfo.environment["PORTAL_API_BASE_URL"]
                ?? "https://portal.example.org")!
        }
    }
}
