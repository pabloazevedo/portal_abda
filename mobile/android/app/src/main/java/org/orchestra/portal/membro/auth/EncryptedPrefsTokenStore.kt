package org.orchestra.portal.membro.auth

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys
import org.orchestra.portal.auth.SecureTokenStore

/** Refresh token em EncryptedSharedPreferences (Android Keystore). */
class EncryptedPrefsTokenStore(context: Context) : SecureTokenStore {
    private val prefs = EncryptedSharedPreferences.create(
        FILE_NAME,
        MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC),
        context.applicationContext,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    override fun saveRefreshToken(token: String) {
        prefs.edit().putString(KEY_REFRESH, token).apply()
    }

    override fun readRefreshToken(): String? = prefs.getString(KEY_REFRESH, null)

    override fun clear() {
        prefs.edit().remove(KEY_REFRESH).apply()
    }

    companion object {
        private const val FILE_NAME = "portal_secure_tokens"
        private const val KEY_REFRESH = "refresh_token"
    }
}
