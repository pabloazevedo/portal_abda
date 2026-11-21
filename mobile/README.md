# Clientes mobile — Orchestra Portal

| Plataforma | Plano | Código |
|---|---|---|
| iOS | [docs/plano-trabalho-ios.md](../docs/plano-trabalho-ios.md) | [ios/](ios/) — SPM + app Xcode `PortalMembro` |
| Android | [docs/plano-trabalho-android.md](../docs/plano-trabalho-android.md) | [android/](android/) — Gradle `:app` + `:portal-api` |

Contrato: [docs/MOBILE_API.md](../docs/MOBILE_API.md).  
Backend local: `docker compose up -d` → `http://localhost:8000`.

**Android build/emulador:** Ubuntu `192.168.50.32` (usuário `pablo`) — ver [android/README.md](android/README.md) e `scripts/android/`.
