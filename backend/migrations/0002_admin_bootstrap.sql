-- Promove um e-mail específico a admin, se o usuário já existir (já tiver
-- feito login pelo menos uma vez via Google). Roda uma única vez (idempotente
-- via schema_migrations, ver run_migrations.py) — se o e-mail ainda não
-- existir em `users` nesse momento, o UPDATE simplesmente não afeta nenhuma
-- linha e não dá erro.
--
-- Se a pessoa ainda não tiver logado nunca, o caminho é diferente: colocar o
-- e-mail em ADMIN_EMAILS (backend/.env) — o próprio app promove a admin
-- automaticamente no primeiro login (ver CONTRACTS.md #6 e server.py:auth_session).

UPDATE users SET is_admin = true WHERE email = 'luiz.tinti@tintitech.com.br';
