package org.orchestra.portal.api

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.orchestra.portal.auth.SessionRepository
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Cliente HTTP para `/api/v1` (login, refresh, partituras).
 * Depende de OkHttp + kotlinx.serialization no módulo Gradle do app.
 */
class PortalApiClient(
    private val baseUrl: String,
    private val session: SessionRepository = SessionRepository(),
    private val http: OkHttpClient = defaultClient(),
    private val json: Json = Json { ignoreUnknownKeys = true },
) {
    private val clientName = "android"
    private val jsonMedia = "application/json; charset=utf-8".toMediaType()

    fun sessionRepository(): SessionRepository = session

    @Throws(PortalApiException::class, IOException::class)
    fun login(username: String, password: String): TokenResponse {
        val body = LoginRequest(username = username, password = password, client = clientName)
        val tokens = post<LoginRequest, TokenResponse>("/api/v1/auth/login", body, authorized = false)
        session.apply(tokens)
        return tokens
    }

    @Throws(PortalApiException::class, IOException::class)
    fun refresh(): TokenResponse {
        val refresh = session.refreshToken() ?: throw PortalApiException.Unauthorized()
        val body = RefreshRequest(refreshToken = refresh, client = clientName)
        val tokens = post<RefreshRequest, TokenResponse>("/api/v1/auth/refresh", body, authorized = false)
        session.apply(tokens)
        return tokens
    }

    @Throws(IOException::class)
    fun logout() {
        session.refreshToken()?.let { token ->
            try {
                post<LogoutRequest, LogoutOk>(
                    "/api/v1/auth/logout",
                    LogoutRequest(refreshToken = token),
                    authorized = false,
                )
            } catch (_: Exception) {
                // Limpa local mesmo se a rede falhar.
            }
        }
        session.clear()
    }

    @Throws(PortalApiException::class, IOException::class)
    fun me(): ApiUser = get("/api/v1/auth/me")

    @Throws(PortalApiException::class, IOException::class)
    fun listPartituras(): PartiturasResponse = get("/api/v1/me/partituras")

    @Throws(PortalApiException::class, IOException::class)
    fun createViewTicket(acessoId: Int, documentoId: Int): ViewTicketResponse {
        return post(
            "/api/v1/me/partituras/$acessoId/documentos/$documentoId/view-ticket",
            EmptyBody,
            authorized = true,
        )
    }

    /** Download autenticado do PDF (bytes; gravar só em cache privado do app). */
    @Throws(PortalApiException::class, IOException::class)
    fun downloadPDF(acessoId: Int, documentoId: Int): ByteArray =
        executeBytes(
            "/api/v1/me/partituras/$acessoId/documentos/$documentoId/pdf",
            authorized = true,
            didRefresh = false,
        )

    /** Se houver refresh no store, renova a sessão. */
    @Throws(PortalApiException::class, IOException::class)
    fun restoreSessionIfPossible(): Boolean {
        if (session.refreshToken() == null) return false
        refresh()
        return true
    }

    fun absoluteUrl(path: String): String {
        val base = baseUrl.trimEnd('/')
        return if (path.startsWith("http")) path else "$base$path"
    }

    private object EmptyBody

    private inline fun <reified T> get(path: String): T =
        execute(path, "GET", bodyJson = null, authorized = true, didRefresh = false) {
            json.decodeFromString(it)
        }

    private inline fun <reified B, reified T> post(path: String, body: B, authorized: Boolean): T {
        val payload = when (body) {
            is EmptyBody -> "{}"
            else -> json.encodeToString(body)
        }
        return execute(path, "POST", bodyJson = payload, authorized = authorized, didRefresh = false) {
            json.decodeFromString(it)
        }
    }

    private fun <T> execute(
        path: String,
        method: String,
        bodyJson: String?,
        authorized: Boolean,
        didRefresh: Boolean,
        decode: (String) -> T,
    ): T {
        val url = absoluteUrl(path)
        val builder = Request.Builder().url(url).header("Accept", "application/json")
        if (bodyJson != null) {
            builder.method(method, bodyJson.toRequestBody(jsonMedia))
                .header("Content-Type", "application/json")
        } else {
            builder.method(method, null)
        }
        if (authorized) {
            session.currentAccessToken()?.let {
                builder.header("Authorization", "Bearer $it")
            }
        }

        http.newCall(builder.build()).execute().use { response ->
            val raw = response.body?.string().orEmpty()
            if (response.code == 401 && authorized && !didRefresh) {
                refresh()
                return execute(path, method, bodyJson, authorized = true, didRefresh = true, decode = decode)
            }
            if (!response.isSuccessful) {
                val detail = runCatching { json.decodeFromString<ApiErrorBody>(raw).detail }.getOrNull()
                if (response.code == 401) throw PortalApiException.Unauthorized()
                val lower = detail.orEmpty().lowercase()
                if (response.code == 403 && (lower.contains("vínculo") || lower.contains("vinculo") || lower.contains("membro"))) {
                    throw PortalApiException.MissingMusicianLink()
                }
                throw PortalApiException.Http(response.code, detail)
            }
            return decode(raw)
        }
    }

    private fun executeBytes(path: String, authorized: Boolean, didRefresh: Boolean): ByteArray {
        val url = absoluteUrl(path)
        val builder = Request.Builder().url(url).header("Accept", "application/pdf").get()
        if (authorized) {
            session.currentAccessToken()?.let {
                builder.header("Authorization", "Bearer $it")
            }
        }
        http.newCall(builder.build()).execute().use { response ->
            if (response.code == 401 && authorized && !didRefresh) {
                refresh()
                return executeBytes(path, authorized = true, didRefresh = true)
            }
            if (!response.isSuccessful) {
                val raw = response.body?.string().orEmpty()
                val detail = runCatching { json.decodeFromString<ApiErrorBody>(raw).detail }.getOrNull()
                if (response.code == 401) throw PortalApiException.Unauthorized()
                throw PortalApiException.Http(response.code, detail)
            }
            return response.body?.bytes() ?: ByteArray(0)
        }
    }

    companion object {
        fun defaultClient(): OkHttpClient =
            OkHttpClient.Builder()
                .connectTimeout(20, TimeUnit.SECONDS)
                .readTimeout(60, TimeUnit.SECONDS)
                .build()
    }
}
