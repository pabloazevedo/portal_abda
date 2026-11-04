package org.orchestra.portal.api

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class LoginRequest(
    val username: String,
    val password: String,
    val client: String = "android",
)

@Serializable
data class RefreshRequest(
    @SerialName("refresh_token") val refreshToken: String,
    val client: String = "android",
)

@Serializable
data class LogoutRequest(
    @SerialName("refresh_token") val refreshToken: String,
)

@Serializable
data class TokenResponse(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("token_type") val tokenType: String,
    @SerialName("expires_in") val expiresIn: Int,
    val user: ApiUser,
)

@Serializable
data class ApiUser(
    val id: Int,
    val username: String,
    val email: String? = null,
    val role: String,
    @SerialName("musician_id") val musicianId: Int? = null,
    @SerialName("has_musician_link") val hasMusicianLink: Boolean = false,
)

@Serializable
data class PartiturasResponse(
    @SerialName("musician_id") val musicianId: Int,
    val count: Int,
    val items: List<PartituraAcesso>,
    @SerialName("server_time") val serverTime: String,
)

@Serializable
data class PartituraAcesso(
    @SerialName("acesso_id") val acessoId: Int,
    val status: String,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("valid_from") val validFrom: String? = null,
    @SerialName("expires_at") val expiresAt: String? = null,
    @SerialName("documento_count") val documentoCount: Int = 0,
    val evento: PartituraEvento? = null,
    val documentos: List<PartituraDocumento> = emptyList(),
)

@Serializable
data class PartituraEvento(
    val id: Int? = null,
    val titulo: String? = null,
    @SerialName("data_inicio") val dataInicio: String? = null,
    val local: String? = null,
)

@Serializable
data class PartituraDocumento(
    val id: Int,
    val tipo: String? = null,
    val title: String? = null,
    val label: String? = null,
    @SerialName("instrumento_nome") val instrumentoNome: String? = null,
    @SerialName("download_path") val downloadPath: String? = null,
    @SerialName("view_ticket_path") val viewTicketPath: String? = null,
)

@Serializable
data class ViewTicketResponse(
    val ticket: String,
    @SerialName("expires_in") val expiresIn: Int,
    val title: String? = null,
    @SerialName("view_url") val viewUrl: String,
)

@Serializable
data class ApiErrorBody(
    val detail: String? = null,
)

@Serializable
data class LogoutOk(
    val ok: Boolean? = null,
)

sealed class PortalApiException(message: String) : Exception(message) {
    class Http(val status: Int, detail: String?) : PortalApiException(detail ?: "HTTP $status")
    class Unauthorized : PortalApiException("Sessão expirada. Entre novamente.")
    class MissingMusicianLink : PortalApiException("Conta sem vínculo com membro.")
}
