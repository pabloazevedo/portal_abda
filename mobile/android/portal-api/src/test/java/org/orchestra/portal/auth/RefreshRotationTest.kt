package org.orchestra.portal.auth

import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.orchestra.portal.api.PortalApiClient
import org.orchestra.portal.api.PortalApiException

/**
 * Token antigo inválido após rotação: refresh grava o novo e o antigo deixa de funcionar.
 */
class RefreshRotationTest {
    private lateinit var server: MockWebServer
    private lateinit var store: InMemoryTokenStore
    private lateinit var client: PortalApiClient

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
        store = InMemoryTokenStore()
        store.saveRefreshToken("refresh-old")
        val session = SessionRepository(store)
        session.seedAccessToken("access-stale")
        client = PortalApiClient(baseUrl = server.url("/").toString().trimEnd('/'), session = session)
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun refreshRotatesAndOldTokenIsReplaced() {
        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(
                    """
                    {
                      "access_token": "access-new",
                      "refresh_token": "refresh-new",
                      "token_type": "Bearer",
                      "expires_in": 1800,
                      "user": {
                        "id": 1,
                        "username": "musico",
                        "role": "user",
                        "musician_id": 9,
                        "has_musician_link": true
                      }
                    }
                    """.trimIndent(),
                ),
        )

        val tokens = client.refresh()
        assertEquals("access-new", tokens.accessToken)
        assertEquals("refresh-new", store.readRefreshToken())
        assertEquals("access-new", client.sessionRepository().currentAccessToken())
    }

    @Test
    fun meRetriesOnceAfter401UsingRotatedRefresh() {
        // 1) GET /me → 401
        server.enqueue(MockResponse().setResponseCode(401).setBody("""{"detail":"expired"}"""))
        // 2) POST /refresh → novo token
        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(
                    """
                    {
                      "access_token": "access-new",
                      "refresh_token": "refresh-new",
                      "token_type": "Bearer",
                      "expires_in": 1800,
                      "user": {
                        "id": 1,
                        "username": "musico",
                        "role": "user",
                        "musician_id": 9,
                        "has_musician_link": true
                      }
                    }
                    """.trimIndent(),
                ),
        )
        // 3) retry GET /me → 200
        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(
                    """
                    {
                      "id": 1,
                      "username": "musico",
                      "role": "user",
                      "musician_id": 9,
                      "has_musician_link": true
                    }
                    """.trimIndent(),
                ),
        )

        val me = client.me()
        assertEquals(9, me.musicianId)
        assertEquals("refresh-new", store.readRefreshToken())
        assertEquals(3, server.requestCount)
        assertTrue(server.takeRequest().path!!.contains("/me"))
        assertTrue(server.takeRequest().path!!.contains("/refresh"))
        assertTrue(server.takeRequest().path!!.contains("/me"))
    }

    @Test
    fun logoutClearsStoreEvenIfNetworkFails() {
        server.enqueue(MockResponse().setResponseCode(500).setBody("boom"))
        client.logout()
        assertNull(store.readRefreshToken())
        assertNull(client.sessionRepository().currentAccessToken())
    }

    @Test(expected = PortalApiException.Unauthorized::class)
    fun refreshWithoutTokenThrowsUnauthorized() {
        store.clear()
        client.refresh()
    }

    @Test
    fun restoreSessionIfPossibleWithToken() {
        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(
                    """
                    {
                      "access_token": "a2",
                      "refresh_token": "r2",
                      "token_type": "Bearer",
                      "expires_in": 1800,
                      "user": {"id": 1, "username": "musico", "role": "user", "musician_id": 9, "has_musician_link": true}
                    }
                    """.trimIndent(),
                ),
        )
        assertTrue(client.restoreSessionIfPossible())
        assertNotNull(client.sessionRepository().currentAccessToken())
    }
}
