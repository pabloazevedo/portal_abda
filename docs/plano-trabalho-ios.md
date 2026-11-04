# Plano de trabalho — App iOS (Portal do Membro)

**Objetivo:** app nativo iOS (Swift / SwiftUI) para músicos e coralistas consumirem a API em `/api/v1`, com tokens no Keychain, PDFKit e publicação na App Store.  
**Contrato:** [MOBILE_API.md](MOBILE_API.md) · Gaps: [gaps-e-oportunidades.md](gaps-e-oportunidades.md)  
**Código inicial:** [`mobile/ios/`](../mobile/ios/)

---

## Escopo MVP (v1)

| Inclui | Não inclui (v1) |
|---|---|
| Login / logout / refresh com rotação | Gestão admin (membros, patrimônio, acervo) |
| Lista de partituras por evento + status | Push notifications |
| Abertura de PDF (PDFKit) via Bearer ou ticket `/m/pdf/{ticket}` | Modo offline completo |
| Perfil (`GET /api/v1/auth/me`) | Face ID obrigatório (opcional na v1.1) |
| HTTPS + ATS em produção | Certificate pinning (v1.1) |

---

## Fases

### Fase 0 — Fundação (semana 1)
- [x] Plano documentado e pasta `mobile/ios/`
- [x] Cliente HTTP Swift alinhado à API (`PortalAPIClient`)
- [x] Armazenamento de refresh no Keychain (`KeychainStore`)
- [x] Projeto Xcode (App + Unit Tests) em `mobile/ios/App/` apontando para o pacote `PortalMobile` (`../Sources`)
- [x] Configuração de ambientes: `Debug` → `http://127.0.0.1:8000` (env `PORTAL_API_BASE_URL`); `Release` → HTTPS

**Critério de pronto:** build no simulador abre tela de login (mesmo que ainda stub de UI). ✅ `xcodebuild` build + test OK.

### Fase 1 — Autenticação (semana 1–2)
- [x] `POST /api/v1/auth/login` com `client: "ios"` (`LoginView` + `AppSession`)
- [x] Access token só em memória; refresh no Keychain (`KeychainStore` / `SessionStore`)
- [x] Interceptor: em `401`, `POST /api/v1/auth/refresh` e retry uma vez (`PortalAPIClient`)
- [x] Logout: `POST /api/v1/auth/logout` + limpar Keychain
- [x] Tela de erro para usuário sem `musician_id` / vínculo
- [x] Restauração de sessão no boot (`restoreSessionIfPossible`)
- [x] Testes unitários/integração do refresh (token antigo inválido após rotação): `RefreshRotationTests` + `RefreshRotationIntegrationTests`

**Critério de pronto:** login → lista → logout no simulador contra stack Docker local. ✅ UI ligada.

### Fase 2 — Partituras (semana 2–3)
- [x] `GET /api/v1/me/partituras` com UI por evento (`PartiturasListView`)
- [x] Badges: `available` | `not_yet_available` | `expired` (`PartituraStatusBadge`)
- [x] Download autenticado do PDF (`PortalAPIClient.downloadPDF`)
- [x] Viewer nativo com **PDFKit** (bytes em memória; sem gravar em Files)
- [x] Empty state e pull-to-refresh
- [x] Unit tests de badges + build/test no simulador

**Critério de pronto:** músico com distribuição `available` abre PDF no simulador/device.

### Fase 3 — Endurecimento e App Store (semana 3–4)
- [ ] ATS: só HTTPS em Release; exceção Debug documentada
- [ ] Não logar tokens / PII
- [ ] Privacy Nutrition Labels (dados de conta, sem tracking)
- [ ] Ícones, splash, suporte iPhone + iPad
- [ ] TestFlight interno → App Store Connect
- [ ] (v1.1) Certificate pinning; Face ID para reabrir a sessão

**Critério de pronto:** build TestFlight instalável pela equipe da orquestra.

---

## Arquitetura sugerida

```
mobile/ios/
├── Package.swift                 # SPM local
├── Sources/PortalMobile/
│   ├── API/PortalAPIClient.swift
│   ├── API/Models.swift
│   ├── Auth/KeychainStore.swift
│   └── Auth/SessionStore.swift
└── README.md
```

App Xcode (criar na Fase 0): target `PortalMembro` importa `PortalMobile`.

```
LoginView → SessionStore
PartiturasListView → PortalAPIClient.listPartituras()
PDFViewer → PDFKit / ticket URL
```

---

## Testes

| Camada | O quê |
|---|---|
| Unit (XCTest) | Parse de modelos, Keychain mock, refresh/retry |
| Integração | Contra `localhost:8000` (opt-in; CI com stack Docker) |
| Backend já existente | `tests/test_mobile_api.py` com `client: "ios"` |
| Manual | Simulador iOS 17+ e 1 device físico Safari/ATS |

---

## Dependências do backend

- Conta com vínculo a membro e acesso App/PWA liberado
- Evento com partituras distribuídas e janela `available`
- `HTTPS_ONLY=1` e domínio válido em produção ([DEPLOY.md](DEPLOY.md))

---

## Riscos

| Risco | Mitigação |
|---|---|
| ATS bloqueia HTTP em device | Usar HTTPS de staging cedo; localhost só simulador |
| PDF grande / memória | Stream + PDFKit; evitar carregar bytes inteiros na UI thread |
| Refresh concurrent | Mutex / actor no `SessionStore` |
| Rejeição App Store (conta demo) | Conta de revisão com partituras de exemplo |

---

## Marcos e donos

| Marco | Entrega |
|---|---|
| M1 | Pacote Swift + login no simulador |
| M2 | Lista + PDF |
| M3 | TestFlight |
| M4 | App Store (após feedback da orquestra) |
