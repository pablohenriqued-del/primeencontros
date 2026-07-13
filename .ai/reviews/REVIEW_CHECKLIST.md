# Checklist antes de subir mudanças pra produção

Marque item por item. Não pular etapas de build/teste achando que "é só uma mudança pequena" — o backend é um arquivo único de 1750+ linhas e um erro de sintaxe/import derruba tudo.

## Backend
- [ ] `python -m py_compile backend/server.py` (ou importar o módulo) não dá erro de sintaxe
- [ ] `uvicorn server:app --reload` sobe sem exceção no startup (confere `seed_massagistas()` e a criação do pool `asyncpg` não quebraram)
- [ ] `backend/.env` tem `DATABASE_URL` preenchida (processo derruba sem ela)
- [ ] Se mudou o schema: nova migration criada em `backend/migrations/000N_*.sql` (nunca editar `0001_initial_schema.sql` depois de aplicado em produção) e `python3 -m migrations.run_migrations` aplicada sem erro
- [ ] Se a mudança mexeu em upload de mídia: `EMERGENT_LLM_KEY` está configurada e o Object Storage responde (testar um upload real, não só o código)
- [ ] Se a mudança mexeu em checkout/pagamento: `STRIPE_API_KEY` configurada e testar um checkout de ponta a ponta em modo teste
- [ ] Rodar a suíte de testes: `cd backend && pytest tests/` — confirmar que `test_oasis_rio.py`, `test_media.py`, `test_verification.py`, `test_iter4.py` passam contra um Postgres real (não contra Mongo — a suíte foi migrada em 2026-07-12, ver CONTRACTS.md #11)
- [ ] Se mudou schema de qualquer tabela, ou formato de resposta de rota: conferir `.ai/context/CONTRACTS.md` — se quebrar contrato, isso precisa ter sido avisado e confirmado explicitamente antes, não descoberto agora no checklist
- [ ] Se mudou lógica de admin/auth: testar login com um email fora de `ADMIN_EMAILS` (não deve virar admin) e um dentro (deve virar admin)
- [ ] Se a query nova retorna linha(s) pra API: passou por `_row()`/`_rows()` (e por `_massagista_out()` se for massagista)? Sem isso, `Decimal`/`date`/`time` do asyncpg quebram a serialização JSON — ver CONTRACTS.md #11

## Frontend
- [ ] `cd frontend && yarn build` (craco build) termina sem erro
- [ ] `frontend/.env` tem `REACT_APP_BACKEND_URL` apontando pro backend correto do ambiente que vai receber o deploy (não deixar apontando pra localhost/staging por engano)
- [ ] Rodar `yarn build` e navegar localmente pelo build gerado (`npx serve -s build` ou equivalente) pra pegar erro que só aparece em produção (dev mode esconde alguns)
- [ ] Testar manualmente o fluxo principal no browser: home → filtro/busca → detalhe da massagista → agendamento → checkout (mesmo que em modo teste do Stripe)
- [ ] Testar login (Google/Emergent Auth) e confirmar que token Bearer é persistido e as chamadas autenticadas funcionam
- [ ] Conferir console do browser sem erros de CORS (confirma que o backend está com `allow_origin_regex` compatível com o domínio novo)

## Infraestrutura / deploy (VPS Docker — ver `.ai/docs/DEPLOY.md`)
- [ ] `docker compose config` valida sem erro antes de `up` (pega erro de sintaxe/placeholder esquecido, ex: `NOME_DA_REDE_DO_NPM`/`NOME_DA_REDE_DO_POSTGRES` não trocados)
- [ ] `docker compose build` termina sem erro pros dois serviços (backend, frontend — não há mais container de banco próprio)
- [ ] `docker stats --no-stream` depois do `up`: consumo real de cada container dentro do `mem_limit` configurado (backend 400m / frontend 100m) — se algum estourar, não é "normal", é sinal de rever o limite ou investigar vazamento
- [ ] `free -h` sem swap saturado (comparar antes/depois)
- [ ] Containers com os nomes exatos esperados: `primeencontros_backend-app-prod`, `primeencontros_frontend-nginx-prod`
- [ ] Postgres acessível pelo backend via `DATABASE_URL` apontando pro `noxsystems_postgres-db` (mesma rede Docker externa) — se não conectar, checar se o banco/usuário dedicados foram criados (DEPLOY.md seção 4.1) e se a rede está certa (seção 4.3)
- [ ] `docker compose logs backend-app-prod` mostra a migration aplicada com sucesso (ou "Nada a aplicar" se já rodou antes) — se falhar aqui, o container nem chega a subir o uvicorn
- [ ] Nginx Proxy Manager consegue resolver os hostnames dos containers (frontend/backend na mesma rede externa do `noxsystems_npm` — ver DEPLOY.md seção 4.3)
- [ ] SPA fallback funciona: dar refresh numa rota interna do React (ex: `/admin`) não pode dar 404 — testado localmente com `nginx.conf` do `frontend/`, mas confirmar de novo atrás do domínio real
- [ ] `pip install -r requirements.txt` completo dentro da imagem do backend não falha (checado: `stripe`, `asyncpg`, `Pillow` e o restante instalam via wheel sem pacote externo à PyPI)

## Segurança / dados
- [ ] Nenhum arquivo `.env`, chave Stripe, `EMERGENT_LLM_KEY` ou `DATABASE_URL` com senha real foi commitado (`git status` e `git diff` antes do commit — não confiar só no `.gitignore`)
- [ ] Se mexeu em dados de produção (massagistas, bookings): confirmar que não é o banco de um usuário real antes de rodar qualquer `DELETE`/`TRUNCATE` manual no Postgres
- [ ] Páginas `/termos` e `/privacidade`: se ainda tiverem placeholders `[colchetes]`, não é bloqueante pra deploy técnico, mas é bloqueante pra lançamento público real (LGPD) — confirmar com o usuário se isso já foi resolvido

## Git
- [ ] Commit segue a convenção `tipo(escopo): descrição` (ver `.ai/context/AGENT_INSTRUCTIONS.md`)
- [ ] `.ai/docs/EXECUTION_ORDER.md` atualizado se a mudança alterou o estado geral do projeto (nova feature, pendência resolvida, pendência nova descoberta)
