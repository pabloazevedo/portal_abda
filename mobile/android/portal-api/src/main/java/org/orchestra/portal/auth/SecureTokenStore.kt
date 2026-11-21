package org.orchestra.portal.auth

/**
 * Contrato de armazenamento do refresh token.
 * Em produção use EncryptedSharedPreferences / Android Keystore.
 * Não use SharedPreferences em texto claro.
 */
interface SecureTokenStore {
    fun saveRefreshToken(token: String)
    fun readRefreshToken(): String?
    fun clear()
}

/** Implementação em memória — útil para testes unitários. */
class InMemoryTokenStore : SecureTokenStore {
    @Volatile private var refresh: String? = null

    override fun saveRefreshToken(token: String) {
        refresh = token
    }

    override fun readRefreshToken(): String? = refresh

    override fun clear() {
        refresh = null
    }
}
