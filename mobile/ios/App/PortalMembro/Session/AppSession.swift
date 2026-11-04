import Foundation
import PortalMobile
import SwiftUI

@MainActor
final class AppSession: ObservableObject {
    enum Phase {
        case bootstrapping
        case loggedOut
        case loggedIn
    }

    @Published private(set) var phase: Phase = .bootstrapping
    @Published private(set) var user: APIUser?
    @Published var errorMessage: String?

    let client: PortalAPIClient

    init(baseURL: URL = AppConfig.apiBaseURL) {
        self.client = PortalAPIClient(baseURL: baseURL)
    }

    func bootstrap() async {
        phase = .bootstrapping
        errorMessage = nil
        do {
            if try await client.restoreSessionIfPossible() {
                user = await client.store.currentUser
                phase = .loggedIn
                return
            }
        } catch {
            await client.store.clear()
        }
        user = nil
        phase = .loggedOut
    }

    func login(username: String, password: String) async {
        errorMessage = nil
        do {
            let tokens = try await client.login(username: username, password: password)
            if !tokens.user.hasMusicianLink && tokens.user.musicianId == nil {
                try? await client.logout()
                errorMessage = "Conta sem vínculo com membro. Peça acesso ao App na secretaria."
                phase = .loggedOut
                user = nil
                return
            }
            user = tokens.user
            phase = .loggedIn
        } catch let err as PortalAPIError {
            errorMessage = err.localizedDescription
            phase = .loggedOut
        } catch let err as KeychainError {
            errorMessage = err.localizedDescription
            phase = .loggedOut
        } catch let urlError as URLError {
            errorMessage = Self.describe(urlError)
            phase = .loggedOut
        } catch {
            errorMessage = error.localizedDescription
            phase = .loggedOut
        }
    }

    func logout() async {
        errorMessage = nil
        try? await client.logout()
        user = nil
        phase = .loggedOut
    }

    func handleUnauthorized() async {
        await logout()
        errorMessage = "Sessão expirada. Entre novamente."
    }

    private static func describe(_ error: URLError) -> String {
        let host = AppConfig.apiBaseURL.absoluteString
        switch error.code {
        case .cannotConnectToHost, .networkConnectionLost, .timedOut, .notConnectedToInternet:
            return "Sem conexão com \(host) (código \(error.errorCode)). Confirme o Docker e rode de novo."
        case .appTransportSecurityRequiresSecureConnection:
            return "HTTP bloqueado pelo ATS. Rebuild do app necessário para liberar localhost."
        default:
            return "Erro de rede (\(error.errorCode)): \(error.localizedDescription)"
        }
    }
}
