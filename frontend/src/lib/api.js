import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

const TOKEN_KEY = "oasis_token";

export function getToken() { return localStorage.getItem(TOKEN_KEY) || ""; }
export function setToken(t) { if (t) localStorage.setItem(TOKEN_KEY, t); else localStorage.removeItem(TOKEN_KEY); }

export const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  const t = getToken();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

export function brl(value) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value || 0);
}

// Resolve "/api/files/..." (caminho relativo salvo no banco) pra URL absoluta
// do backend. Sem isso, um <img src="/api/files/...">  aponta pro domínio do
// FRONTEND (onde a página está), não pro backend — quebra sempre que
// frontend e backend estão em domínios diferentes (produção normalmente usa
// subdomínios distintos, ex: app.primeencontros.com / api.primeencontros.com).
// URLs absolutas (seed de demonstração, foto do Google) passam direto.
export function resolveMediaUrl(u) {
  if (!u) return u;
  if (u.startsWith("http")) return u;
  const root = API_BASE.replace(/\/api$/, "");
  return `${root}${u}`;
}
