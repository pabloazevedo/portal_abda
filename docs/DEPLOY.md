# Deploy — Orchestra Portal (simples)

Guia para os primeiros deploys com **Docker Compose** em um único servidor (VPS).  
Você sobe Postgres, Redis e a app no mesmo host (ou DB gerenciado à parte, se preferir).

Status do produto: [DOCS.md](DOCS.md) · visão geral: [../README.md](../README.md) · gaps: [gaps-e-oportunidades.md](gaps-e-oportunidades.md).

---

## Arquitetura (MVP em produção)

```
Internet (HTTPS via reverse proxy, ex.: Caddy/Nginx)
        │
        ▼
   Host VPS
   ├── app      (FastAPI / Uvicorn :8000)
   ├── db       (PostgreSQL 15)
   └── redis    (Redis 7)
        +
   volume uploads/  (persistir partituras e fotos)
```

Mais adiante: DB gerenciado, S3 para arquivos, etc. Não é obrigatório no primeiro deploy.

---

## Pré-requisitos no servidor

- Docker Engine 24+ e Docker Compose v2
- Domínio apontando para o IP do VPS (recomendado)
- Reverse proxy com TLS (Caddy ou Nginx + Let's Encrypt)

```bash
docker --version
docker compose version
```

---

## Passo a passo

### 1. Código no servidor

```bash
git clone <seu-repo> orchestra-portal
cd orchestra-portal
```

### 2. Variáveis de ambiente

```bash
cp .env.example .env
# Em produção, use também .env.prod.example como checklist
```

Defina no mínimo:

| Variável | Nota |
|---|---|
| `SECRET_KEY` | Aleatória ≥ 32 chars |
| `ADMIN_PASSWORD` | Senha inicial do admin |
| `HTTPS_ONLY` | `1` atrás de TLS |
| `DATABASE_URL` | Já correta no compose (`@db:5432`) |
| `REDIS_URL` | Já correta no compose (`@redis:6379`) |
| `SMTP_*` | Opcional (reset de senha / e-mail de partituras) |

Gerar `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Não commitar** `.env` com valores reais.

### 3. Subir o stack

```bash
docker compose up -d --build
docker compose logs -f app
```

App em `http://localhost:8000` (ou via proxy).

### 4. Migrations

Em banco já existente, aplique os SQL em `migrations/` em ordem numérica:

```bash
# Exemplo (dentro da rede do compose)
docker compose exec -T db psql -U orchestra_user -d orchestra_db < migrations/001_refactor_members.sql
# ... até o último arquivo
```

Em instalação nova, o startup também roda `create_all()`; ainda assim as migrations manuais cobrem índices/constraints evolutivas — rode-as em produção controlada.

### 5. Reverse proxy (HTTPS)

Exemplo mínimo com **Caddy** (outro host ou mesmo servidor):

```caddyfile
portal.suaorquestra.org {
    reverse_proxy localhost:8000
}
```

Com Nginx: `proxy_pass http://127.0.0.1:8000;` + certificado Let's Encrypt.

Depois: `HTTPS_ONLY=1` no `.env` e `docker compose up -d`.

### 6. Pós-deploy

- [ ] Login admin e **trocar senha**
- [ ] Testar cadastro de membro e upload de partitura
- [ ] Confirmar volume `uploads_data` persistindo após restart
- [ ] Backup periódico do volume Postgres (`postgres_data`)

---

## Comandos úteis

| Ação | Comando |
|---|---|
| Logs | `docker compose logs -f app` |
| Rebuild | `docker compose up -d --build` |
| Parar | `docker compose down` |
| Backup DB | `docker compose exec -T db pg_dump -U orchestra_user orchestra_db > backup.sql` |
| Restore | `docker compose exec -T db psql -U orchestra_user orchestra_db < backup.sql` |

---

## Troubleshooting

| Sintoma | Ação |
|---|---|
| App não sobe | `docker compose logs app` — DB healthy? `SECRET_KEY` setada? |
| 502 no proxy | App escutando em `8000`? Firewall liberando só 80/443? |
| Uploads somem | Volume `uploads_data` mapeado? Não apagar com `down -v` |
| Login / sessão | `HTTPS_ONLY` coerente com HTTP vs HTTPS |
| 500 ao excluir arranjo | Remover do programa do evento antes (FK) |

---

## Checklist de segurança

- [ ] `SECRET_KEY` e `ADMIN_PASSWORD` fortes
- [ ] `.env` fora do Git
- [ ] HTTPS no proxy + `HTTPS_ONLY=1`
- [ ] Portas 5432/6379 **não** expostas publicamente
- [ ] Backup do Postgres agendado
- [ ] Atualizações de imagem / `git pull` + rebuild periódicos
