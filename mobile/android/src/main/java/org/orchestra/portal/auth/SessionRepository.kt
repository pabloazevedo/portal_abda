package org.orchestra.portal.auth

import org.orchestra.portal.api.ApiUser
import org.orchestra.portal.api.TokenResponse
import java.util.concurrent.atomic.AtomicReference

/** Access token em memória; refresh no [SecureTokenStore]. */
class SessionRepository(
    private val tokenStore: SecureTokenStore = InMemoryTokenStore(),
) {
    private val accessToken = AtomicReference<String?>(null)
    private val user = AtomicReference<ApiUser?>(null)

    fun currentAccessToken(): String? = accessToken.get()
    fun currentUser(): ApiUser? = user.get()
    fun refreshToken(): String? = tokenStore.readRefreshToken()

    fun apply(tokens: TokenResponse) {
        accessToken.set(tokens.accessToken)
        user.set(tokens.user)
        tokenStore.saveRefreshToken(tokens.refreshToken)
    }

    fun clear() {
        accessToken.set(null)
        user.set(null)
        tokenStore.clear()
    }

    fun hasMusicianLink(): Boolean {
        val u = user.get() ?: return false
        return u.hasMusicianLink || u.musicianId != null
    }
}
