# Contratos que não podem quebrar sem revisão

Este projeto **não tem versionamento de API** (`/api`, sem `/v1`) e **não tem envelope de paginação** — todo endpoint de listagem devolve um array JSON puro, sem `{data, meta, page}`. Se algum dia isso mudar, é breaking change pra todo o frontend de uma vez (não tem fallback).

Qualquer mudança abaixo exige: avisar explicitamente o usuário que é breaking change, e esperar confirmação antes de aplicar.

## 1. Identificadores
- Toda entidade tem campo `id` (string, `uuid.uuid4().hex[:N]` + prefixo por tipo — ex: `m_...`, `b_...`, `r_...`). **Não é UUID canônico de 36 caracteres** — é um formato próprio, mantido de propósito na migração pro Postgres (PK das tabelas é `TEXT`, não `UUID` nativo — ver CONTRACTS.md #11).
- Usuário usa `user_id` (formato `user_{uuid.hex[:12]}`) em vez de `id` — inconsistência conhecida entre tabelas, não "corrigir" sem avisar (quebra tudo que já lê `user_id`).
- `user_sessions` e `payment_transactions` não têm coluna `id` própria — a chave é `session_token`/`session_id` respectivamente (igual era no Mongo).

## 2. Formato de resposta
- Listagens (`GET /api/massagistas`, `GET /api/bairros`, etc.) retornam **array JSON direto**, sem envelope.
- Detalhe (`GET /api/massagistas/{mid}`) retorna **objeto direto**, sem wrapper `{data: ...}`.
- Erros seguem o padrão do FastAPI: `HTTPException(status_code, "mensagem")` → body `{"detail": "mensagem"}`. O frontend espera esse formato (`error.response.data.detail`) — não trocar por outro shape de erro sem atualizar todos os catches do frontend.

## 3. Schema de `Massagista` (`backend/server.py:142`)
Campos obrigatórios e seus tipos — mudar nome ou tipo de qualquer um quebra o card/detalhe no frontend:
```
id: str
name: str
bairro: str
bairro_slug: str
lat, lng: float
rating: float
reviews: int
bio: str
specialties: List[str]
hourly_rate: float          # BRL
price_60, price_90, price_120: float
main_image: str
gallery: List[str]
video_url: str
video_thumb: str
experience_years: int
languages: List[str]
```
`GET /api/massagistas` também injeta um campo extra `distance_km` (float, 2 casas) quando `lat`/`lng` são passados na query — isso é calculado on-the-fly, não persistido.

## 4. Schema de `Booking` (`backend/server.py:175`)
```
id, user_id, user_email, massagista_id, massagista_name, massagista_image, bairro,
date (YYYY-MM-DD), time (HH:MM), duration (60|90|120), location_type ("studio"|"home"),
address?, notes?, amount: float, currency: "brl", status, payment_session_id?,
payment_method? ("whatsapp"|"pix"|"cash"|"manual" — só em reservas manuais do admin),
manual_confirmed_by?, manual_confirmed_at?, created_at (ISO string)
```
`status` no banco aceita 4 valores (`pending_payment`, `confirmed`, `cancelled`, `completed` — CHECK constraint no Postgres), mas **na prática só `pending_payment` e `confirmed` são escritos** em algum lugar do código hoje; `cancelled`/`completed` são tratados defensivamente (stats) mas nada os produz ainda. Não remover esses dois do CHECK constraint achando que são "mortos" — são reservados pro futuro.

## 5. Autenticação (dual transport — cookie E bearer)
- O backend aceita **duas formas** de autenticação simultaneamente: cookie httpOnly `session_token` OU header `Authorization: Bearer <token>`. Isso existe porque o ingress da Emergent corta cookies cross-origin (ver comentário em `auth_session`, `backend/server.py:788`).
- O frontend depende do Bearer via `localStorage` (chave `oasis_token`, ver `frontend/src/lib/api.js`) como caminho principal. **Não remover o suporte a Bearer** assumindo que cookie basta — em produção fora do domínio da Emergent isso pode até ser o único caminho que funciona, dependendo de como cookies same-site/cross-site se comportam no domínio final.
- Sessões expiram em 7 dias (hardcoded, `timedelta(days=7)` em dois lugares: cookie `max_age` e `user_sessions.expires_at`) — mudar um sem o outro cria inconsistência.

## 6. Regras de admin
- Bootstrap: primeiro usuário a fazer login (`total_users == 0`) vira admin automaticamente.
- Emails em `ADMIN_EMAILS` (env, separado por vírgula, case-insensitive) sempre viram/ficam admin a cada login.
- Não existe endpoint para "remover" admin — é feito só por `UPDATE` direto no Postgres. Não presumir que existe rota de revogação sem checar o código primeiro.

## 7. Tabelas Postgres (nomes fixos, não renomear)
`users`, `user_sessions`, `massagistas`, `bookings`, `payment_transactions`, `reviews`, `whatsapp_clicks`, `profile_views`, `files`. Schema completo em `backend/migrations/0001_initial_schema.sql`.

## 8. Object Storage — disco local (migrado em 2026-07-18)
Arquivos de mídia (fotos/vídeo) ficam em disco local, dentro de `STORAGE_DIR` (env, default `/data/uploads`) — ver `put_object()`/`get_object()` em `backend/server.py`. Precisa ser um **volume Docker nomeado** (`uploads_data`, já configurado em `docker-compose.yml`), senão o conteúdo some a cada recriação do container. `_storage_full_path()` resolve o path e rejeita qualquer tentativa de escapar `STORAGE_DIR` (defesa em profundidade — `storage_path` sempre é gerado com `uuid4` internamente, nunca vem de input direto do usuário). Substitui a dependência anterior do Object Storage da Emergent (`EMERGENT_LLM_KEY`) — ver item 10 (histórico).

## 9. Pacote de pagamento (migrado em 2026-07-12)
Stripe é acessado via **SDK oficial `stripe`** (PyPI, `stripe>=15.3.0`), usando os métodos assíncronos nativos (`stripe.checkout.Session.create_async`, `.retrieve_async`, `stripe.Webhook.construct_event`). Não usa mais o wrapper `emergentintegrations.payments.stripe.checkout` — esse pacote foi removido do `requirements.txt` porque não está disponível no PyPI público (bloqueava deploy fora do ambiente Emergent).

Pontos que não podem quebrar:
- `POST /api/checkout/session` continua devolvendo `{"url": ..., "session_id": ...}` (mesmo shape de antes).
- `GET /api/checkout/status/{session_id}` continua devolvendo `{"status", "payment_status", "amount_total", "currency", "booking_id"}`. **`amount_total` é retornado em centavos** (formato nativo do Stripe) — o frontend já divide por 100 em `CheckoutSuccess.jsx:57`, então não mudar essa unidade sem atualizar o frontend também.
- `POST /api/webhook/stripe` agora valida a assinatura com `stripe.Webhook.construct_event(body, signature, STRIPE_WEBHOOK_SECRET)` — isso exige a variável de ambiente **`STRIPE_WEBHOOK_SECRET`** (novo requisito, não existia com o wrapper da Emergent). Sem ela configurada corretamente (o segredo gerado no dashboard do Stripe para o endpoint do webhook), toda chamada de webhook falha com 400.
- O valor em reais salvo em `payment_transactions.amount` continua sendo a unidade decimal (ex: `150.0`), não centavos — só o que trafega com o Stripe (`unit_amount`, `amount_total`) é em centavos. Não confundir as duas unidades ao mexer nesse fluxo.

## 10. Object Storage — RESOLVIDO em 2026-07-18 (era dependência adiada da Emergent)
Histórico: na migração de 2026-07-12 pra VPS Docker, o Object Storage da Emergent (`EMERGENT_LLM_KEY`) foi mantido de propósito ("decisão: trocar só o Stripe agora, Object Storage fica pra depois"). Isso causou upload de foto/vídeo quebrado em produção — a chave nunca foi validada fora do ambiente Emergent. Resolvido migrando pra disco local (ver item 8). `EMERGENT_LLM_KEY` foi removida do código e do `.env.example`.

## 11. Banco de dados — migrado de MongoDB pra PostgreSQL (2026-07-12)
Migração completa (schema + queries + ETL de dados), documentada em detalhe — inventário, design aprovado e implementação. Pontos que não podem quebrar:

- **Driver**: `asyncpg` puro (sem ORM). Pool global `pool: asyncpg.Pool`, criado no `startup` do FastAPI a partir de `DATABASE_URL`. Não confundir com o padrão antigo `db.<collection>.<op>()` do motor — todo acesso agora é `await pool.fetch/fetchrow/fetchval/execute(sql, *params)`.
- **`_row()` / `_rows()`** (`backend/server.py`): convertem `asyncpg.Record` em dict JSON-seguro — `Decimal→float`, `datetime→isoformat string`, `date→"YYYY-MM-DD"`, `time→"HH:MM"`. Qualquer query nova que retorne linha pra API **precisa** passar por essas funções, senão a resposta quebra a serialização JSON (asyncpg devolve `Decimal`/`date`/`time` nativos, que o FastAPI não serializa do jeito que o contrato espera).
- **`_massagista_out()`**: reconstrói o objeto `verification` aninhado a partir das colunas achatadas (`verification_status`, `verification_id_check`, etc.) e remove `is_deleted`/`deleted_by`/`deleted_at` da resposta (soft-delete é implementação interna, nunca aparece na API). **Toda leitura de `massagistas` que vai pra API tem que passar por essa função.**
- **Soft-delete em `massagistas`**: colunas `is_deleted`/`deleted_by`/`deleted_at` existem no schema mas **não há endpoint que exclua massagista hoje** — são preparatórias. Todas as queries de leitura filtram `WHERE is_deleted = false`. Se um endpoint de exclusão for criado no futuro, ele deve fazer `UPDATE ... SET is_deleted = true`, nunca `DELETE FROM massagistas` — as FKs de `bookings`/`reviews`/`whatsapp_clicks`/`profile_views`/`files` pra `massagistas(id)` são `ON DELETE RESTRICT` de propósito, um `DELETE` de verdade com histórico associado falha (é a garantia estrutural, não só disciplina de código).
- **FK circular resolvida via `ALTER TABLE`**: `bookings.payment_session_id → payment_transactions.session_id` e `payment_transactions.booking_id → bookings.id` se referenciam mutuamente. A migration cria `bookings` sem a primeira FK, cria `payment_transactions` depois, e só então adiciona a FK via `ALTER TABLE ... ADD CONSTRAINT` no fim de `0001_initial_schema.sql`. Não reordenar os `CREATE TABLE` sem entender essa dependência.
- **`reviews.booking_id` tem `UNIQUE`** — "1 review por reserva" agora é garantido pelo banco, não só pela checagem em `create_review()`. Isso é mais forte que o comportamento Mongo original (que só checava na aplicação) — enrijecimento deliberado, aprovado na revisão de design.
- **`gallery`/`specialties`/`languages`** são `TEXT[]` nativo — mutações usam `array_append`/`array_remove` (equivalentes a `$push`/`$pull` do Mongo). Busca textual em `specialties` usa `EXISTS (SELECT 1 FROM unnest(specialties) s WHERE s ILIKE ...)`.
- **Migrations**: `backend/migrations/0001_initial_schema.sql` + `run_migrations.py` (runner mínimo, sem Alembic, idempotente via tabela `schema_migrations`). Roda automaticamente no boot do container (ver `docker-compose.yml`).
- **ETL de dados** (`backend/migrate_mongo_to_postgres.py`): script one-shot já executado na migração de 2026-07-12, mantido só como referência/auditoria — não roda em deploys normais. É tolerante a documentos Mongo divergentes do schema do código (achado real do inventário: o script `cleanup_for_production.py` inseria massagistas com campos antigos como `phone_ddd`/`phone_number` em vez de `ddd`/`phone`, e sem `bairro_slug`/`hourly_rate`/`experience_years`/`verification`) — usa `.get(...)` com defaults em vez de acesso direto por chave. `user_sessions` **não foi migrada** (tokens efêmeros — usuários precisaram logar de novo após o corte).
- **Testes** (`backend/tests/conftest.py`): a suíte usava `pymongo` direto em `conftest.py` **e também em `test_iter4.py`** (fixture local `mongo`, descoberta só durante a migração — não capturada no inventário inicial porque usava nome de fixture diferente de `mongo_db`). Ambos os arquivos agora usam um shim (`_PgCollection`/`_PgDB` em `conftest.py`) que imita o subset da API do pymongo (`insert_one`/`find_one`/`delete_one`/`delete_many`/`update_one` com `$set`) sobre Postgres — mantém quase 100% do código de teste original intacto. Novas asserções de teste que insiram diretamente no banco precisam respeitar as FKs (ex: `massagista_id` de um booking de teste precisa apontar pra uma massagista real — sob Mongo isso não era checado).
