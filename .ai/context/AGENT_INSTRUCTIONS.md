# Protocolo para agentes de IA neste repositório

Leia primeiro `.ai/context/ARCHITECTURE.md` e `.ai/context/CONTRACTS.md` antes de mexer em qualquer coisa. Este projeto foi gerado pela plataforma Emergent e tem convenções próprias que não são óbvias lendo só o código.

## Regras gerais
1. **Backend é um arquivo único** (`backend/server.py`, ~1750 linhas). Não quebre em módulos "porque fica mais organizado" sem o usuário pedir — é uma decisão de escopo, não um acidente a ser corrigido.
2. **Não renomeie "Prime Encontros" / "Oásis Rio"** para unificar sem perguntar. A duplicidade de nome é conhecida (ver ARCHITECTURE.md) e mexer nisso afeta UI, título da API, tags Open Graph e possivelmente SEO/links já compartilhados.
3. **Nunca commite segredos.** `.env` (backend e frontend), chaves Stripe, `EMERGENT_LLM_KEY`, `DATABASE_URL` com senha real — tudo isso é ignorado pelo `.gitignore` e deve continuar assim. Se precisar documentar uma variável nova, documente o *nome*, nunca o *valor*.
4. **Não edite o bloco de cabeçalho de `test_result.md`** (entre `# START - Testing Protocol` e `# END - Testing Protocol`) — é protocolo fixo da Emergent para comunicação entre agentes de teste. Pode adicionar dados abaixo dele.
5. **Duas dependências da Emergent ainda são externas e frágeis**: `EMERGENT_AUTH_SESSION_URL` (proxy de OAuth) e o Object Storage (`integrations.emergentagent.com`, fotos/vídeo). O Stripe **já foi migrado** pro SDK oficial (2026-07-12, ver CONTRACTS.md #9) e não é mais um bloqueio. Qualquer mudança de hospedagem/deploy precisa considerar se auth e storage continuam acessíveis — ver `.ai/docs/DEPLOY.md`.
6. **Antes de mudar rotas de API, schema do banco, ou formato de resposta**, confira `.ai/context/CONTRACTS.md`. Se a mudança quebrar algo listado lá, é obrigatório: (a) avisar o usuário explicitamente que é uma mudança que quebra contrato, e (b) esperar confirmação antes de aplicar — não faça isso silenciosamente numa tacada só com outras mudanças.
7. **Banco é PostgreSQL desde 2026-07-12** (migrado do MongoDB — ver ARCHITECTURE.md e CONTRACTS.md #11). Mudança de schema é sempre uma **nova migration** em `backend/migrations/000N_*.sql`, nunca editar `0001_initial_schema.sql` depois de aplicado em produção. Toda query nova que retorna linha pra API precisa passar por `_row()`/`_rows()` (e `_massagista_out()` se for massagista) — senão `Decimal`/`date`/`time` do asyncpg quebram a serialização JSON.
8. **Massagistas/dados de produção**: o seed atual (pós `cleanup_for_production.py`) tem só 1 profissional de teste ("Lara", Ipanema). Não rode scripts de seed em massa ou popule dados fake em ambiente que pareça produção sem confirmar com o usuário — pode ser o banco real já em uso por usuários reais.
9. **Uploads de mídia (fotos/vídeo) dependem do Object Storage da Emergent.** Se for testar upload localmente e a chave `EMERGENT_LLM_KEY` não estiver configurada, o upload vai falhar com 500 — isso é esperado, não é bug a ser "corrigido" mudando a lógica de storage.
10. Antes de dar como concluída qualquer mudança de frontend, rode `yarn build` (ou `craco build`) na pasta `frontend/` e confirme que não há erro. Para backend, rode a suíte em `backend/tests/` com pytest se a mudança tocar lógica de API — contra um Postgres real, nunca contra Mongo (a suíte foi migrada em 2026-07-12).
11. Ao final de qualquer análise ou mudança relevante, atualize `.ai/docs/EXECUTION_ORDER.md` com o novo estado — esse arquivo existe justamente para a próxima sessão (humana ou de IA) não ter que reanalisar tudo do zero.

## Convenção de commits
Formato obrigatório: `tipo(escopo): descrição curta no imperativo`.

- `feat(escopo): descrição` — funcionalidade nova
- `fix(escopo): descrição` — correção de bug
- `chore(escopo): descrição` — manutenção, dependências, config, sem mudança de comportamento
- `docs(escopo): descrição` — documentação (inclui mudanças em `.ai/`)

Exemplos de escopo: `backend`, `frontend`, `admin`, `booking`, `auth`, `storage`, `deploy`, `ai-docs`.

Exemplos:
- `feat(booking): adicionar cancelamento de reserva pelo cliente`
- `fix(auth): corrigir expiração de sessão não sendo checada`
- `chore(deploy): documentar variáveis de ambiente do build`
- `docs(ai-docs): atualizar EXECUTION_ORDER com pendências do sprint`

**Não use `git commit --amend` nem force-push** a menos que o usuário peça explicitamente. Sempre criar um commit novo. Não commitar sem o usuário pedir explicitamente (a menos que instruções do projeto digam o contrário).

## O que não mexer sem revisão explícita do usuário
- `test_result.md` (cabeçalho de protocolo)
- Nomes das tabelas Postgres (`users`, `user_sessions`, `massagistas`, `bookings`, `payment_transactions`, `reviews`, `whatsapp_clicks`, `profile_views`, `files`) — renomear quebra dados já existentes e migrations aplicadas
- `backend/migrations/0001_initial_schema.sql` depois de aplicado em produção — mudança de schema é sempre uma migration nova, nunca editar uma já aplicada
- Lógica de bootstrap de admin (`total_users == 0` vira admin) — mexer aqui pode criar admin indevido ou travar acesso administrativo
- `design_guidelines.json` — é a fonte da identidade visual; mudanças de paleta/tipografia devem ser intencionais, não efeito colateral de outra tarefa
- Qualquer coisa dentro de `.emergent/` — metadata da plataforma, não é config de aplicação
