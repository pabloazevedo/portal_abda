<div align="center">

# 🎼 Orchestra Portal — Sistema de Gestão para Orquestra & Coral

### *Plataforma multilíngue para gestão integrada de músicos, patrimônio e acervo musical*

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/Status-Beta-orange?style=for-the-badge)]()

</div>

---

## 📖 Sobre o Projeto

O **Orchestra Portal** é um sistema web desenvolvido para suprir a necessidade real de gestão administrativa e operacional de uma orquestra e coral de médio/grande porte. Reúne em uma única plataforma o cadastro de membros (com múltiplos papéis), o controle patrimonial dos instrumentos e o acervo digital de partituras.

### 🎯 Problema que resolve

Orquestras e corais frequentemente operam com planilhas dispersas, informações desencontradas entre maestro/secretaria/arquivista e dificuldade em rastrear instrumentos emprestados ou partituras em circulação. O Orchestra Portal centraliza esse fluxo:

- Um **único cadastro** de pessoa, com possibilidade de exercer múltiplos papéis (músico, maestro, chefe de naipe, arquivista, arranjador, coralista, compositor).
- **Rastreamento patrimonial** de cada instrumento, móvel e equipamento, incluindo histórico de empréstimos com identificação via **QR Code**.
- **Acervo musical** vinculado a obras e arranjos, com integração planejada para repositórios em nuvem (OneDrive/Google Drive).
- **Suporte multilíngue nativo** (PT-BR, EN, ES) com troca em tempo real.

---

## ✨ Funcionalidades Principais

### 👥 Gestão de Pessoas
- 🎭 **Cadastro Multimembro:** um membro pode acumular vários papéis simultaneamente — Músico, Maestro (com ordem hierárquica: 1º, 2º, 3º), Chefe de Naipe, Arquivista, Arranjador, Coralista (SATB) e Compositor.
- 🎻 **Múltiplos instrumentos por membro** com relação N:N e categoria.
- 🎤 **Tipos de voz** automaticamente exigidos para coralistas (Soprano, Alto, Tenor, Baixo).
- 📅 **Aniversariantes do mês** com exportação em CSV.
- 🌐 **Internacionalização** completa do formulário (PT/EN/ES).

### 📦 Patrimônio com QR Code
- 🏷️ **Rastreamento patrimonial** com identificador interno único e UUID público.
- 📱 **Endpoint QR Code** (`/patrimonio/qr/{identificador}`) para etiquetagem física dos instrumentos.
- 🔄 **Empréstimos e devoluções** vinculando item ↔ músico, com histórico imutável.
- 📊 **Status operacional**: Disponível, Emprestado, Em Manutenção, Baixa.
- 💰 **Valor de mercado** e ano de compra para fins contábeis e de seguro.

### 🎼 Acervo Musical
- 📄 **Obras e arranjos** com grade (maestro) e partes por instrumento.
- 🔗 **Distribuição por link** aos músicos no dia do evento cadastrado.
- 🔍 **Busca** no acervo e busca global por membros / patrimônio.

### ⚡ Performance & Segurança
- 🚀 **Cache Redis** para sessões e dados de leitura intensiva.
- 🔐 **Autenticação com bcrypt** + sessões assinadas (`itsdangerous`).
- 🛡️ **Rate limiting** com SlowAPI nas rotas críticas (login, recuperação de senha).
- 🔑 **Recuperação de senha** com token de uso único e expiração.
- 🖼️ **Validação de upload** por *magic bytes* (não confia em extensão).
- 🌍 **HTTPS-only** opcional via variável de ambiente.

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia | Versão | Função |
|---|---|---|---|
| **Linguagem** | Python | 3.12 | Backend principal |
| **Framework Web** | FastAPI | 0.115.5 | API + rotas server-rendered |
| **ASGI Server** | Uvicorn | 0.32.1 | Runtime HTTP/ASGI |
| **ORM** | SQLAlchemy | 2.0.36 | Mapeamento objeto-relacional |
| **Banco de Dados** | PostgreSQL | 15-alpine | Persistência principal |
| **Driver DB** | psycopg2-binary | 2.9.10 | Conector PostgreSQL |
| **Cache** | Redis | 7-alpine | Sessões + cache de leitura |
| **Templates** | Jinja2 | 3.1.4 | Renderização server-side |
| **Auth** | bcrypt + itsdangerous | 4.2.1 / 2.2.0 | Hashing + assinatura de sessão |
| **Rate Limiting** | SlowAPI | 0.1.9 | Proteção anti-abuso |
| **Crypto** | cryptography | 43.0.3 | Tokens e operações simétricas |
| **Imagens** | Pillow | 11.0.0 | Processamento de fotos |
| **Exportação** | openpyxl | 3.1.5 | Geração de planilhas |
| **Containerização** | Docker + Compose | — | Ambiente reprodutível |

