import Foundation

/// Access token em memória; refresh no Keychain (com fallback em memória no Debug).
public actor SessionStore {
    private let keychain: KeychainStore
    private var accessToken: String?
    private var refreshTokenMemory: String?
    private var user: APIUser?

    public init(keychain: KeychainStore = KeychainStore()) {
        self.keychain = keychain
    }

    public var currentAccessToken: String? { accessToken }
    public var currentUser: APIUser? { user }
    public var refreshToken: String? { refreshTokenMemory ?? keychain.readRefreshToken() }

    public func apply(_ tokens: TokenResponse) throws {
        accessToken = tokens.accessToken
        refreshTokenMemory = tokens.refreshToken
        user = tokens.user
        try keychain.saveRefreshToken(tokens.refreshToken)
    }

    public func clear() {
        accessToken = nil
        refreshTokenMemory = nil
        user = nil
        keychain.clear()
    }

    public func hasMusicianLink() -> Bool {
        user?.hasMusicianLink == true || user?.musicianId != nil
    }
}
