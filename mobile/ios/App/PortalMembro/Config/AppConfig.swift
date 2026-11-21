import Foundation

/// Ambientes. Debug pode usar HTTP local; Release exige HTTPS (ATS sem exceções).
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

    /// Simulador/Debug: `http://127.0.0.1:8000` (override `PORTAL_API_BASE_URL`).
    /// Release: HTTPS obrigatório (`https://portal.example.org` até o domínio real).
    static var apiBaseURL: URL {
        let fallback: String
        switch environment {
        case .debug:
            fallback = "http://127.0.0.1:8000"
        case .release:
            fallback = "https://portal.example.org"
        }
        let raw = ProcessInfo.processInfo.environment["PORTAL_API_BASE_URL"] ?? fallback
        let url = URL(string: raw)!
        #if !DEBUG
        assert(url.scheme?.lowercased() == "https", "Release exige HTTPS (ATS).")
        #endif
        return url
    }

    /// Não logar tokens, senhas, e-mails ou outros PII — usar só mensagens genéricas de erro na UI.
    static let logsTokensOrPII = false
}