---

## 🚀 Como Começar (Getting Started)

### 📋 Pré-requisitos

| Ferramenta | Versão Mínima | Verificação |
|---|---|---|
| **Docker Engine** | 24.0+ | `docker --version` |
| **Docker Compose** | v2.20+ | `docker compose version` |
| **Git** | 2.40+ | `git --version` |

> 💡 Não é necessário instalar Python, PostgreSQL ou Redis localmente — todo o stack roda em containers.

### 📥 Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/<seu-usuario>/orchestra-portal.git
cd orchestra-portal

# 2. Crie o arquivo de variáveis de ambiente
cp .env.example .env

# 3. Edite o .env com seus valores (veja seção abaixo)
```

### ⚙️ Configuração do `.env`

```dotenv
# ──────────────────────────────────────────────
# Segurança (OBRIGATÓRIO em produção)
# ──────────────────────────────────────────────
SECRET_KEY=gere-uma-chave-aleatoria-de-32-caracteres
HTTPS_ONLY=0                    # 1 em produção atrás de TLS

# ──────────────────────────────────────────────
# Banco de Dados (já consumido pelo docker-compose)
# ──────────────────────────────────────────────
DATABASE_URL=postgresql://orchestra_user:orchestra_pass@db:5432/orchestra_db

# ──────────────────────────────────────────────
# Cache / Sessões
# ──────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ──────────────────────────────────────────────
# SMTP (opcional — recuperação de senha por email)
# ──────────────────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=portal@suaorquestra.org
SMTP_PASSWORD=app-password-aqui
SMTP_FROM=Orchestra Portal <portal@suaorquestra.org>
```

> ⚠️ **Gere uma `SECRET_KEY` segura:**
> ```bash
> python -c "import secrets; print(secrets.token_urlsafe(32))"
> ```

| Variável | Obrigatória | Descrição |
|---|---|---|
| `SECRET_KEY` | ✅ | Chave de assinatura de sessões e tokens. Mín. 32 caracteres. |
| `HTTPS_ONLY` | ❌ | `1` força cookies *secure*; use atrás de TLS reverso. |
| `DATABASE_URL` | ✅ | Connection string PostgreSQL. |
| `REDIS_URL` | ✅ | Connection string Redis. |
| `SMTP_*` | ❌ | Necessárias para reset de senha via e-mail. |

### ▶️ Execução

```bash
# Subir o stack completo (DB + Redis + App)
docker compose up -d

# Acompanhar logs em tempo real
docker compose logs -f app

# Parar o ambiente
docker compose down

# Reset completo (⚠️ apaga dados)
docker compose down -v
```

A aplicação ficará disponível em **http://localhost:8000**.

> 🌱 Na primeira execução, o sistema cria automaticamente as tabelas e popula a tabela `instrumentos_base` com o seed padrão (cordas, sopros, percussão, vozes).

---

## 📚 Documentação da API

O FastAPI gera **automaticamente** documentação interativa a partir das anotações de tipo:

| Interface | URL | Uso |
|---|---|---|
| **Swagger UI** | `http://localhost:8000/docs` | Exploração interativa, executar requests |
| **ReDoc** | `http://localhost:8000/redoc` | Leitura humana, navegação por seções |
| **OpenAPI JSON** | `http://localhost:8000/openapi.json` | Importação em Postman, geração de clients |

> 📖 Endpoints HTML server-rendered (formulários, listagens) não aparecem no Swagger — apenas as rotas JSON/API. Para o fluxo completo, abra a aplicação no navegador.

---

## 📂 Estrutura de Pastas

```
orchestra-portal/
├── 📁 app/                      # Núcleo da aplicação
│   ├── __init__.py
│   ├── main.py                  # Bootstrap FastAPI + middlewares
│   ├── database.py              # Engine SQLAlchemy + sessão
│   ├── models.py                # Modelos ORM (Musician, Patrimonio, ...)
│   ├── dependencies.py          # Auth, contexto de template, i18n
│   ├── limiter.py               # Configuração SlowAPI
│   ├── email_utils.py           # Envio SMTP (reset de senha)
│   ├── utils.py                 # Helpers (magic bytes, etc.)
│   ├── labels.py                # Labels traduzíveis de enums
│   ├── seeds.py                 # Seed de instrumentos
│   ├── 📁 i18n/                 # Traduções PT/EN/ES (JSON)
│   └── 📁 routers/              # Rotas modulares
│       ├── auth.py              # Login, logout, reset de senha
│       ├── musicians.py         # CRUD de membros
│       ├── instrumentos.py      # Catálogo de instrumentos
│       ├── patrimonio.py        # Inventário + QR Code
│       ├── users.py             # Usuários do sistema
│       ├── settings.py          # Config institucional + exports
│       └── search.py            # Busca global
│
├── 📁 templates/                # Jinja2 templates HTML
├── 📁 static/                   # CSS, JS, imagens
├── 📁 uploads/                  # Fotos de membros (volume Docker)
├── 📁 migrations/               # Scripts SQL de migração
├── 📁 tests/                    # Testes automatizados
│
├── 🐳 Dockerfile                # Imagem da aplicação
├── 🐳 docker-compose.yml        # Stack local / primeiros deploys
├── 📄 requirements.txt          # Dependências de produção
├── 📄 requirements-dev.txt      # Dependências de teste/lint
├── 📄 DOCS.md                   # Status, backlog e notas do projeto
├── 📄 DEPLOY.md                 # Deploy simples (Docker Compose / VPS)
└── 📄 README.md                 # Este arquivo
```

