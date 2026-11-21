# Plano de trabalho — App Android (Portal do Membro)

**Objetivo:** app nativo Android (Kotlin / Jetpack Compose) para músicos e coralistas consumirem a API em `/api/v1`, com refresh no Keystore/EncryptedSharedPreferences, PdfRenderer e publicação na Play Store.  
**Contrato:** [MOBILE_API.md](MOBILE_API.md) · Gaps: [gaps-e-oportunidades.md](gaps-e-oportunidades.md)  
**Código inicial:** [`mobile/android/`](../mobile/android/)

---

## Escopo MVP (v1)

| Inclui | Não inclui (v1) |
|---|---|
| Login / logout / refresh com rotação | Gestão admin |
| Lista de partituras por evento + status | FCM / push |
| Abertura de PDF (PdfRenderer ou Custom Tabs no ticket) | Offline completo |
| Perfil (`GET /api/v1/auth/me`) | Biometria obrigatória (v1.1) |
| HTTPS + Network Security Config | Certificate pinning (v1.1) |

---

## Fases

### Fase 0 — Fundação (semana 1)
- [x] Plano documentado e pasta `mobile/android/`
- [x] Cliente HTTP Kotlin alinhado à API (`PortalApiClient`)
- [x] Persistência segura do refresh (`SecureTokenStore`)
- [x] Projeto Gradle (app + `:portal-api` library) em `mobile/android/`
- [x] Flavors: `dev` (cleartext LAN), `staging`, `prod` (HTTPS only)
- [x] Scripts de setup no Ubuntu de build/emulador (`scripts/android/`) — host `192.168.50.32` (`ub2404202405`)
- [x] Validar `assembleDevDebug` + emulador no Ubuntu (`Portal_API35`, APK instalado, `MainActivity` em foreground)

**Critério de pronto:** `assembleDevDebug` abre tela de login no emulador Ubuntu. ✅

### Fase 1 — Autenticação (semana 1–2)
- [ ] `POST /api/v1/auth/login` com `client: "android"`
- [ ] Access token em memória (`StateFlow`); refresh em EncryptedSharedPreferences / Keystore
- [ ] OkHttp Authenticator: em `401`, refresh + retry único
- [ ] Logout: `POST /api/v1/auth/logout` + limpar store
- [ ] Tela quando `has_musician_link == false`
- [ ] Testes JUnit do fluxo de refresh (token antigo → 401)

**Critério de pronto:** login → `/me` → logout no emulador contra Docker.

### Fase 2 — Partituras (semana 2–3)
- [ ] `GET /api/v1/me/partituras` em Compose (LazyColumn por evento)
- [ ] Chips de status: `available` | `not_yet_available` | `expired`
- [ ] Download Bearer do PDF **ou** `view-ticket` + Custom Tabs em `/m/pdf/{ticket}`
- [ ] Viewer com **PdfRenderer** (preferencial); cache em cache dir privado, apagar ao fechar
- [ ] Pull-to-refresh + empty state

**Critério de pronto:** músico de teste abre PDF no emulador/device.

### Fase 3 — Endurecimento e Play Store (semana 3–4)
- [ ] `network_security_config.xml`: cleartext só em `dev`
- [ ] ProGuard/R8 sem vazar strings de token
- [ ] Data safety form (conta, sem ads)
- [ ] Ícones adaptive, edge-to-edge, tablets
- [ ] Internal testing track → produção
- [ ] (v1.1) Certificate pinning (OkHttp `CertificatePinner`); biometria

**Critério de pronto:** AAB na faixa interna instalável pela equipe.

---

## Arquitetura

```
mobile/android/
├── settings.gradle.kts
├── app/                          # Compose (Login stub Fase 0)
├── portal-api/                   # OkHttp + serialization + sessão
│   └── src/main/java/org/orchestra/portal/
│       ├── api/PortalApiClient.kt
│       ├── api/Models.kt
│       ├── auth/SecureTokenStore.kt
│       └── auth/SessionRepository.kt
└── README.md
```

Build/emulador: Ubuntu `192.168.50.32` (`scripts/android/setup-ubuntu.sh`).

```
LoginScreen → SessionRepository          # Fase 1
PartiturasScreen → PortalApiClient…      # Fase 2
PdfScreen → PdfRenderer / Custom Tabs    # Fase 2
```

---

## Testes

| Camada | O quê |
|---|---|
| Unit (JUnit) | Models, SecureTokenStore fake, Authenticator |
| Instrumented | Emulador API 29+ contra backend local |
| Backend já existente | `tests/test_mobile_api.py` (login android + refresh) |
| Manual | Emulador + 1 device físico |

---

## Dependências do backend

- Conta com vínculo a membro e acesso App liberado
- Distribuição de partituras com status `available`
- Staging HTTPS ([DEPLOY.md](DEPLOY.md))

---

## Riscos

| Risco | Mitigação |
|---|---|
| Cleartext em prod | Flavor `prod` sem cleartext; lint CI |
| Scoped storage / PDF | Cache privado do app; não usar Downloads públicos |
| Refresh race | Mutex no `SessionRepository` |
| Play rejeição | Conta de demonstração com partituras |

---

## Marcos

| Marco | Entrega |
|---|---|
| M1 | Library Kotlin + login no emulador |
| M2 | Lista + PDF |
| M3 | Internal testing |
| M4 | Produção Play Store |
