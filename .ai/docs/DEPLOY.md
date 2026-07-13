# Deploy — Prime Encontros

**Destino atual (desde 2026-07-12): VPS própria via Docker/Portainer, compartilhada com o stack `anuncifacil` e o `noxsystems_npm` (Nginx Proxy Manager).** O plano anterior de FTP em hospedagem compartilhada (Localweb) foi descartado — ficou registrado só como contexto histórico no fim deste arquivo, caso surja de novo.

**Banco de dados (atualizado 2026-07-12): PostgreSQL, não mais MongoDB próprio.** O primeencontros não sobe mais um container de banco seu — reaproveita o `noxsystems_postgres-db` já rodando nessa VPS (usado pelo anuncifacil), com um banco e usuário **dedicados** (não o schema do anuncifacil). Motivo: reduzir RAM (um container de banco a menos rodando) e reaproveitar infraestrutura que já existe. Ver seção 4 pra criar esse banco/usuário antes do primeiro deploy, e `.ai/context/CONTRACTS.md` #11 pro detalhe técnico completo da migração Mongo→Postgres.

Servidor: **3,8GB RAM total**, ~1,7GB livre no momento do dimensionamento abaixo (containers do anuncifacil + noxsystems já usam ~1,52GB). Disco: 100GB, 49GB livres — não é o gargalo. Swap: 2GB (756MB em uso). **RAM é o recurso escasso** — todo o dimensionamento abaixo gira em torno disso.

---

## 1. Arquivos gerados nestas migrações
```
docker-compose.yml          # raiz do repo — copiar/clonar pra /opt/primeencontros/ na VPS
.env.example                 # → /opt/primeencontros/.env (só REACT_APP_BACKEND_URL, usado no build do frontend)
backend/Dockerfile
backend/.dockerignore
backend/.env.example          # → backend/.env (segredos reais do backend, agora com DATABASE_URL)
backend/migrations/0001_initial_schema.sql   # schema Postgres completo
backend/migrations/run_migrations.py         # runner das migrations (roda automático no boot do container)
backend/migrate_mongo_to_postgres.py         # ETL one-shot (já rodado, mantido como referência)
frontend/Dockerfile           # multi-stage: build (node) → runtime (nginx só com estático)
frontend/nginx.conf
frontend/.dockerignore
```
Os `Dockerfile`/`docker-compose.yml`/migrations foram **testados localmente** (`docker build`, `docker compose config`, migration aplicada num Postgres local, suíte de testes rodando contra o backend real) antes de entregar — ver `.ai/reviews/REVIEW_CHECKLIST.md` pra reproduzir.

