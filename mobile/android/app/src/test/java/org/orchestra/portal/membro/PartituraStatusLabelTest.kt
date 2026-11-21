package org.orchestra.portal.membro

import org.junit.Assert.assertEquals
import org.junit.Test

class PartituraStatusLabelTest {
    @Test
    fun mapsKnownStatuses() {
        assertEquals("Disponível", labelFor("available"))
        assertEquals("Em breve", labelFor("not_yet_available"))
        assertEquals("Expirada", labelFor("expired"))
        assertEquals("other", labelFor("other"))
    }

    private fun labelFor(status: String): String = when (status) {
        "available" -> "Disponível"
        "not_yet_available" -> "Em breve"
        "expired" -> "Expirada"
        else -> status
    }
}
