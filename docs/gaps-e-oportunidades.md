# Gaps e oportunidades

Documento vivo das lacunas conhecidas e das oportunidades de evolução.  
Atualizado: 2026-11-03. Fonte complementar: [DOCS.md](DOCS.md), [MOBILE_API.md](MOBILE_API.md), [PWA.md](PWA.md).

---

## 1. Produto (funcional)

| Gap | Impacto | Oportunidade |
|---|---|---|
| Ensaios e presença | Regência sem métrica operacional | Modelo `Attendance`, lista de presença por ensaio, exportação |
| Licenças / afastamentos | Quórum e convocação manuais | Fluxo de afastamento com impacto em convocação |
| Ordens de manutenção | Status `Manutencao` sem workflow | OS com histórico, prazo e responsável |
| Reserva de salas | Fora do portal | Calendário de salas integrado à programação |
| Self-service do músico | Músico depende da secretaria | Área do membro: ensaios, partituras, empréstimos |
| Matching de instrumentos | Partes vs catálogo inconsistente | Unificar `instrumentos_base` com nomes das partes |
| Convocação por e-mail no evento | Só distribuição de partituras | E-mail de convocação além do link de partitura |
| OCR / tags no acervo | Busca limitada a metadados | Indexação de conteúdo e tags automáticas |
| Integração OneDrive / Google Drive | Uploads locais ou S3 parcial | Sync com repositórios já usados pela orquestra |
| Dashboard do maestro | Visão fragmentada | Painel de presença, naipe e programa |
| RFID no patrimônio | Só QR / barcode | Etiquetas RFID para inventário físico rápido |

---

## 2. Mobile e iOS

Planos: [plano-trabalho-ios.md](plano-trabalho-ios.md) · [plano-trabalho-android.md](plano-trabalho-android.md) · código [`mobile/`](../mobile/).

| Gap | Impacto | Oportunidade |
|---|---|---|
| App iOS (UI / Xcode / App Store) incompleto | Library SPM + Keychain prontos; falta app | Seguir plano iOS Fase 0–3 |
| App Android (UI / Gradle / Play) incompleto | Library Kotlin pronta; falta AAB | Seguir plano Android Fase 0–3 |
| Certificate pinning | Só recomendação na doc | Pinning no cliente nativo em produção (v1.1 dos planos) |
| Keychain / Keystore na UI app | Library cobre; app ainda não amarra | Ligar SessionStore / SecureTokenStore nas telas |
| ATS / Network Security | Só orientação | Perfis de produção só HTTPS |
| Testes em device / simulador | Cobertura só no backend (pytest) | UI tests (XCTest / Espresso) e smoke em CI |
| Download PDF `available` / `expired` | Fluxo documentado, teste parcial | Casos de integração Bearer + janela de validade |
| Logout / forgot-reset na API mobile | Endpoints existem, pouco teste | Ampliar `tests/test_mobile_api.py` |
| PWA no iOS | Instalação via Safari (sem `beforeinstallprompt`) | Melhorar onboarding A2HS e offline seguro |
| Formulários mobile-first (portal web) | UX pobre no celular para admin | Layout responsivo dos formulários Jinja/SPA |

---

## 3. Infraestrutura e dados

| Gap | Impacto | Oportunidade |
|---|---|---|
| S3 parcial em produção | Uploads no volume do container | S3 obrigatório + lifecycle + backup |
| Migrations manuais + `create_all()` | Risco em upgrades | Alembic (ou runner formal) na esteira |
| DB e Redis no mesmo host (MVP) | Menos resiliência | Postgres/Redis gerenciados + backups agendados |
| Validação avançada de partitura | Código stub (OCR/fuzzy) | Pipeline de validação com score e quarentena |
| Observabilidade | Logs básicos | Métricas, tracing e alertas (health além de `/healthz`) |

---

## 4. Segurança e qualidade

| Gap | Impacto | Oportunidade |
|---|---|---|
| CSRF / CSP / cabeçalhos hardenizados | ZAP ainda aponta avisos | Tokens CSRF nos forms, CSP, `X-Frame-Options`, `nosniff` |
| IDOR horizontal em objetos | Testes cobrem mais RBAC de papel | Testes de acesso a recurso de outro usuário |
| Rate limit só em rotas críticas | Outras superfícies abertas | Limites em busca e scan públicos |
| Scan DAST sem autenticação | ZAP só vê login | Perfil autenticado no ZAP / smoke autenticado |
| CVEs de imagem Debian sem patch | Trivy reporta OS unfixed | Rebuild periódico da base / distroless quando viável |
| A11y e regressão | Playwright presente, cobertura limitada | Expandir fluxos críticos (login, patrimônio, acervo) |

---

## 5. Priorização sugerida

1. **Alta** — Ensaios/presença; storage S3 em produção; migrations formais; harden de cabeçalhos/CSRF.
2. **Média** — Self-service do músico; ampliar testes da API mobile; S3 + backup; mobile-first nos forms admin.
3. **Baixa / oportunística** — App nativo iOS/Android; OCR; RFID; OneDrive/Graph; dashboard do maestro.

Detalhe de backlog operacional: [DOCS.md](DOCS.md). Contrato mobile: [MOBILE_API.md](MOBILE_API.md).
