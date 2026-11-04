# Portal Mobile — iOS (SPM)

Pacote Swift da Fase 0/1 do [plano iOS](../../docs/plano-trabalho-ios.md).

## Conteúdo

- `PortalAPIClient` — login / refresh / logout / me / partituras / view-ticket (`client: "ios"`)
- `KeychainStore` — refresh token no Keychain
- `SessionStore` — access token em memória

## App Xcode (Fase 0)

O app **PortalMembro** vive em [`App/`](App/) e já depende deste pacote via SPM local.

```bash
open mobile/ios/App/PortalMembro.xcodeproj
```

Detalhes: [App/README.md](App/README.md).

## Uso do pacote

```swift
import PortalMobile

let client = PortalAPIClient(baseURL: URL(string: "http://127.0.0.1:8000")!)
let tokens = try await client.login(username: "musico", password: "…")
let lista = try await client.listPartituras()
```

## Testes

```bash
# Pacote SPM
cd mobile/ios && swift test

# App + unit tests no simulador
cd mobile/ios/App
xcodebuild -project PortalMembro.xcodeproj -scheme PortalMembro \
  -destination 'platform=iOS Simulator,name=iPhone 16' \
  CODE_SIGNING_ALLOWED=NO test
```
