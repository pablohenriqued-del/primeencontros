# Oásis Rio — PRD

## Original problem statement
App estilo iFood para contratação de massagistas no Rio de Janeiro. Funcionalidades: local de atendimento, fotos/vídeos das profissionais, valores por hora, pagamento direto pelo site, agendamento, segregação por bairros do Rio e ordenação "mais próximo de você".

## User choices
- Pagamento: Stripe (test mode, sk_test_emergent)
- Auth: Emergent Google Auth (social login)
- Geolocalização: Geolocation API do navegador
- Mock: 12 profissionais seedadas automaticamente
- Sem painel do profissional (admin centralizado)

## Architecture (built 2026-06-13)
- Backend: FastAPI + MongoDB (motor); seed on startup; Stripe via emergentintegrations; Bearer-token auth fallback (ingress strips cross-origin cookies).
- Frontend: React + Tailwind + Shadcn UI; "Organic & Earthy" palette (stone/emerald), Outfit + Manrope fonts; mobile-first.
- Collections: users, user_sessions, massagistas, bookings, payment_transactions.

## Implemented (2026-06-13)
- Home com hero, busca, filtro por bairro, "Perto de mim" (haversine sort)
- 12 profissionais seedadas em 12 bairros do Rio
- Detail page: galeria bento, vídeo, especialidades, preços 60/90/120 min
- Booking dialog com Calendar, horários, estúdio/domicílio, endereço, observações
- Stripe Checkout (BRL) com transaction idempotente
- "Minhas reservas" com status (pending_payment/confirmed/cancelled)
- Login Google (Emergent Auth) com Bearer token persistido em localStorage
- Painel admin completo (verificação, edição, métricas, reservas manuais)
- Sistema de avaliações pós-agendamento
- WhatsApp direto + métricas de clique
- Upload de fotos/vídeos via Object Storage
- Mapa Leaflet com geolocalização
- **Lightbox de fotos** no Detail (clique amplia, prev/next, ESC/setas, contador) — 2026-06-13
- **Thumbnail real do vídeo** extraída no client (canvas/seek 1s) ao fazer upload; botão "Gerar do vídeo" para regenerar de vídeos já existentes — 2026-06-13

## Backlog
- P1: Sistema de avaliações (escrever review pós-atendimento)
- P1: Painel da profissional (autocadastro, agenda, preços)
- P2: Chat in-app cliente ↔ profissional
- P2: Notificações por e-mail (Resend)
- P2: Cupons de desconto / fidelidade
- P2: Mapa real (Leaflet/Mapbox) na home
- P2: Suporte multi-cidade (SP, BH)