## 2. Por que trocar `emergentintegrations` importava pro deploy
O backend usava um pacote (`emergentintegrations==0.2.0`) que **não existe no PyPI público** — `pip install -r requirements.txt` falhava fora do ambiente Emergent. Isso foi resolvido nesta mesma leva: o wrapper de Stripe foi trocado pelo SDK oficial `stripe` (ver `.ai/context/CONTRACTS.md` #9). **O Object Storage da Emergent (fotos/vídeo, `EMERGENT_LLM_KEY`) foi mantido de propósito** — não foi migrado, é dependência externa que continua ativa (ver CONTRACTS.md #10). Isso significa que o backend, mesmo rodando nesta VPS, ainda precisa de egress HTTPS liberado para `integrations.emergentagent.com` e `demobackend.emergentagent.com` (auth).

De quebra, ao migrar, encontrei e corrigi um bug real: `backend/promo_card.py` importa `PIL` (Pillow), mas `Pillow` **não estava** no `requirements.txt` — funcionava só porque a imagem-base da Emergent já vinha com Pillow pré-instalado. Rodar `pip install -r requirements.txt` num container Python limpo (como o `backend/Dockerfile` novo) sem essa correção derrubaria o backend inteiro na subida (`from promo_card import generate_promo_card` roda no import do `server.py`). Já corrigido — `Pillow>=10.3.0` está no requirements.txt.

Também removi do `requirements.txt` os pacotes confirmados como não usados em nenhum lugar do backend (`pandas`, `numpy`, `boto3`, `cryptography`, `python-jose`, `pyjwt`, `bcrypt`, `passlib`, `requests-oauthlib`, `email-validator`, `jq`, `typer` — grep confirma zero import em `server.py`, `promo_card.py`, `cleanup_for_production.py` e nos testes). A autenticação deste app não usa JWT nem hash de senha — é token opaco guardado em `user_sessions` no Mongo. Isso não muda RAM em runtime (pacote não importado não é carregado), mas reduz tempo/superfície de build da imagem Docker.

## 3. Limites de memória — de onde veio cada número
RAM disponível real na VPS hoje: ~1,7GB. Sem container de banco próprio (Postgres é compartilhado com o anuncifacil), o primeencontros agora só sobe **2 containers**:

| Serviço | `mem_limit` | Por quê |
|---|---|---|
| `backend-app-prod` | **400m** | 1 worker uvicorn. Import real do processo é leve (fastapi, asyncpg, stripe, httpx, Pillow, dotenv) — nada de pandas/numpy/boto3/motor/pymongo (removidos, ver seção 2 e CONTRACTS.md #11). Baseline esperado: ~150-250MB num único worker; 400MB dá margem. **Não subir pra 2 workers sem medir primeiro** — cada worker uvicorn é um processo Python separado, dobra o baseline. |
| `frontend-nginx-prod` | **100m** | Só serve arquivos estáticos (build do CRA) via nginx — sem node, sem build tooling na imagem final. nginx-alpine puro consome tipicamente 5-20MB; 100MB é folga generosa. |

Total: até 500MB no pior caso contra ~1,7GB livres — bem mais folgado do que quando havia um Mongo próprio (que sozinho já pedia 700MB). **Atenção**: o `noxsystems_postgres-db` compartilhado tem seu próprio consumo de RAM, que não é dimensionado aqui (é gerenciado pelo stack do anuncifacil) — se o volume de dados do primeencontros crescer bastante, o consumo desse Postgres compartilhado sobe pra os dois lados, revisar junto com quem administra o anuncifacil.

Todos os serviços têm `restart: unless-stopped`. Se o backend bater no `mem_limit`, o Docker mata o processo (OOM-kill) e o restart policy sobe de novo — isso evita travar a VPS inteira, mas mascara um limite curto demais como "reinício aleatório". Rodar `docker stats --no-stream` logo depois do primeiro deploy (e sob uso real) pra confirmar que os limites batem com o consumo de verdade, não só em teste local.

## 4. Antes do primeiro `docker compose up`

### 4.1 Criar o banco e usuário dedicados dentro do `noxsystems_postgres-db`
O primeencontros usa um banco **próprio**, não o schema do anuncifacil, dentro do mesmo container Postgres compartilhado. Rodar uma vez, direto no container existente (trocar `SENHA_FORTE_AQUI` por uma senha real, gerada, não essa placeholder):
```bash
docker exec -it noxsystems_postgres-db psql -U postgres -v ON_ERROR_STOP=1 <<'EOF'
CREATE USER primeencontros WITH PASSWORD 'SENHA_FORTE_AQUI';
CREATE DATABASE primeencontros OWNER primeencontros;
EOF
```
(`docker exec` precisa do `-i` — sem ele o heredoc não chega no `psql`, ele simplesmente não recebe nada e não dá erro nenhum — isso já me mordeu uma vez testando isso localmente.) Se o usuário `postgres` (superuser) tiver outro nome nesse container, ajustar o `-U`. Guardar a senha gerada — ela vai pro `DATABASE_URL` do `backend/.env` (seção 4.3).

Depois de criado, as migrations (`backend/migrations/0001_initial_schema.sql`) rodam sozinhas no boot do container backend (ver `docker-compose.yml`, `command:`) — não precisa aplicar nada à mão.

### 4.2 Se já existir dado de produção no MongoDB antigo: rodar o ETL uma vez
Só se houver dado real acumulado no Mongo antes deste corte (não é o caso se ainda estiver só com o seed de teste). Rodar uma única vez, **antes** de considerar o Mongo antigo desligado:
```bash
cd backend
pip install pymongo asyncpg python-dotenv   # não são dependências do app em produção, só deste script
MONGO_URL=<url do Mongo antigo> DB_NAME=<nome do banco antigo> \
DATABASE_URL=<a mesma DATABASE_URL do backend/.env, já com o banco criado na seção 4.1> \
python3 migrate_mongo_to_postgres.py
```
Ver `.ai/context/CONTRACTS.md` #11 pro que esse script cobre (e o que ele deliberadamente não migra — `user_sessions`, por serem tokens efêmeros).

### 4.3 Descobrir as redes Docker do `noxsystems_npm` e do `noxsystems_postgres-db`
O `docker-compose.yml` referencia duas redes externas — `NOME_DA_REDE_DO_NPM` e `NOME_DA_REDE_DO_POSTGRES` (placeholders, trocar pelos nomes reais antes do primeiro `up`; podem ser a mesma rede, se o NPM e o Postgres já compartilharem uma). Descobrir com:
```bash
docker ps --format '{{.Names}}' | grep -iE 'npm|postgres'
docker inspect <nome_do_container> --format '{{json .NetworkSettings.Networks}}'
```
Pegar a chave (nome da rede) do JSON retornado e substituir no `docker-compose.yml` (`networks.npm_network.name` e `networks.postgres_network.name`).

### 4.4 Preencher os `.env`
```bash
cp .env.example .env                       # REACT_APP_BACKEND_URL
cp backend/.env.example backend/.env        # DATABASE_URL, STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET, EMERGENT_LLM_KEY, ADMIN_EMAILS
```
`DATABASE_URL` usa o usuário/senha/banco criados na seção 4.1 e o nome do container `noxsystems_postgres-db` como host (mesma rede Docker, resolve por DNS interno do compose): `postgresql://primeencontros:SENHA_FORTE_AQUI@noxsystems_postgres-db:5432/primeencontros`. `STRIPE_WEBHOOK_SECRET` é novo (não existia com o wrapper da Emergent) — gerar no dashboard do Stripe ao criar o endpoint do webhook, apontando pra `https://api.primeencontros.com/api/webhook/stripe`.

## 5. Subir o stack
```bash
cd /opt/primeencontros
docker compose build
docker compose up -d
docker compose ps
docker compose logs backend-app-prod --tail 50   # confirmar que as migrations aplicaram sem erro
docker stats --no-stream
free -h
```
Confirmar: os 2 containers com os nomes exatos (`primeencontros_backend-app-prod`, `primeencontros_frontend-nginx-prod`), `healthy` no backend, o log mostrando a migration aplicada (ou "Nada a aplicar" se já rodou antes), e o consumo de memória em `docker stats` dentro dos `mem_limit` configurados.

## 6. Nginx Proxy Manager (`noxsystems_npm`) — domínio `primeencontros.com`

Recomendado: **dois Proxy Hosts** (mais simples de configurar na UI do NPM do que path-based routing num domínio só, e casa com `REACT_APP_BACKEND_URL` sendo uma origem própria).

### Proxy Host 1 — frontend
| Campo | Valor |
|---|---|
| Domain Names | `primeencontros.com`, `www.primeencontros.com` |
| Scheme | `http` |
| Forward Hostname/IP | `primeencontros_frontend-nginx-prod` |
| Forward Port | `80` |
| Block Common Exploits | ligado |
| SSL | Request a new SSL Certificate (Let's Encrypt) → Force SSL + HTTP/2 |

### Proxy Host 2 — backend (API)
| Campo | Valor |
|---|---|
| Domain Names | `api.primeencontros.com` |
| Scheme | `http` |
| Forward Hostname/IP | `primeencontros_backend-app-prod` |
| Forward Port | `8001` |
| Block Common Exploits | ligado |
| SSL | Request a new SSL Certificate (Let's Encrypt) → Force SSL + HTTP/2 |

E então `REACT_APP_BACKEND_URL=https://api.primeencontros.com` no `.env` da raiz (já é o default no `.env.example`).

Pré-requisito pra isso funcionar: os containers `primeencontros_frontend-nginx-prod` e `primeencontros_backend-app-prod` precisam estar na **mesma rede Docker** que o container do NPM (seção 4.2) — sem isso, o NPM não consegue resolver o hostname do container no "Forward Hostname/IP".

### Alternativa (um domínio só, sem subdomínio de API)
Se preferir não criar `api.primeencontros.com`, dá pra rotear por path no mesmo Proxy Host do frontend, na aba **"Custom Nginx Configuration"**:
```nginx
location /api {
    proxy_pass http://primeencontros_backend-app-prod:8001;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```
Nesse caso `REACT_APP_BACKEND_URL=https://primeencontros.com` (sem `/api` — o frontend já concatena `/api` sozinho em `frontend/src/lib/api.js`).

## 7. Aumentar swap de 2GB pra 4GB sem perder o que já está em uso
**Não mexer no swap já ativo** (não dar `swapoff` nele) — isso forçaria o kernel a mover os 756MB já em uso de volta pra RAM, arriscado numa máquina com só ~1,7GB livres se outro processo pedir memória no meio da operação. O caminho seguro é **somar** um segundo swapfile, sem tocar no existente:
```bash
# 1. Confirmar o que já existe (não sobrescrever por engano)
sudo swapon --show
free -h

# 2. Criar um novo swapfile de 2GB (2GB existente + 2GB novo = 4GB total)
sudo fallocate -l 2G /swapfile2 || sudo dd if=/dev/zero of=/swapfile2 bs=1M count=2048
sudo chmod 600 /swapfile2
sudo mkswap /swapfile2
sudo swapon /swapfile2

# 3. Confirmar os dois ativos e o total
sudo swapon --show
free -h

# 4. Só depois de confirmar que funcionou: persistir no boot
echo '/swapfile2 none swap sw 0 0' | sudo tee -a /etc/fstab
```
Se `swapon --show` já mostrar um caminho diferente de `/swapfile` (ex: partição dedicada), usar outro nome de arquivo (`/swapfile2`) de qualquer forma evita colisão — o comando acima já assume isso.

## 8. Variáveis de ambiente — referência rápida
| Arquivo | Variável | Obrigatória | Observação |
|---|---|---|---|
| `.env` (raiz) | `REACT_APP_BACKEND_URL` | Sim | Só usada como build-arg do frontend — mudar exige `docker compose build` de novo, não só `up`. |
| `backend/.env` | `DATABASE_URL` | Sim | `postgresql://primeencontros:SENHA@noxsystems_postgres-db:5432/primeencontros` — processo derruba sem isso. Banco/usuário criados na seção 4.1. |
| `backend/.env` | `STRIPE_API_KEY` | Recomendada | Checkout falha sem ela. |
| `backend/.env` | `STRIPE_WEBHOOK_SECRET` | Recomendada | Sem ela, todo webhook do Stripe recebe 400. |
| `backend/.env` | `EMERGENT_LLM_KEY` | Recomendada | Object Storage (fotos/vídeo) ainda depende da Emergent — ver CONTRACTS.md #10. |
| `backend/.env` | `ADMIN_EMAILS` | Opcional | Sem isso, só o primeiro usuário a logar vira admin. |

## 9. Pendências conhecidas
- Não existe `yarn.lock` commitado no `frontend/` — o build funciona (testado), mas não é 100% reprodutível (versões de dependência podem variar entre builds). Gerar localmente com `yarn install` e commitar o `yarn.lock` é recomendado antes do próximo build de produção.
- Placeholders `NOME_DA_REDE_DO_NPM` e `NOME_DA_REDE_DO_POSTGRES` no `docker-compose.yml` precisam ser trocados pelos nomes reais antes do primeiro `up` (seção 4.3).
- Checkout (Stripe) e upload de mídia (Object Storage) foram migrados/revisados no código e testados o quanto dava sem credenciais reais — mas não foram exercitados ponta-a-ponta neste ambiente (sem `sk_test_...` real nem `EMERGENT_LLM_KEY` real). Validar manualmente na VPS com as chaves de verdade antes de considerar essas duas funcionalidades 100% confirmadas em produção.

---

## Histórico — plano anterior (FTP / Localweb, descartado em 2026-07-12)
Esse plano previa subir só o frontend estático via FTP simples em hospedagem compartilhada, e deixava o backend sem destino definido (FTP puro nunca foi viável pro backend — precisa de processo Python persistente + banco de dados, que hospedagem compartilhada não oferece). Superado pela VPS Docker acima, que resolve as duas pontas de uma vez.
