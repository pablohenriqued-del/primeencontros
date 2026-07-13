# Estado atual do projeto

Última análise: 2026-07-12 (atualizado após migração do banco de MongoDB pra PostgreSQL).

## O que já existe e funciona (segundo PRD + código)
- Home com busca, filtro por bairro e ordenação "mais perto de você" (haversine)
- Listagem e detalhe de massagistas (galeria, vídeo, preços 60/90/120 min)
- Fluxo de agendamento completo → checkout Stripe (modo teste) → status assíncrono + webhook
- "Minhas reservas" com status pending_payment/confirmed/cancelled
- Login Google via Emergent Auth (cookie + Bearer fallback)
- Painel admin: verificação de perfis, edição, métricas, reservas manuais
- Avaliações pós-agendamento
- Clique de WhatsApp + métricas
- Upload de fotos/vídeo via Object Storage da Emergent
- Mapa Leaflet com geolocalização
- Lightbox de fotos com deep-link (`?foto=N`) e compartilhamento (Web Share API)
- Thumbnail de vídeo gerado no client (canvas)
- Painel de desempenho da profissional (`/sou-profissional`)
- Tracking de visitas ao perfil (ignora self-view e bots)
- Open Graph dinâmico por massagista + card promocional PNG auto-gerado
- Páginas legais `/termos` e `/privacidade` — **com placeholders `[colchetes]` ainda não preenchidos** (contato/razão social)
- Limpeza pré-produção já rodada: banco reduzido a 1 profissional de teste ("Lara", Ipanema)

## Resolvido em 2026-07-12 (migração pra VPS Docker compartilhada)
- ✅ `emergentintegrations` (Stripe) substituído pelo SDK oficial `stripe>=15.3.0` — ver CONTRACTS.md #9. `pip install` agora funciona fora do ambiente Emergent.
- ✅ Bug real corrigido: `Pillow` faltava no `requirements.txt` (usado por `promo_card.py`, só funcionava por acaso na imagem-base da Emergent) — sem essa correção o backend não subiria em nenhum container limpo.
- ✅ Requirements.txt limpo: removidos `pandas`, `numpy`, `boto3`, `cryptography`, `python-jose`, `pyjwt`, `bcrypt`, `passlib`, `requests-oauthlib`, `email-validator`, `jq`, `typer` — confirmado via grep que nada no backend importa esses pacotes (auth deste app é token opaco, não JWT).
- ✅ `Dockerfile` de backend e frontend (multi-stage) + `docker-compose.yml` + `.env.example` criados e testados localmente (`docker build`, `docker compose config`, smoke test do nginx).
- ✅ Deploy documentado em `.ai/docs/DEPLOY.md` pra VPS Docker (Portainer), com limites de memória, config do Nginx Proxy Manager e comando de swap.

## Resolvido em 2026-07-12 (migração MongoDB → PostgreSQL)
- ✅ Inventário completo do uso do Mongo (9 coleções, ~130 queries, 3 aggregation pipelines) — confirmado que **nenhum ObjectId** é exposto em lugar nenhum (backend nem frontend), migração de ID foi trivial.
- ✅ Design relacional aprovado (9 tabelas, PK em `TEXT` mantendo o formato exato de antes, FK circular `bookings`↔`payment_transactions` resolvida via `ALTER TABLE`, soft-delete em `massagistas`) — ver `.ai/context/CONTRACTS.md` #11.
- ✅ `backend/server.py` reescrito de `motor` (Mongo) pra `asyncpg` (Postgres) — todas as ~130 queries, incluindo as 3 aggregation pipelines (viraram `GROUP BY`) e a busca textual em array (`specialties`, via `unnest`+`ILIKE`).
- ✅ Migrations SQL versionadas (`backend/migrations/0001_initial_schema.sql` + `run_migrations.py`, sem Alembic) — testadas contra Postgres local, incluindo a FK circular.
- ✅ ETL de dados (`backend/migrate_mongo_to_postgres.py`) — testado com dados simulando o drift real encontrado no inventário (o doc "Lara" do `cleanup_for_production.py` tem campos antigos/ausentes); um bug de contagem de placeholders SQL foi pego e corrigido durante esse teste.
- ✅ Suíte de testes adaptada e **rodando de verdade** contra o backend em Postgres: 57/64 passam. Os 7 restantes (checkout + upload de mídia) falham só por falta de credenciais reais (Stripe/Emergent) neste ambiente, não por bug de migração — confirmado lendo o traceback de cada um.
- ✅ Achado durante a adaptação dos testes: `test_iter4.py` tinha sua própria fixture Mongo separada (`mongo`, não capturada no inventário original que só viu `mongo_db`) — corrigido, e dois bugs reais de teste expostos pela FK enforcement do Postgres (massagista_id fake `"m1"`, ordem de delete em `finally`) foram corrigidos.
- ✅ `docker-compose.yml`: removido o serviço `mongo-db`; backend agora conecta ao `noxsystems_postgres-db` compartilhado via rede externa, com banco/usuário próprios (não reaproveita schema do anuncifacil). Migrations rodam automaticamente no boot do container.
- ✅ `.ai/context/ARCHITECTURE.md`, `.ai/context/CONTRACTS.md`, `.ai/docs/DEPLOY.md` e `.ai/reviews/REVIEW_CHECKLIST.md` atualizados.

