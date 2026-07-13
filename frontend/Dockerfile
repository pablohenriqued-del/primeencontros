# ---- Stage 1: build (só existe durante `docker build`, não vai pra imagem final) ----
FROM node:20-alpine AS build
WORKDIR /app

# Sem yarn.lock commitado no repo hoje (ver .ai/docs/EXECUTION_ORDER.md) —
# build não é 100% reprodutível até isso ser gerado e versionado.
COPY package.json ./
RUN yarn install

COPY . .

# REACT_APP_BACKEND_URL é embutida no bundle JS neste momento (padrão CRA) —
# mudar depois do build exige rebuild, não dá pra trocar em runtime.
ARG REACT_APP_BACKEND_URL
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL
RUN yarn build

# ---- Stage 2: runtime — só nginx + arquivos estáticos, sem node/yarn ----
FROM nginx:1.27-alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
