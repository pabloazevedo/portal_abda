import PortalMobile
import XCTest
@testable import PortalMembro

/// Espelha o teste de integração do pacote, rodando no host do app.
final class RefreshRotationIntegrationTests: XCTestCase {
    func testRefreshRotatesAndOldTokenIsRejected() async throws {
        let baseURL = AppConfig.apiBaseURL
        let reachable = await apiIsReachable(baseURL)
        try XCTSkipUnless(reachable, "API local indisponível em \(baseURL)")

        let store = SessionStore(
            keychain: KeychainStore(
                service: "org.orchestra.portal.app.test.refresh",
                account: UUID().uuidString
            )
        )
        let client = PortalAPIClient(baseURL: baseURL, sessionStore: store)
        let user = ProcessInfo.processInfo.environment["PORTAL_TEST_USER"] ?? "musico"
        let pass = ProcessInfo.processInfo.environment["PORTAL_TEST_PASSWORD"] ?? "musico123"

        let login = try await client.login(username: user, password: pass)
        let oldRefresh = login.refreshToken

        let rotated = try await client.refresh()
        XCTAssertNotEqual(rotated.refreshToken, oldRefresh)

        let reuseStatus = try await postRefresh(baseURL, token: oldRefresh)
        let newStatus = try await postRefresh(baseURL, token: rotated.refreshToken)
        XCTAssertEqual(reuseStatus, 401)
        XCTAssertEqual(newStatus, 200)

        try await client.logout()
    }

    private func apiIsReachable(_ baseURL: URL) async -> Bool {
        guard let url = URL(string: "/healthz", relativeTo: baseURL)?.absoluteURL else { return false }
        var request = URLRequest(url: url)
        request.timeoutInterval = 2
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    private func postRefresh(_ baseURL: URL, token: String) async throws -> Int {
        let url = URL(string: "/api/v1/auth/refresh", relativeTo: baseURL)!.absoluteURL
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: [
            "refresh_token": token,
            "client": "ios",
        ])
        let (_, response) = try await URLSession.shared.data(for: request)
        return (response as? HTTPURLResponse)?.statusCode ?? -1
    }
}
