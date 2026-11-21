package org.orchestra.portal.membro.ui

import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

@Composable
fun PartituraStatusChip(status: String) {
    val (label, container) = when (status) {
        "available" -> "Disponível" to Color(0xFF2E7D32)
        "not_yet_available" -> "Em breve" to Color(0xFFF9A825)
        "expired" -> "Expirada" to Color(0xFFC62828)
        else -> status to MaterialTheme.colorScheme.secondary
    }
    AssistChip(
        onClick = {},
        label = { Text(label) },
        colors = AssistChipDefaults.assistChipColors(
            containerColor = container.copy(alpha = 0.15f),
            labelColor = container,
        ),
    )
}
