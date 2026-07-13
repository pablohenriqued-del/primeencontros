# Arquitetura — Prime Encontros (a.k.a. Oásis Rio)

## O que é
Marketplace estilo iFood para contratação de massagistas no Rio de Janeiro. Nome interno no PRD e no docstring do backend é **"Oásis Rio"**; nome exibido para o usuário (UI, título da API, tags Open Graph) é **"Prime Encontros"**. Os dois nomes convivem no código — não é bug, é rebranding que não foi propagado 100%.

Este projeto foi gerado originalmente pela plataforma **Emergent** (emergent.sh) — evidências: `.emergent/emergent.yml`, `test_result.md` (protocolo de comunicação main-agent/testing-agent da Emergent), pacote `emergentintegrations`, variáveis `EMERGENT_LLM_KEY` / `EMERGENT_AUTH_SESSION_URL`. Isso importa porque partes do sistema (auth, storage de arquivos) dependem de infraestrutura hospedada pela Emergent, não são 100% self-contained.

## Stack

### Backend
- **Python 3 + FastAPI 0.110.1** rodando via ASGI (Uvicorn 0.25.0)
- Arquivo único: `backend/server.py` (~1750 linhas, todas as rotas, modelos e lógica de negócio)
- **PostgreSQL** via `asyncpg` (driver async puro, sem ORM) — migrado do MongoDB em 2026-07-12, ver seção "Banco de dados" abaixo e `.ai/context/CONTRACTS.md` #9-#11
- Auxiliar: `backend/promo_card.py` (gera imagem PNG promocional com Pillow)
- `backend/cleanup_for_production.py` — script utilitário de limpeza de dados de teste (histórico, era pra Mongo; hoje o equivalente é rodar `DELETE`/`TRUNCATE` direto no Postgres — o script antigo não foi portado)
- `backend/migrations/` — schema versionado em SQL puro (não usa Alembic — ver seção "Banco de dados")
- `backend/migrate_mongo_to_postgres.py` — ETL one-shot da migração 2026-07-12, mantido só como referência histórica/auditoria, não roda mais em deploys normais

### Frontend
- **React 19** com **Create React App 5** encapsulado por **CRACO** (`craco.config.js`) — não é Vite nem Next.js
- Tailwind CSS + shadcn/ui (Radix primitives) — paleta "Organic & Earthy" (stone/emerald), fontes Outfit + Manrope
- Roteamento: `react-router-dom` v7
- Dados: `axios` (cliente único em `frontend/src/lib/api.js`) + `@tanstack/react-query` / `swr`
- Mapa: `leaflet` + `react-leaflet`
- Alias `@` → `frontend/src` (configurado no craco)
- Plugin opcional `@emergentbase/visual-edits` só ativa em dev (`isDevServer`), com fallback silencioso se não instalado

## Estrutura de pastas
```
primeencontros/
├── backend/
│   ├── server.py              # entry point da API (app = FastAPI(...))
│   ├── promo_card.py           # geração de card PNG (Pillow)
│   ├── cleanup_for_production.py  # histórico — era pra Mongo, não portado
│   ├── migrate_mongo_to_postgres.py  # ETL one-shot da migração (2026-07-12), referência histórica
│   ├── migrations/
│   │   ├── 0001_initial_schema.sql  # schema Postgres completo (9 tabelas)
│   │   └── run_migrations.py        # runner mínimo (sem Alembic), idempotente
│   ├── requirements.txt
│   └── tests/                  # pytest (test_oasis_rio.py, test_media.py, test_verification.py, test_iter4.py)
├── frontend/
│   ├── src/
│   │   ├── index.js             # entry point React
│   │   ├── App.js               # rotas principais
│   │   ├── pages/
│   │   ├── components/ (+ components/ui = shadcn)
│   │   ├── context/
│   │   ├── hooks/
│   │   ├── lib/api.js           # axios client + helpers (token, brl)
│   │   └── constants/
│   ├── public/
│   ├── craco.config.js
│   ├── tailwind.config.js
│   └── package.json
├── memory/PRD.md                # histórico de decisões e features implementadas (Emergent)
├── test_result.md               # protocolo de testes da Emergent — NÃO editar o bloco de cabeçalho
├── test_reports/                # saídas de pytest (xml/json)
├── design_guidelines.json        # guia de design (cores, tipografia) usado pela Emergent
└── .emergent/emergent.yml        # metadata da plataforma Emergent (imagem de ambiente, job_id)
```

## Arquivo de entrada
- **Backend**: `backend/server.py`, variável `app` (FastAPI). Sobe com `uvicorn server:app --host 0.0.0.0 --port <porta>` a partir da pasta `backend/`. Não há `if __name__ == "__main__": uvicorn.run(...)` no arquivo — o processo é sempre iniciado externamente (supervisor, systemd, ou painel da hospedagem).
- **Frontend**: `frontend/src/index.js` → monta `App.js`. Em dev: `craco start`. Em produção: `craco build` gera estático em `frontend/build/`.

## Banco de dados
**PostgreSQL** — migrado do MongoDB em 2026-07-12 (motivo: reduzir RAM e reaproveitar o container `noxsystems_postgres-db` já rodando na VPS, em vez de manter um Mongo próprio — ver `.ai/docs/DEPLOY.md`). Acesso via **`asyncpg`** puro (pool de conexões, sem ORM/SQLAlchemy) — `pool: asyncpg.Pool` global, criado no evento `startup` do FastAPI.

