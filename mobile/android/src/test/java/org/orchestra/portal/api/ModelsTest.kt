package org.orchestra.portal.api

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ModelsTest {
    private val json = Json { ignoreUnknownKeys = true }

    @Test
    fun tokenResponseDecoding() {
        val raw = """
        {
          "access_token": "a",
          "refresh_token": "r",
          "token_type": "Bearer",
          "expires_in": 1800,
          "user": {
            "id": 1,
            "username": "musico",
            "email": "m@test.local",
            "role": "user",
            "musician_id": 9,
            "has_musician_link": true
          }
        }
        """.trimIndent()
        val tokens = json.decodeFromString<TokenResponse>(raw)
        assertEquals(9, tokens.user.musicianId)
        assertTrue(tokens.user.hasMusicianLink)
    }

    @Test
    fun partiturasDecoding() {
        val raw = """
        {
          "musician_id": 9,
          "count": 1,
          "server_time": "2026-11-03T00:00:00+00:00",
          "items": [{
            "acesso_id": 3,
            "status": "available",
            "documento_count": 1,
            "evento": {"id": 1, "titulo": "Ensaio"},
            "documentos": [{
              "id": 10,
              "title": "Violino",
              "download_path": "/api/v1/me/partituras/3/documentos/10/pdf"
            }]
          }]
        }
        """.trimIndent()
        val resp = json.decodeFromString<PartiturasResponse>(raw)
        assertEquals(1, resp.count)
        assertEquals("available", resp.items.first().status)
        assertEquals(10, resp.items.first().documentos.first().id)
    }
}
