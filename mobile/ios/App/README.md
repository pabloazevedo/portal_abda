# PortalMembro — app iOS (Fase 0)

Projeto Xcode gerado com [XcodeGen](https://github.com/yonaskolb/XcodeGen) a partir de `project.yml`.  
Depende do pacote local **PortalMobile** em `../` (`Sources/PortalMobile`).

## Abrir no Xcode

```bash
open mobile/ios/App/PortalMembro.xcodeproj
```

Se alterar `project.yml`, regenere:

```bash
# com XcodeGen no PATH, ou:
../../../../.tools/xcodegen/bin/xcodegen generate   # a partir de mobile/ios/App
```

## Build / testes (simulador)

```bash
cd mobile/ios/App
xcodebuild -project PortalMembro.xcodeproj -scheme PortalMembro \
  -destination 'platform=iOS Simulator,name=iPhone 16' \
  CODE_SIGNING_ALLOWED=NO build test
```

## Ambientes

| Config | Base URL |
|---|---|
| Debug | `http://127.0.0.1:8000` (override: env `PORTAL_API_BASE_URL`) |
| Release | `https://portal.example.org` (trocar no deploy) |

Device físico em Debug: defina `PORTAL_API_BASE_URL=http://<IP-do-Mac>:8000`.

## Estrutura

```
App/
├── project.yml                 # fonte do .xcodeproj
├── PortalMembro.xcodeproj
├── PortalMembro/
│   ├── Session/AppSession.swift
│   ├── Views/LoginView.swift
│   ├── Views/PartiturasListView.swift
│   ├── Views/PDFViewerScreen.swift   # PDFKit
│   └── Info.plist                    # ATS local networking
└── PortalMembroTests/
```

## Fluxo (Fases 1–2)

1. Login → `POST /api/v1/auth/login` (`client: ios`)
2. Lista → `GET /api/v1/me/partituras` (badges + pull-to-refresh)
3. Abrir PDF → download Bearer + PDFKit em memória
4. Sair → logout + limpa Keychain

Backend local: `docker compose up -d` em `http://127.0.0.1:8000`.