- Config de conexão: uma única variável **`DATABASE_URL`** (`os.environ["DATABASE_URL"]`, obrigatória — sem ela o processo derruba no boot), formato `postgresql://usuario:senha@host:porta/banco`.
- **9 tabelas** (schema em `backend/migrations/0001_initial_schema.sql`): `users`, `user_sessions`, `massagistas`, `bookings`, `payment_transactions`, `reviews`, `whatsapp_clicks`, `profile_views`, `files`. Mesmos nomes das antigas coleções Mongo — mapeamento 1:1.
- **Chaves primárias são `TEXT`, não `UUID` nativo** — decisão deliberada pra manter o EXATO formato de antes (`m_a1b2c3d4e5`, `b_...`, etc., gerados em Python com `uuid.uuid4().hex[:N]` + prefixo por tipo). `user_sessions` e `payment_transactions` não têm PK própria — usam `session_token`/`session_id` como chave natural, igual no Mongo.
- **`gallery`, `specialties`, `languages`** são colunas `TEXT[]` (array nativo do Postgres) — `$push`/`$pull` do Mongo viraram `array_append`/`array_remove` no SQL.
- **`verification`** (objeto aninhado no Mongo) foi achatado em colunas `verification_status`, `verification_id_check`, `verification_photo_check`, `verification_address_check`, `verification_verified_at`, `verification_verified_by`, `verification_notes` — a API reconstrói o objeto aninhado na resposta (`_massagista_out()` em `server.py`), o contrato de API não mudou.
- **Migrations**: SQL puro versionado, sem Alembic (schema simples, sem ORM — Alembic adicionaria dependência sem ganho real aqui). `backend/migrations/run_migrations.py` aplica cada `.sql` pendente uma vez, registrando em `schema_migrations`. Roda automaticamente no boot do container (ver `docker-compose.yml`), é idempotente.
- Seed automático: no `startup` do FastAPI, só `seed_massagistas()` (popula 12 massagistas de exemplo se a tabela estiver vazia). A função `migrate_massagistas()` do Mongo (backfill de campos ausentes em docs antigos) **não existe mais** — não faz sentido em Postgres, já que colunas `NOT NULL DEFAULT` garantem os campos desde a criação da linha.
- Detalhes completos do design (tipos, FKs, índices, decisões) em `.ai/context/CONTRACTS.md` #9-#11.

## Fluxo principal
1. Frontend faz login via Google (Emergent Auth): recebe `session_id` na URL, envia no header `X-Session-ID` pro backend em `POST /api/auth/session`.
2. Backend troca esse `session_id` com o serviço da Emergent (`EMERGENT_AUTH_SESSION_URL`), recebe email/nome/foto/`session_token`, faz upsert em `users`, grava sessão em `user_sessions`, seta cookie httpOnly `session_token` **e** devolve o token pro frontend guardar em `localStorage` (fallback Bearer, porque o ingress da Emergent corta cookies cross-origin).
3. Cada request subsequente do frontend manda `Authorization: Bearer <token>` (ver `frontend/src/lib/api.js`) — o backend aceita cookie OU header.
4. Home lista massagistas (`GET /api/massagistas`), com filtro por bairro e ordenação "mais perto de você" (haversine).
5. Detalhe da profissional → dialog de agendamento (`POST /api/bookings`) → checkout Stripe (`POST /api/checkout/session`, via SDK oficial `stripe`) → status assíncrono (`GET /api/checkout/status/{id}`) + webhook (`POST /api/webhook/stripe`).
6. Painel admin (`/admin/*` rotas, gate por `require_admin`) faz verificação de perfis, edição de fotos/vídeos, métricas e reservas manuais.
7. Painel da profissional (`/me/*` rotas) permite autoatendimento: editar perfil, subir fotos/vídeo, ver estatísticas (`GET /me/stats`).
8. Upload de mídia (fotos/vídeo) não vai pro disco local — vai pro **Object Storage da Emergent** (`STORAGE_URL = https://integrations.emergentagent.com/objstore/...`), autenticado via `EMERGENT_LLM_KEY`. **Isso é uma dependência externa forte**: sem chave válida e sem acesso a esse domínio, upload de mídia simplesmente não funciona (ver `init_storage()` em `backend/server.py:60`).

## Autenticação de admin
- Bootstrap: o primeiro usuário que loga (`total_users == 0`) vira admin automaticamente.
- Além disso, qualquer email listado em `ADMIN_EMAILS` (env var, separado por vírgula) também vira admin no login.
- Rotas `/admin/*` são protegidas por `require_admin()` (`backend/server.py:502`).

## Pagamentos
- Stripe via **SDK oficial `stripe`** (migrado em 2026-07-12, antes usava o wrapper `emergentintegrations.payments.stripe.checkout`) — chave em `STRIPE_API_KEY`, segredo de webhook em `STRIPE_WEBHOOK_SECRET`. Ver `.ai/context/CONTRACTS.md` #9 pro detalhe da migração. Conforme o PRD, hoje está em modo teste (`sk_test_...`).

## Dependências restantes da Emergent (não migradas)
- **Object Storage** (upload de fotos/vídeo) — ainda chama `integrations.emergentagent.com`, autenticado via `EMERGENT_LLM_KEY`. Decisão consciente de manter por enquanto (ver CONTRACTS.md #10).
- **Auth (`EMERGENT_AUTH_SESSION_URL`)** — login Google ainda troca `session_id` com o proxy OAuth da Emergent. Não foi tocado nesta migração.
- O pacote `emergentintegrations` (Python) **foi removido** do backend — não é mais dependência de código, só a infraestrutura de storage/auth acima continua externa.