## Pendências identificadas na análise (não é backlog do PRD, é o que falta pra produção real)

1. **Placeholders legais não preenchidos** — `/termos` e `/privacidade` têm campos `[colchetes]` esperando razão social e contato real. Bloqueia lançamento sério (LGPD).
2. **Naming inconsistente**: "Oásis Rio" (interno/PRD/docstring) vs "Prime Encontros" (UI/API/OG tags). Decidir um nome definitivo e propagar, ou documentar formalmente que é intencional.
3. **Stripe em modo teste** (`sk_test_...`, segundo o PRD) — precisa trocar pra chave live antes de aceitar pagamento real. **Novo requisito pós-migração**: `STRIPE_WEBHOOK_SECRET` precisa ser gerado no dashboard do Stripe pro endpoint `/api/webhook/stripe` — não existia com o wrapper antigo.
4. **Object Storage ainda depende da Emergent** (`EMERGENT_LLM_KEY`, upload de fotos/vídeo) — decisão consciente de não migrar nesta leva (ver CONTRACTS.md #10). A VPS precisa manter egress HTTPS liberado pra `integrations.emergentagent.com` e `demobackend.emergentagent.com` (auth), mesmo rodando fora da infra da Emergent.
5. **Sem `yarn.lock` commitado** no frontend — build funciona (testado), mas não é reprodutível entre builds. Gerar e commitar antes do próximo deploy de verdade.
6. **Placeholders pendentes no `docker-compose.yml`**: `NOME_DA_REDE_DO_NPM` e `NOME_DA_REDE_DO_POSTGRES` precisam ser trocados pelos nomes reais das redes Docker antes do primeiro `docker compose up` na VPS — comando pra descobrir em DEPLOY.md seção 4.3.
7. **Banco/usuário do Postgres ainda não criados na VPS**: `CREATE USER`/`CREATE DATABASE` dedicados dentro do `noxsystems_postgres-db` precisam rodar uma vez antes do primeiro deploy — comando em DEPLOY.md seção 4.1. Sem isso o backend não sobe (`DATABASE_URL` aponta pra um banco que não existe ainda).
8. **Se já existir dado real no MongoDB antigo** (fora do seed de teste): rodar `backend/migrate_mongo_to_postgres.py` uma vez antes de desligar o Mongo de vez — ver DEPLOY.md seção 4.2. Não confirmei se há dado de produção real acumulado lá ou só o seed de teste ("Lara") — checar antes de assumir que não precisa rodar.
9. **Checkout e upload de mídia não testados ponta-a-ponta**: migrados/revisados no código, mas sem credenciais reais (Stripe `sk_test_...`, `EMERGENT_LLM_KEY`) neste ambiente pra validar de verdade. Confirmar manualmente na VPS com as chaves reais antes de considerar essas duas funcionalidades 100% prontas.
10. **Backlog do PRD ainda não implementado** (do `memory/PRD.md`):
    - P1: Painel da profissional com autocadastro completo (hoje o autocadastro existe parcialmente via `/me/profile`, mas o PRD trata como pendência maior — confirmar escopo real antes de assumir "pronto")
    - P2: Chat in-app cliente ↔ profissional
    - P2: Notificações por e-mail (Resend)
    - P2: Cupons de desconto / fidelidade
    - P2: Mapa real na home (Leaflet já existe no detalhe/mapa, confirmar se falta só na home)
    - P2: Suporte multi-cidade (SP, BH) — hoje hardcoded pra bairros do Rio (`BAIRROS`)
11. **Histórico de commits não é rastreável por conteúdo** — todos os commits recentes são `"Auto-generated changes"` / `"auto-commit for <uuid>"` (gerados pela Emergent). Se for continuar em git normal, considerar mensagens de commit descritivas daqui pra frente (ver convenção em `AGENT_INSTRUCTIONS.md`).

## Como continuar uma sessão futura
1. Ler `.ai/context/ARCHITECTURE.md` pra entender stack e fluxo.
2. Ler `.ai/context/CONTRACTS.md` antes de mexer em rotas, schema ou auth.
3. Ler `.ai/context/AGENT_INSTRUCTIONS.md` pras regras de trabalho e convenção de commit.
4. Consultar `memory/PRD.md` pra decisões de produto já tomadas (não redecidir o que já foi decidido).
5. Antes de subir qualquer coisa, rodar o checklist em `.ai/reviews/REVIEW_CHECKLIST.md`.
6. Atualizar este arquivo (`EXECUTION_ORDER.md`) no final da sessão com o que mudou.
