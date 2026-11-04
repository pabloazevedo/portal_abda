# Orchestra Portal — Documentação do Projeto

Documento vivo de status, backlog e notas operacionais.  
Para setup local e visão geral do produto, use o [README.md](../README.md).  
Para primeiros deploys (Docker Compose / VPS), use o [DEPLOY.md](DEPLOY.md).  
Gaps e oportunidades: [gaps-e-oportunidades.md](gaps-e-oportunidades.md).

**Atualizado:** 2026-11-03

---

## 1. Status atual (resumo)

| Área | Situação |
|---|---|
| Pessoas (multi-papéis, instrumentos, organograma) | Maduro |
| Patrimônio + QR / etiquetas + empréstimo | Maduro |
| Auth, RBAC, reset de senha, i18n PT/EN/ES | Maduro |
| Acervo: Obra + Arranjo + grade + partes | Implementado |
| Programação: eventos, programa, iCal | Implementado |
| Distribuição de partituras por link (dia do evento) | Implementado |
| Ensaios / presença / afastamentos | Pendente |
| Manutenção de instrumentos (OS) | Pendente |
| Reserva de salas | Pendente |
| S3 obrigatório em produção (uploads ainda locais) | Parcial |
| Validação avançada de partitura (OCR/fuzzy) | Não entregue (código stub) |

---

## 2. Backlog priorizado

### Alta prioridade

1. **Ensaio + Presença (`Attendance`)** — métrica operacional nº 1 da regência.
2. **Licenças / afastamentos** — quórum e convocação.
3. **Ordens de manutenção** — status `Manutencao` existe, sem workflow.
4. **Storage de arquivos em produção** — volume Docker para MVP; S3 quando escalar.
5. **Pipeline de migrations** — hoje: SQL manual + `create_all()`; formalizar (Alembic ou runner).

### Média prioridade

- Posição de naipe / estante (spalla vs tutti) com histórico.
- Convocação por evento (e-mail) além da distribuição de partituras.
- Página self-service do músico (ensaios, partituras, empréstimos).
- Consolidar matching instrumento (`instrumentos_base` vs nomes das partes).

### Ideias (baixo / futuro)

- OCR/tags no acervo, dashboard do maestro, RFID no patrimônio, OneDrive/Graph.

---

## 3. Segurança (checklist operacional)

Controles já presentes: bcrypt, sessões assinadas, rate limit no login, tokens de reset one-time, validação básica de upload, RBAC por rota, `HTTPS_ONLY`.

Antes de produção:

- [ ] `SECRET_KEY` forte (≥ 32 chars), nunca o default
- [ ] `ADMIN_PASSWORD` definido; trocar senha do admin no 1º login
- [ ] Credenciais DB/Redis só via secrets / `.env` (não commitadas)
- [ ] Cookies `HTTPS_ONLY=1` atrás de TLS
- [ ] Bucket S3 privado; sem ACL pública
- [ ] Backup RDS habilitado

Reportar vulnerabilidades por canal privado (não abrir issue pública). Detalhes de contactos: ver README.

---

## 4. Testes

| Suíte | Caminho | Foco |
|---|---|---|
| A11y / regressão | `tests/` | Playwright + axe; regressão Fase 1 |
| Auditoria | `tests_audit/` | Unit, integração Redis, IDOR, QR |
| Esteira de segurança | `scripts/security/pipeline.sh` | Gitleaks, Bandit, Semgrep, pip-audit, npm audit, Hadolint, Trivy, OWASP ZAP |

A esteira roda em containers. No GitHub Actions (`.github/workflows/security.yml`) cada scanner é um job, em push, pull request e disparo manual. Localmente o hook `.githooks/pre-commit` chama a esteira inteira a cada commit. Ative uma vez, sem alterar `git config`:

```bash
cp .githooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit scripts/security/pipeline.sh
```

Uma etapa só: `bash scripts/security/pipeline.sh gitleaks` (ou `bandit`, `semgrep`, `pip-audit`, `npm-audit`, `hadolint`, `trivy-fs`, `image`, `dast`).

```bash
docker compose exec app pytest tests/ -q
docker compose exec app pytest tests_audit/ -q   # deps extras podem ser necessárias
```

---

## 5. Histórico de documentação

Diversos relatórios pontuais foram consolidados neste arquivo, em [DEPLOY.md](DEPLOY.md) e em [gaps-e-oportunidades.md](gaps-e-oportunidades.md). A fonte da verdade técnica é o código em `app/` e o `docker-compose.yml`.
