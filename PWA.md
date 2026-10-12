# Site mobile / PWA (MVP)

Base: `/m/` · Liga/desliga: **Configurações → Sistema**

## Uso
1. Admin liga o PWA nas configurações
2. Em **Programação**, após montar o programa, use **Distribuir partituras** (criar o evento sozinho não envia partituras)
3. Músico abre `/m` no celular/tablet (HTTPS em produção)
4. Login com usuário do portal (conta com vínculo a membro)
5. Área **Novidades** avisa partituras novas ou liberadas para download
6. Opcional: “Adicionar à tela de início” (Chrome / Safari)

## Técnico
- Consome `/api/v1` (Bearer + refresh)
- Abrir partitura no celular: ticket curto → `/m/pdf/{ticket}` (viewer nativo; evita blob/iframe)
- Manifest: `/m/manifest.webmanifest`
- Service Worker: `/m/sw.js` (escopo `/m/` — não cacheia API/PDF)
- Portal web e links de e-mail **não** mudam com o toggle
