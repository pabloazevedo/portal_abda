# Integração mobile (Android / iOS) — Orchestra Portal

Base URL (dev): `http://localhost:8000`  
Docs interativas: `/api/docs` · OpenAPI: `/api/openapi.json`

## Autenticação (padrão mercado)

1. `POST /api/v1/auth/login` com JSON `{ "username", "password", "client": "android"|"ios" }`
2. Guardar `access_token` (memória) e `refresh_token` no **Keystore (Android)** / **Keychain (iOS)**
3. Em cada request: `Authorization: Bearer <access_token>`
4. Em `401`: `POST /api/v1/auth/refresh` com `{ "refresh_token" }` (rotação — use o novo refresh)
5. Logout: `POST /api/v1/auth/logout` com o refresh atual
6. **HTTPS obrigatório em produção** (`HTTPS_ONLY=1`)

Access ~30 min · Refresh ~30 dias (env: `API_ACCESS_TOKEN_MINUTES`, `API_REFRESH_TOKEN_DAYS`).

## Partituras

1. Conta do usuário deve ter **vínculo com membro** (admin: Usuários → Vínculo com membro)
2. `GET /api/v1/me/partituras` → lista com `status`: `available` | `not_yet_available` | `expired`
3. PDF: `GET /api/v1/me/partituras/{acesso_id}/documentos/{documento_id}/pdf`  
   (só quando `status=available`; mesma janela do link por e-mail)

## Segurança / App Store & Play

- Não embutir `SECRET_KEY` no app
- Certificate pinning opcional (recomendado em prod)
- Não logar tokens
- PDF: `Cache-Control: private, no-store` — preferir abrir em viewer in-app (PdfRenderer / PDFKit)
- ATS (iOS) / Network Security Config (Android): apenas HTTPS em prod

## Site mobile (PWA)

Ver [PWA.md](PWA.md). Gaps: [gaps-e-oportunidades.md](gaps-e-oportunidades.md). Planos: [iOS](plano-trabalho-ios.md) · [Android](plano-trabalho-android.md). Código: [`mobile/`](../mobile/). Admin: Configurações → Sistema → ligar/desligar. URL: `/m/`.

## O que NÃO mudou

- Login web por cookie
- Links públicos `/acervo/programacao/acesso/{token}` (e-mail)
- Downloads de logo/fotos em `/uploads/` (exceto `uploads/obras/` bloqueado sem sessão)

