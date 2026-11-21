package org.orchestra.portal.membro.session

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.orchestra.portal.api.ApiUser
import org.orchestra.portal.api.PartituraAcesso
import org.orchestra.portal.api.PortalApiClient
import org.orchestra.portal.api.PortalApiException
import org.orchestra.portal.auth.SessionRepository
import org.orchestra.portal.membro.auth.EncryptedPrefsTokenStore
import org.orchestra.portal.membro.config.AppConfig
import java.io.File

data class SessionUiState(
    val bootstrapped: Boolean = false,
    val loading: Boolean = false,
    val user: ApiUser? = null,
    val missingMusicianLink: Boolean = false,
    val partituras: List<PartituraAcesso> = emptyList(),
    val error: String? = null,
    val pdfBytes: ByteArray? = null,
    val pdfTitle: String? = null,
)

class SessionViewModel(app: Application) : AndroidViewModel(app) {
    private val tokenStore = EncryptedPrefsTokenStore(app)
    private val session = SessionRepository(tokenStore)
    private val client = PortalApiClient(baseUrl = AppConfig.apiBaseUrl, session = session)

    private val _state = MutableStateFlow(SessionUiState())
    val state: StateFlow<SessionUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch { restore() }
    }

    private suspend fun restore() {
        _state.update { it.copy(loading = true, error = null) }
        try {
            val ok = withContext(Dispatchers.IO) { client.restoreSessionIfPossible() }
            if (ok) {
                val user = session.currentUser()
                if (user != null && !session.hasMusicianLink()) {
                    _state.update {
                        it.copy(
                            bootstrapped = true,
                            loading = false,
                            user = user,
                            missingMusicianLink = true,
                        )
                    }
                } else {
                    loadPartiturasInternal()
                }
            } else {
                _state.update { it.copy(bootstrapped = true, loading = false) }
            }
        } catch (e: Exception) {
            session.clear()
            _state.update {
                it.copy(bootstrapped = true, loading = false, error = humanize(e))
            }
        }
    }

    fun login(username: String, password: String) {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val tokens = withContext(Dispatchers.IO) { client.login(username.trim(), password) }
                if (!session.hasMusicianLink()) {
                    _state.update {
                        it.copy(
                            loading = false,
                            user = tokens.user,
                            missingMusicianLink = true,
                        )
                    }
                } else {
                    loadPartiturasInternal()
                }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = humanize(e)) }
            }
        }
    }

    fun logout() {
        viewModelScope.launch {
            withContext(Dispatchers.IO) { client.logout() }
            clearPdfCache()
            _state.value = SessionUiState(bootstrapped = true)
        }
    }

    fun refreshPartituras() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                loadPartiturasInternal()
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = humanize(e)) }
            }
        }
    }

    fun openPdf(acessoId: Int, documentoId: Int, title: String?) {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val bytes = withContext(Dispatchers.IO) { client.downloadPDF(acessoId, documentoId) }
                writePdfCache(bytes)
                _state.update {
                    it.copy(loading = false, pdfBytes = bytes, pdfTitle = title)
                }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = humanize(e)) }
            }
        }
    }

    fun closePdf() {
        clearPdfCache()
        _state.update { it.copy(pdfBytes = null, pdfTitle = null) }
    }

    private suspend fun loadPartiturasInternal() {
        val response = withContext(Dispatchers.IO) { client.listPartituras() }
        _state.update {
            it.copy(
                bootstrapped = true,
                loading = false,
                user = session.currentUser(),
                missingMusicianLink = false,
                partituras = response.items,
                error = null,
            )
        }
    }

    private fun pdfCacheFile(): File =
        File(getApplication<Application>().cacheDir, "portal-partitura.pdf")

    private fun writePdfCache(bytes: ByteArray) {
        pdfCacheFile().writeBytes(bytes)
    }

    private fun clearPdfCache() {
        runCatching { pdfCacheFile().delete() }
    }

    private fun humanize(e: Exception): String = when (e) {
        is PortalApiException.Unauthorized -> e.message ?: "Sessão expirada."
        is PortalApiException.MissingMusicianLink -> e.message ?: "Sem vínculo com membro."
        is PortalApiException.Http -> e.message ?: "Erro HTTP"
        else -> e.message ?: "Falha de rede"
    }
}
