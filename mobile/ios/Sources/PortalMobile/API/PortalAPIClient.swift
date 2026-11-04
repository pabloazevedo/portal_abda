import Foundation

/// Cliente HTTP para `/api/v1` (login, refresh, partituras).
public final class PortalAPIClient: @unchecked Sendable {
    public let baseURL: URL
    private let session: URLSession
    private let sessionStore: SessionStore
    private let jsonDecoder = JSONDecoder()
    private let jsonEncoder = JSONEncoder()
    private let clientName = "ios"

    public init(
        baseURL: URL,
        sessionStore: SessionStore = SessionStore(),
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL
        self.sessionStore = sessionStore
        self.session = session
    }

    public var store: SessionStore { sessionStore }

    public func login(username: String, password: String) async throws -> TokenResponse {
        let body = LoginRequest(username: username, password: password, client: clientName)
        let tokens: TokenResponse = try await post(path: "/api/v1/auth/login", body: body, authorized: false)
        try await sessionStore.apply(tokens)
        return tokens
    }

    public func refresh() async throws -> TokenResponse {
        guard let refresh = await sessionStore.refreshToken else {
            throw PortalAPIError.unauthorized
        }
        let body = RefreshRequest(refreshToken: refresh, client: clientName)
        let tokens: TokenResponse = try await post(path: "/api/v1/auth/refresh", body: body, authorized: false)
        try await sessionStore.apply(tokens)
        return tokens
    }

    public func logout() async throws {
        if let refresh = await sessionStore.refreshToken {
            let body = LogoutRequest(refreshToken: refresh)
            do {
                let _: LogoutOK = try await post(path: "/api/v1/auth/logout", body: body, authorized: false)
            } catch {
                // Revoga localmente mesmo se a rede falhar.
            }
        }
        await sessionStore.clear()
    }

    public func me() async throws -> APIUser {
        try await get(path: "/api/v1/auth/me")
    }

    public func listPartituras() async throws -> PartiturasResponse {
        try await get(path: "/api/v1/me/partituras")
    }

    public func createViewTicket(acessoId: Int, documentoId: Int) async throws -> ViewTicketResponse {
        try await post(
            path: "/api/v1/me/partituras/\(acessoId)/documentos/\(documentoId)/view-ticket",
            body: EmptyBody(),
            authorized: true
        )
    }

    /// Download autenticado do PDF (bytes em memória; não grava em Files).
    public func downloadPDF(acessoId: Int, documentoId: Int) async throws -> Data {
        try await rawRequest(
            path: "/api/v1/me/partituras/\(acessoId)/documentos/\(documentoId)/pdf",
            method: "GET",
            body: Optional<EmptyBody>.none,
            authorized: true,
            didRefresh: false,
            accept: "application/pdf"
        )
    }

    /// Se houver refresh no Keychain, renova a sessão.
    @discardableResult
    public func restoreSessionIfPossible() async throws -> Bool {
        guard await sessionStore.refreshToken != nil else { return false }
        _ = try await refresh()
        return true
    }

    public func absoluteURL(path: String) throws -> URL {
        guard let url = URL(string: path, relativeTo: baseURL)?.absoluteURL else {
            throw PortalAPIError.invalidURL
        }
        return url
    }

    // MARK: - Internals

    private struct EmptyBody: Encodable {}
    private struct LogoutOK: Decodable { let ok: Bool? }

    private func get<T: Decodable>(path: String) async throws -> T {
        let data = try await rawRequest(
            path: path,
            method: "GET",
            body: Optional<EmptyBody>.none,
            authorized: true,
            didRefresh: false,
            accept: "application/json"
        )
        do {
            return try jsonDecoder.decode(T.self, from: data)
        } catch {
            throw PortalAPIError.decoding(error)
        }
    }

    private func post<Body: Encodable, T: Decodable>(
        path: String,
        body: Body,
        authorized: Bool
    ) async throws -> T {
        let data = try await rawRequest(
            path: path,
            method: "POST",
            body: body,
            authorized: authorized,
            didRefresh: false,
            accept: "application/json"
        )
        do {
            return try jsonDecoder.decode(T.self, from: data)
        } catch {
            throw PortalAPIError.decoding(error)
        }
    }

    private func rawRequest<Body: Encodable>(
        path: String,
        method: String,
        body: Body?,
        authorized: Bool,
        didRefresh: Bool,
        accept: String = "application/json"
    ) async throws -> Data {
        guard let url = URL(string: path, relativeTo: baseURL)?.absoluteURL else {
            throw PortalAPIError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue(accept, forHTTPHeaderField: "Accept")
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try jsonEncoder.encode(body)
        }
        if authorized, let token = await sessionStore.currentAccessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw PortalAPIError.http(status: -1, detail: nil)
        }

        if http.statusCode == 401, authorized, !didRefresh {
            _ = try await refresh()
            return try await rawRequest(
                path: path,
                method: method,
                body: body,
                authorized: authorized,
                didRefresh: true,
                accept: accept
            )
        }

        guard (200..<300).contains(http.statusCode) else {
            let detail = try? jsonDecoder.decode(APIErrorBody.self, from: data).detail
            if http.statusCode == 401 { throw PortalAPIError.unauthorized }
            let lower = detail?.lowercased() ?? ""
            if http.statusCode == 403, lower.contains("vínculo") || lower.contains("vinculo") || lower.contains("membro") {
                throw PortalAPIError.missingMusicianLink
            }
            throw PortalAPIError.http(status: http.statusCode, detail: detail)
        }
        return data
    }
}
