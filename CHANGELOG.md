# Changelog

Todas as mudanças notáveis deste projeto são documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

A versão publicada no portal (rodapé) vem do arquivo `VERSION` na raiz do repositório.
O mesmo número deve ser usado em tags Git (`vX.Y.Z`) quando a esteira de release estiver ativa.

## [Unreleased]

## [1.3.1] - 2026-08-10

### Adicionado
- Pré-visualização PDF da **Grade** no Detalhe da Obra (painel à direita)
- Endpoint de visualização inline `/acervo/documentos/{id}/view`

## [1.3.0] - 2026-08-10

### Adicionado
- Colunas `qr_payload` e `barcode_value` no inventário (geradas no cadastro)
- Código de barras Code128 automático por item
- Impressão formatada de QR e código de barras para impressoras de etiquetas
- Página de impressão com opções: só QR, só código de barras ou ambos

### Alterado
- QR e código de barras deixam de ser cadastrados manualmente
- Detalhe do item exibe QR e código de barras gerados pelo sistema

### Corrigido
- Scan de inventário resolve barcode/identificador além das etiquetas físicas

## [1.2.0] - 2026-08-10

### Adicionado
- Opção **Acesso ao App (PWA)** no cadastro/edição de Membros (músicos e coralistas)
- Remoção de acesso ao App na ficha do membro (somente Admin)
- Badge de App/PWA na ficha do membro

### Alterado
- Página **Usuários** passa a listar apenas usuários de sistema (admin, maestro, arquivista, secretaria)
- Acesso ao App deixa de ser configurado em Usuários; fica no fluxo de Membros
- Separação clara: Membros (artístico) × Usuários de sistema (operacional)

### Corrigido
- Evita misturar contas de músicos/coralistas com a equipe administrativa do portal

## [1.1.0] - 2026-08-10

### Adicionado
- Arquivo `VERSION` como fonte de verdade da versão da aplicação
- Página pública de histórico de versões (`/versoes`)
- Release notes persistidas no banco e gerenciamento em Configurações → Versões
- Sincronização automática da versão do código com o registro “atual” no banco

### Alterado
- Rodapé passa a exibir a versão do arquivo `VERSION`, com link para o histórico

## [1.0.0] - 2026-08-10

### Adicionado
- Portal do Membro disponível para a associação
- Gestão de membros, papéis e instrumentos
- Inventário de patrimônio com etiquetas
- Acervo musical (obras, arranjos e programação)
- Configurações institucionais e branding
