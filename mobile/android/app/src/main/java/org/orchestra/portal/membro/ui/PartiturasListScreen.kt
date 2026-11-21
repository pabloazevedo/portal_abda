package org.orchestra.portal.membro.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.orchestra.portal.api.PartituraAcesso

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PartiturasListScreen(
    username: String?,
    items: List<PartituraAcesso>,
    loading: Boolean,
    error: String?,
    onRefresh: () -> Unit,
    onOpenPdf: (acessoId: Int, documentoId: Int, title: String?) -> Unit,
    onLogout: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(username?.let { "Olá, $it" } ?: "Partituras") },
                actions = {
                    IconButton(onClick = onLogout) {
                        Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = "Sair")
                    }
                },
            )
        },
    ) { padding ->
        PullToRefreshBox(
            isRefreshing = loading,
            onRefresh = onRefresh,
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            when {
                items.isEmpty() && !loading -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("Nenhuma partitura distribuída.")
                            if (!error.isNullOrBlank()) {
                                Spacer(Modifier.height(8.dp))
                                Text(error, color = MaterialTheme.colorScheme.error)
                            }
                            Spacer(Modifier.height(16.dp))
                            Button(onClick = onRefresh) { Text("Atualizar") }
                        }
                    }
                }
                else -> {
                    LazyColumn(
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                        modifier = Modifier.fillMaxSize(),
                    ) {
                        if (!error.isNullOrBlank()) {
                            item {
                                Text(error, color = MaterialTheme.colorScheme.error)
                            }
                        }
                        items(items, key = { it.acessoId }) { acesso ->
                            PartituraCard(acesso = acesso, onOpenPdf = onOpenPdf)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun PartituraCard(
    acesso: PartituraAcesso,
    onOpenPdf: (acessoId: Int, documentoId: Int, title: String?) -> Unit,
) {
    Column(Modifier.fillMaxWidth()) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = acesso.evento?.titulo ?: "Evento #${acesso.acessoId}",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.weight(1f),
            )
            PartituraStatusChip(acesso.status)
        }
        acesso.evento?.local?.let {
            Text(it, style = MaterialTheme.typography.bodySmall)
        }
        Spacer(Modifier.height(8.dp))
        acesso.documentos.forEach { doc ->
            val title = doc.title ?: doc.label ?: doc.instrumentoNome ?: "Documento ${doc.id}"
            val enabled = acesso.status == "available"
            Button(
                onClick = { onOpenPdf(acesso.acessoId, doc.id, title) },
                enabled = enabled,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp),
            ) {
                Text(if (enabled) "Abrir: $title" else "$title (${acesso.status})")
            }
        }
    }
}
