# Portal Mobile — Android (library)

Código da Fase 0/1 do [plano Android](../../docs/plano-trabalho-android.md).

## Conteúdo

- `PortalApiClient` — login / refresh / logout / me / partituras / view-ticket (`client: "android"`)
- `SecureTokenStore` / `InMemoryTokenStore` — contrato para EncryptedSharedPreferences
- `SessionRepository` — access token em memória

## Uso no Android Studio

1. Crie um projeto Compose (ou importe este diretório como módulo `:portal-api`)
2. Use `build.gradle.kts.example` como base
3. Flavor `dev`: `http://10.0.2.2:8000` (emulador → host)

```kotlin
val client = PortalApiClient(baseUrl = "http://10.0.2.2:8000")
val tokens = client.login("musico", "…")
val lista = client.listPartituras()
```

## Testes

Com o módulo Gradle configurado:

```bash
./gradlew :portal-api:test
```

Os testes de modelos em `src/test` cobrem o decode JSON da API.
