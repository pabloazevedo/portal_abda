package org.orchestra.portal.membro.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import org.orchestra.portal.membro.session.SessionViewModel
import java.io.File

@Composable
fun RootScreen(vm: SessionViewModel = viewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val cacheFile = File(LocalContext.current.cacheDir, "portal-partitura.pdf")

    when {
        !state.bootstrapped -> {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        }
        state.pdfBytes != null -> {
            PdfViewerScreen(
                title = state.pdfTitle,
                cacheFile = cacheFile,
                onClose = vm::closePdf,
            )
        }
        state.missingMusicianLink -> {
            MissingMusicianLinkScreen(user = state.user, onLogout = vm::logout)
        }
        state.user != null -> {
            PartiturasListScreen(
                username = state.user?.username,
                items = state.partituras,
                loading = state.loading,
                error = state.error,
                onRefresh = vm::refreshPartituras,
                onOpenPdf = vm::openPdf,
                onLogout = vm::logout,
            )
        }
        else -> {
            LoginScreen(
                loading = state.loading,
                error = state.error,
                onLogin = vm::login,
            )
        }
    }
}