---

## 🔒 Segurança

A segurança da informação é tratada como requisito de primeira classe neste projeto.

### Controles implementados

- 🔐 **Hashing de senhas** com bcrypt (custo 12).
- 🍪 **Cookies de sessão assinados** via `itsdangerous`.
- 🛡️ **Rate limiting** em endpoints sensíveis (`/login`, `/forgot-password`, `/reset-password`).
- 🔑 **Tokens de reset de senha** de uso único, com expiração e *hash* armazenado (não o token em texto claro).
- 🖼️ **Validação de uploads** por *magic bytes* + tamanho máximo + extensão permitida.
- 🚫 **Proteção CSRF** via `SessionMiddleware` + verificação de origem.
- 🌐 **HTTPS-only** opcional, recomendado em produção.

### 📣 Reportando vulnerabilidades

Se você descobrir uma vulnerabilidade de segurança, **NÃO abra uma Issue pública**.

> 🛡️ **Política de Disclosure Responsável**
>
> 1. Envie um e-mail para **`security@example.com`** (ou substitua pelo canal oficial).
> 2. Inclua: descrição do problema, passos para reprodução, impacto estimado.
> 3. Aguarde acuse de recebimento em até **48h**.
> 4. Daremos crédito público (com seu consentimento) na seção *Hall of Fame*.

Vulnerabilidades elegíveis incluem (mas não se limitam a): SQL injection, XSS, CSRF, escalação de privilégio, IDOR, falhas de autenticação, exposição de dados sensíveis.

> 📄 Checklist de segurança e backlog: `DOCS.md`. Deploy: `DEPLOY.md`.

---

## 🤝 Contribuição

Contribuições são bem-vindas! Toda ajuda — código, documentação, traduções, design — é valiosa.

### Workflow

```bash
# 1. Fork o projeto
# 2. Crie sua branch a partir de main
git checkout -b feat/minha-feature

# 3. Faça commits atômicos com mensagens claras
git commit -m "feat(patrimonio): adiciona filtro por categoria"

# 4. Push para seu fork
git push origin feat/minha-feature

# 5. Abra um Pull Request descrevendo o que mudou e por quê
```

### Padrões

- 🐍 **PEP 8** + type hints obrigatórios em código novo.
- 🧪 **Testes** para qualquer regra de negócio alterada (`pytest`).
- 📝 **Commits em formato Conventional Commits** (`feat:`, `fix:`, `docs:`, `refactor:`...).
- 🌐 **Strings traduzíveis** devem ser registradas nos três idiomas (`app/i18n/`).
- 🔍 Antes do PR, rode localmente:
   ```bash
   docker compose exec app pytest
   docker compose exec app python -m py_compile $(git ls-files '*.py')
   ```

### Áreas que precisam de ajuda

- 🎼 Ensaios / presença e afastamentos (ver `DOCS.md`).
- 🔧 Ordens de manutenção de instrumentos.
- ☁️ Consolidar S3 em produção (sair do filesystem do container).
- 📅 Integração com Google Calendar além do feed iCal.
- 📱 Versão **mobile-first** dos formulários.
- 🌍 Revisão de traduções EN/ES por falantes nativos.

---

## 📜 Licença

Distribuído sob a **Licença MIT**. Veja `LICENSE` para mais informações.

```
MIT License

Copyright (c) 2026 Orchestra Portal

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
...
```

---

## 🙏 Agradecimentos

- À **Orquestra e Coral** pelo apoio institucional e validação contínua.
- À comunidade **FastAPI** pela excelente documentação.
- A todos os músicos, maestros e arquivistas que doaram tempo descrevendo seus fluxos reais.

---

<div align="center">

### 🎵 *"A música expressa o que não pode ser dito e sobre o que é impossível permanecer em silêncio."* — Victor Hugo

**Feito com ❤️ para quem faz música acontecer.**

[⬆ Voltar ao topo](#-orchestra-portal--sistema-de-gestão-para-orquestra--coral)

</div>
