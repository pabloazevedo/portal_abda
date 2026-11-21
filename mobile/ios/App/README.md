# PortalMembro — app iOS

Projeto Xcode gerado com [XcodeGen](https://github.com/yonaskolb/XcodeGen) a partir de `project.yml`.  
Pacote local **PortalMobile** em `../Sources/PortalMobile`.

**Testes e archive:** neste Mac. Build Android / esteira de segurança: Ubuntu `192.168.50.32`.

## Abrir / regenerar

```bash
open mobile/ios/App/PortalMembro.xcodeproj
# se alterar project.yml:
cd mobile/ios/App && xcodegen generate   # ou ../../.tools/xcodegen/bin/xcodegen
```

## Build / testes (simulador — Mac)

```bash
cd mobile/ios/App
xcodebuild -project PortalMembro.xcodeproj -scheme PortalMembro \
  -destination 'platform=iOS Simulator,name=iPhone 17' \
  CODE_SIGNING_ALLOWED=NO build test
```

## Ambientes e ATS (Fase 3)

| Config | Info.plist | Base URL |
|---|---|---|
| **Debug** | `Info-Debug.plist` — HTTP local (`NSAllowsLocalNetworking` + localhost) | `http://127.0.0.1:8000` (`PORTAL_API_BASE_URL`) |
| **Release** | `Info.plist` — **só HTTPS**, sem exception domains | `https://portal.example.org` |

Device físico em Debug: `PORTAL_API_BASE_URL=http://<IP-do-Mac>:8000`.

**Privacidade:** `PrivacyInfo.xcprivacy` — dados de conta para funcionalidade; `NSPrivacyTracking=false`.  
**Não logar** tokens, senhas ou PII (`AppConfig.logsTokensOrPII == false`).

## TestFlight

1. Defina `DEVELOPMENT_TEAM` no Xcode (Signing) ou no ambiente.
2. Troque `portal.example.org` pelo domínio real em `AppConfig` / env Release.
3. Arquive e envie:

```bash
DEVELOPMENT_TEAM=XXXXXXXX bash scripts/ios/archive-testflight.sh
```

v1.1 (não incluso): certificate pinning, Face ID para reabrir sessão.

## Fluxo

1. Login → `POST /api/v1/auth/login` (`client: ios`)
2. Lista → `GET /api/v1/me/partituras`
3. PDF → Bearer + PDFKit (memória)
4. Sair → logout + Keychain
