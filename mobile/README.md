# Clientes mobile — Orchestra Portal

Implementação inicial (Fase 0/1) dos planos nativos.

| Plataforma | Plano | Código |
|---|---|---|
| iOS | [docs/plano-trabalho-ios.md](../docs/plano-trabalho-ios.md) | [ios/](ios/) (Swift Package) |
| Android | [docs/plano-trabalho-android.md](../docs/plano-trabalho-android.md) | [android/](android/) (Kotlin library) |

Contrato da API: [docs/MOBILE_API.md](../docs/MOBILE_API.md).  
Backend de desenvolvimento: `docker compose up -d` → `http://localhost:8000` (`/api/docs`).

Próximo passo de cada plano: criar o app Xcode / projeto Gradle Compose e ligar a UI às libraries acima.
