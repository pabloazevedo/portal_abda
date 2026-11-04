import Foundation
import Security

/// Persistência do refresh token no Keychain (nunca use UserDefaults em Release).
public final class KeychainStore: @unchecked Sendable {
    private let service: String
    private let account: String
    /// Fallback só para Debug/simulador quando o Keychain recusa (ex.: sem signing team).
    private var memoryFallback: String?

    public init(
        service: String = Bundle.main.bundleIdentifier ?? "org.orchestra.portal.membro",
        account: String = "refresh_token"
    ) {
        self.service = service
        self.account = account
    }

    public func saveRefreshToken(_ token: String) throws {
        memoryFallback = token
        let data = Data(token.utf8)
        let query = baseQuery()

        let update: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]
        let updateStatus = SecItemUpdate(query as CFDictionary, update as CFDictionary)
        if updateStatus == errSecSuccess {
            return
        }

        if updateStatus == errSecItemNotFound {
            var attrs = query
            attrs[kSecValueData as String] = data
            attrs[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
            #if os(iOS) || os(macOS)
            if #available(iOS 13.0, macOS 10.15, *) {
                attrs[kSecUseDataProtectionKeychain as String] = true
            }
            #endif
            let addStatus = SecItemAdd(attrs as CFDictionary, nil)
            if addStatus == errSecSuccess || addStatus == errSecDuplicateItem {
                if addStatus == errSecDuplicateItem {
                    _ = SecItemUpdate(query as CFDictionary, update as CFDictionary)
                }
                return
            }
            #if DEBUG
            // Simulador / app sem Development Team: segue com token em memória nesta sessão.
            return
            #else
            throw KeychainError.unexpectedStatus(addStatus)
            #endif
        }

        #if DEBUG
        return
        #else
        throw KeychainError.unexpectedStatus(updateStatus)
        #endif
    }

    public func readRefreshToken() -> String? {
        let query: [String: Any] = baseQuery().merging([
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]) { _, new in new }

        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        if status == errSecSuccess, let data = item as? Data {
            return String(data: data, encoding: .utf8)
        }
        return memoryFallback
    }

    public func clear() {
        memoryFallback = nil
        SecItemDelete(baseQuery() as CFDictionary)
    }

    private func baseQuery() -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }
}

public enum KeychainError: Error, LocalizedError {
    case unexpectedStatus(OSStatus)

    public var errorDescription: String? {
        switch self {
        case .unexpectedStatus(let status):
            return "Falha ao gravar no Keychain (OSStatus \(status)). No simulador, defina um Team em Signing & Capabilities."
        }
    }
}
