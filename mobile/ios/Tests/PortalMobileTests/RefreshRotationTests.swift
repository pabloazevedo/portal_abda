import XCTest
@testable import PortalMobile

/// Integração + unitário: refresh rotaciona e o token antigo fica inválido.
final class RefreshRotationTests: XCTestCase {
    private let baseURL = URL(string: ProcessInfo.processInfo.environment["PORTAL_API_BASE_URL"]
        ?? "http://127.0.0.1:8000")!
    private let username = ProcessInfo.processInfo.environment["PORTAL_TEST_USER"] ?? "musico"
    private let password = ProcessInfo.processInfo.environment["PORTAL_TEST_PASSWORD"] ?? "musico123"

    func testSessionStoreReplacesRefreshOnApply() async throws {
        let keychain = KeychainStore(
            service: "org.orchestra.portal.test.session",
            account: UUID().uuidString
        )
        let store = SessionStore(keychain: keychain)
        let user = APIUser(
            id: 1,
            username: "t",
            email: nil,
            role: "user",
            musicianId: 2,
            hasMusicianLink: true
        )
        try await store.apply(
            TokenResponse(
                accessToken: "a1",
                refreshToken: "r1",
                tokenType: "Bearer",
                expiresIn: 1800,
                user: user
            )
        )
        let firstRefresh = await store.refreshToken
        XCTAssertEqual(firstRefresh, "r1")

        try await store.apply(
            TokenResponse(
                accessToken: "a2",
                refreshToken: "r2",
                tokenType: "Bearer",
                expiresIn: 1800,
                user: user
            )
        )
        let secondRefresh = await store.refreshToken
        let secondAccess = await store.currentAccessToken
        XCTAssertEqual(secondRefresh, "r2")
        XCTAssertEqual(secondAccess, "a2")

        await store.clear()
        let clearedRefresh = await store.refreshToken
        let clearedAccess = await store.currentAccessToken
        XCTAssertNil(clearedRefresh)
        XCTAssertNil(clearedAccess)
    }

    func testRefreshRotatesAndOldTokenIsRejectedAgainstAPI() async throws {
        let reachable = await apiIsReachable()
        try XCTSkipUnless(reachable, "API local indisponível em \(baseURL)")

        let keychain = KeychainStore(
            service: "org.orchestra.portal.test.refresh",
            account: UUID().uuidString
        )
        let store = SessionStore(keychain: keychain)
        let client = PortalAPIClient(baseURL: baseURL, sessionStore: store)

        let login = try await client.login(username: username, password: password)
        let oldRefresh = login.refreshToken
        XCTAssertFalse(oldRefresh.isEmpty)

        let rotated = try await client.refresh()
        XCTAssertNotEqual(rotated.refreshToken, oldRefresh, "Refresh deve rotacionar")
        let stored = await store.refreshToken
        XCTAssertEqual(stored, rotated.refreshToken)

        let reuseStatus = try await postRefresh(oldRefresh)
        XCTAssertEqual(reuseStatus, 401, "Token antigo deve ser rejeitado após rotação")

        let newStatus = try await postRefresh(rotated.refreshToken)
        XCTAssertEqual(newStatus, 200, "Token novo deve continuar válido")

        try await client.logout()
    }

    // MARK: - Helpers

    private func apiIsReachable() async -> Bool {
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

    private func postRefresh(_ token: String) async throws -> Int {
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
