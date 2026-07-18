import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, brl, resolveMediaUrl } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ShieldCheck, ShieldAlert, ShieldX, MapPin, Star, Loader2, ImageIcon, Pencil, MessageCircle, TrendingUp, CalendarCheck, Plus, Users, ShieldPlus, Trash2, FileText, ScanFace, Play } from "lucide-react";
import { toast } from "sonner";
import MediaEditor from "@/components/MediaEditor";
import AdminProfileEditor from "@/components/AdminProfileEditor";
import ManualBookingDialog from "@/components/ManualBookingDialog";

function Pill({ verified }) {
  return verified ? (
    <Badge className="bg-red-600/15 text-red-300 border border-red-600/40 rounded-full">
      <ShieldCheck className="h-3 w-3 mr-1" /> Verificada
    </Badge>
  ) : (
    <Badge className="bg-amber-500/10 text-amber-300 border border-amber-500/30 rounded-full">
      <ShieldAlert className="h-3 w-3 mr-1" /> Pendente
    </Badge>
  );
}

export default function Admin() {
  const { user, loading: authLoading, login } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("queue"); // queue | all | metrics
  const [target, setTarget] = useState(null); // currently moderating
  const [action, setAction] = useState("approve"); // approve | reject
  const [checks, setChecks] = useState({ id: true, photo: true, address: true });
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [mediaTarget, setMediaTarget] = useState(null);
  const [editTarget, setEditTarget] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [bookings, setBookings] = useState([]);
  const [bookingsLoading, setBookingsLoading] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [docs, setDocs] = useState({ id_document_front: null, id_document_back: null, selfie: null });
  const [docsLoading, setDocsLoading] = useState(false);

  const fetchList = async () => {
    setLoading(true);
    try {
      const path = view === "queue" ? "/admin/verification/queue" : "/admin/verification/all";
      const { data } = await api.get(path);
      setItems(data);
    } catch (e) {
      if (e?.response?.status === 403) toast.error("Acesso restrito a administradores");
      else if (e?.response?.status === 401) toast.error("Faça login para acessar");
    } finally {
      setLoading(false);
    }
  };

  const fetchMetrics = async () => {
    setMetricsLoading(true);
    try {
      const { data } = await api.get("/admin/whatsapp/stats");
      setMetrics(data);
    } catch {
      toast.error("Erro ao carregar métricas");
    } finally {
      setMetricsLoading(false);
    }
  };

  const fetchBookings = async () => {
    setBookingsLoading(true);
    try {
      const { data } = await api.get("/admin/bookings");
      setBookings(data);
    } catch {
      toast.error("Erro ao carregar reservas");
    } finally {
      setBookingsLoading(false);
    }
  };

  const fetchUsers = async () => {
    setUsersLoading(true);
    try {
      const { data } = await api.get("/admin/users");
      setUsers(data);
    } catch {
      toast.error("Erro ao carregar usuários");
    } finally {
      setUsersLoading(false);
    }
  };

  useEffect(() => {
    if (authLoading) return;
    if (!user) { setLoading(false); return; }
    if (view === "metrics") {
      fetchMetrics();
    } else if (view === "bookings") {
      fetchBookings();
    } else if (view === "users") {
      fetchUsers();
    } else {
      fetchList();
    }
    /* eslint-disable-next-line */
  }, [user, authLoading, view]);

  if (authLoading) return <div className="max-w-7xl mx-auto px-4 py-20 text-zinc-500">Carregando...</div>;

  if (!user) {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h2 className="font-display text-2xl font-medium text-zinc-50">Painel Administrativo</h2>
        <p className="text-zinc-400 mt-2 mb-6">Acesso restrito. Entre com a conta admin.</p>
        <Button onClick={login} className="rounded-full bg-red-600 hover:bg-red-700 text-white px-6 h-11">
          Entrar com Google
        </Button>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <ShieldX className="h-12 w-12 text-red-600 mx-auto mb-4" />
        <h2 className="font-display text-2xl font-medium text-zinc-50">Acesso negado</h2>
        <p className="text-zinc-400 mt-2 mb-6">
          Sua conta ({user.email}) não tem permissão de admin.
        </p>
        <Button onClick={() => navigate("/")} variant="outline" className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900">
          Voltar
        </Button>
      </div>
    );
  }

  // Duas formas válidas: frente+verso (imagem) ou só a frente em PDF (ver
  // migrations/0004 e approve_verification em server.py — mesma regra).
  const docsComplete = () => {
    if (!docs.selfie || !docs.id_document_front) return false;
    return docs.id_document_front.isPdf || !!docs.id_document_back;
  };

  const openModeration = (m, act) => {
    setTarget(m);
    setAction(act);
    setChecks({ id: true, photo: true, address: true });
    setNotes("");
    loadVerificationDocs(m.id);
  };

  const loadVerificationDocs = async (mid) => {
    setDocs((prev) => {
      Object.values(prev).forEach((d) => d?.url && URL.revokeObjectURL(d.url));
      return { id_document_front: null, id_document_back: null, selfie: null };
    });
    setDocsLoading(true);
    try {
      const { data } = await api.get(`/admin/massagistas/${mid}/verification-documents`);
      const next = { id_document_front: null, id_document_back: null, selfie: null };
      await Promise.all(data.map(async (d) => {
        const res = await api.get(d.url, { responseType: "blob" });
        next[d.kind] = { url: URL.createObjectURL(res.data), isPdf: res.data.type === "application/pdf" };
      }));
      setDocs(next);
    } catch {
      // sem documentos enviados ainda, ou erro de rede — mantém como "não enviado"
    } finally {
      setDocsLoading(false);
    }
  };

  const setUserRole = async (u, isAdmin) => {
    try {
      await api.post(`/admin/users/${u.user_id}/role`, { is_admin: isAdmin });
      toast.success(isAdmin ? `${u.email} agora é admin` : `${u.email} não é mais admin`);
      fetchUsers();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Erro ao alterar permissão");
    }
  };

  const deleteUser = async (u) => {
    if (!window.confirm(`Apagar o usuário ${u.email}? Essa ação não pode ser desfeita.`)) return;
    try {
      await api.delete(`/admin/users/${u.user_id}`);
      toast.success(`Usuário ${u.email} apagado`);
      fetchUsers();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Erro ao apagar usuário");
    }
  };

  const submitModeration = async () => {
    if (!target) return;
    if (action === "reject" && !notes.trim()) {
      toast.error("Informe o motivo da rejeição — a profissional vai ver essa mensagem");
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        id_check: checks.id,
        photo_check: checks.photo,
        address_check: checks.address,
        notes: notes || null,
      };
      const path = action === "approve"
        ? `/admin/verification/${target.id}/approve`
        : `/admin/verification/${target.id}/reject`;
      await api.post(path, payload);
      toast.success(action === "approve" ? "Profissional verificada" : "Verificação rejeitada");
      setTarget(null);
      fetchList();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Não foi possível concluir a moderação");
    } finally {
      setSubmitting(false);
    }
  };

  const revoke = async (m) => {
    if (!window.confirm(`Revogar verificação de ${m.name}?`)) return;
    try {
      await api.post(`/admin/verification/${m.id}/revoke`);
      toast.success("Verificação revogada");
      fetchList();
    } catch {
      toast.error("Erro ao revogar");
    }
  };

  return (
    <div data-testid="admin-page" className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex items-end justify-between flex-wrap gap-4 mb-8">
        <div>
          <h1 className="font-display text-3xl font-medium text-zinc-50">Painel de Verificação</h1>
          <p className="text-zinc-400 mt-1 text-sm">Aprovar e revogar selos "Verificada" das profissionais.</p>
        </div>
        <Tabs value={view} onValueChange={setView}>
          <TabsList className="bg-zinc-950 border border-zinc-900 rounded-full p-1">
            <TabsTrigger value="queue" className="rounded-full data-[state=active]:bg-red-600 data-[state=active]:text-white text-zinc-400" data-testid="tab-queue">Fila</TabsTrigger>
            <TabsTrigger value="all" className="rounded-full data-[state=active]:bg-red-600 data-[state=active]:text-white text-zinc-400" data-testid="tab-all">Todas</TabsTrigger>
            <TabsTrigger value="metrics" className="rounded-full data-[state=active]:bg-red-600 data-[state=active]:text-white text-zinc-400" data-testid="tab-metrics">
              <TrendingUp className="h-3.5 w-3.5 mr-1" /> WhatsApp
            </TabsTrigger>
            <TabsTrigger value="bookings" className="rounded-full data-[state=active]:bg-red-600 data-[state=active]:text-white text-zinc-400" data-testid="tab-bookings">
              <CalendarCheck className="h-3.5 w-3.5 mr-1" /> Reservas
            </TabsTrigger>
            <TabsTrigger value="users" className="rounded-full data-[state=active]:bg-red-600 data-[state=active]:text-white text-zinc-400" data-testid="tab-users">
              <Users className="h-3.5 w-3.5 mr-1" /> Usuários
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {view === "metrics" ? (
        metricsLoading || !metrics ? (
          <div className="space-y-3">{[0,1,2].map(i => <div key={i} className="h-20 rounded-2xl bg-zinc-900 animate-pulse" />)}</div>
        ) : (          <div data-testid="metrics-panel">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
              <div className="rounded-2xl border border-zinc-900 bg-zinc-950 p-4">
                <div className="text-xs uppercase tracking-wider text-zinc-500">Cliques no WhatsApp</div>
                <div className="font-display text-3xl font-semibold text-zinc-50 mt-1" data-testid="metric-total-clicks">{metrics.total_clicks}</div>
              </div>
              <div className="rounded-2xl border border-zinc-900 bg-zinc-950 p-4">
                <div className="text-xs uppercase tracking-wider text-zinc-500">Reservas confirmadas (Stripe)</div>
                <div className="font-display text-3xl font-semibold text-zinc-50 mt-1">{metrics.total_confirmed_bookings}</div>
              </div>
              <div className="rounded-2xl border border-zinc-900 bg-zinc-950 p-4">
                <div className="text-xs uppercase tracking-wider text-zinc-500">Conversão Stripe / WA</div>
                <div className="font-display text-3xl font-semibold text-red-500 mt-1">
                  {metrics.global_conversion_pct !== null ? `${metrics.global_conversion_pct}%` : "—"}
                </div>
                <div className="text-[11px] text-zinc-500 mt-1">cliques que viraram pagamento</div>
              </div>
            </div>

            <div className="rounded-2xl border border-zinc-900 bg-zinc-950 overflow-hidden">
              <div className="px-4 py-3 border-b border-zinc-900 text-xs uppercase tracking-wider text-zinc-500 grid grid-cols-12 gap-2">
                <div className="col-span-5">Profissional</div>
                <div className="col-span-2 text-right"><MessageCircle className="h-3 w-3 inline" /> Cliques</div>
                <div className="col-span-2 text-right">Únicos</div>
                <div className="col-span-2 text-right">Stripe</div>
                <div className="col-span-1 text-right">%</div>
              </div>
              {metrics.by_massagista.map((row) => (
                <div key={row.massagista_id} data-testid={`metric-row-${row.massagista_id}`} className="px-4 py-3 border-b border-zinc-900 last:border-b-0 grid grid-cols-12 gap-2 items-center hover:bg-zinc-900/40 transition-colors">
                  <div className="col-span-5 flex items-center gap-3 min-w-0">
                    <img src={resolveMediaUrl(row.main_image)} alt="" className="h-9 w-9 rounded-lg object-cover shrink-0" />
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-zinc-100 truncate">{row.name}</div>
                      <div className="text-[11px] text-zinc-500">{row.bairro}</div>
                    </div>
                  </div>
                  <div className="col-span-2 text-right font-display text-lg font-semibold text-zinc-50" data-testid={`metric-clicks-${row.massagista_id}`}>{row.clicks}</div>
                  <div className="col-span-2 text-right text-sm text-zinc-300">{row.unique_users}</div>
                  <div className="col-span-2 text-right text-sm text-zinc-300">{row.confirmed_bookings}</div>
                  <div className="col-span-1 text-right text-sm">
                    {row.conversion_rate_pct !== null ? (
                      <span className={row.conversion_rate_pct >= 30 ? "text-red-400" : row.conversion_rate_pct >= 10 ? "text-amber-300" : "text-zinc-500"}>
                        {row.conversion_rate_pct}%
                      </span>
                    ) : <span className="text-zinc-600">—</span>}
                  </div>
                </div>
              ))}
            </div>
            <p className="text-[11px] text-zinc-500 mt-4">
              Métrica útil para entender quanto da receita potencial pode estar acontecendo via WhatsApp (fora da plataforma).
              Profissionais com muitos cliques e poucas reservas Stripe são candidatas a renegociação de comissão.
            </p>
          </div>
        )
      ) : view === "users" ? (
        usersLoading ? (
          <div className="space-y-3">{[0,1,2].map(i => <div key={i} className="h-16 rounded-2xl bg-zinc-900 animate-pulse" />)}</div>
        ) : (
          <div data-testid="users-panel">
            <div className="text-sm text-zinc-400 mb-5">
              {users.length} {users.length === 1 ? "usuário cadastrado" : "usuários cadastrados"} · {users.filter(u => u.is_admin).length} admin(s)
            </div>
            <div className="rounded-2xl border border-zinc-900 bg-zinc-950 overflow-hidden">
              {users.length === 0 ? (
                <div className="text-center py-16 text-zinc-500">Nenhum usuário cadastrado ainda.</div>
              ) : users.map((u) => (
                <div key={u.user_id} data-testid={`user-row-${u.user_id}`} className="px-4 py-3 border-b border-zinc-900 last:border-b-0 flex items-center gap-3 flex-wrap hover:bg-zinc-900/40 transition-colors">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-zinc-100">{u.name}</span>
                      {u.is_admin && (
                        <Badge className="bg-red-600/15 text-red-300 border border-red-600/40 rounded-full text-[10px]">Admin</Badge>
                      )}
                      {u.user_id === user.user_id && (
                        <span className="text-[10px] text-zinc-600">(você)</span>
                      )}
                    </div>
                    <div className="text-xs text-zinc-500">{u.email}</div>
                    <div className="text-[10px] text-zinc-600 mt-0.5">Desde {new Date(u.created_at).toLocaleDateString("pt-BR")}</div>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    {u.is_admin ? (
                      <Button
                        data-testid={`demote-${u.user_id}`}
                        onClick={() => setUserRole(u, false)}
                        disabled={u.user_id === user.user_id}
                        variant="outline"
                        size="sm"
                        className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900"
                      >
                        Remover admin
                      </Button>
                    ) : (
                      <Button
                        data-testid={`promote-${u.user_id}`}
                        onClick={() => setUserRole(u, true)}
                        variant="outline"
                        size="sm"
                        className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900 hover:text-red-400"
                      >
                        <ShieldPlus className="h-3.5 w-3.5 mr-1" /> Tornar admin
                      </Button>
                    )}
                    <Button
                      data-testid={`delete-user-${u.user_id}`}
                      onClick={() => deleteUser(u)}
                      disabled={u.user_id === user.user_id}
                      variant="outline"
                      size="sm"
                      className="rounded-full border-zinc-700 text-zinc-400 hover:bg-red-600 hover:text-white hover:border-red-600"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )
      ) : view === "bookings" ? (
        bookingsLoading ? (
          <div className="space-y-3">{[0,1,2].map(i => <div key={i} className="h-20 rounded-2xl bg-zinc-900 animate-pulse" />)}</div>
        ) : (
          <div data-testid="bookings-panel">
            <div className="flex items-center justify-between flex-wrap gap-3 mb-5">
              <div className="text-sm text-zinc-400">
                {bookings.length} {bookings.length === 1 ? "reserva" : "reservas"} no total
              </div>
              <Button onClick={() => setManualOpen(true)} data-testid="open-manual-booking" className="rounded-full bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-600/25">
                <Plus className="h-4 w-4 mr-1.5" /> Lançar atendimento
              </Button>
            </div>
            {bookings.length === 0 ? (
              <div className="text-center py-16 text-zinc-500 rounded-2xl bg-zinc-950 border border-zinc-900">
                Nenhuma reserva ainda. Use "Lançar atendimento" para registrar uma sessão paga fora da plataforma.
              </div>
            ) : (
              <div className="rounded-2xl border border-zinc-900 bg-zinc-950 overflow-hidden">
                {bookings.map((b) => {
                  const isManual = !!b.manual_confirmed_by;
                  const statusCls = b.status === "confirmed"
                    ? "bg-red-600/15 text-red-300 border border-red-600/40"
                    : b.status === "pending_payment"
                    ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                    : "bg-zinc-800 text-zinc-400 border border-zinc-800";
                  return (
                    <div key={b.id} data-testid={`booking-row-${b.id}`} className="px-4 py-3 border-b border-zinc-900 last:border-b-0 flex items-center gap-3 flex-wrap hover:bg-zinc-900/40 transition-colors">
                      <img src={resolveMediaUrl(b.massagista_image)} alt="" className="h-12 w-12 rounded-lg object-cover shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-display text-sm font-semibold text-zinc-50">{b.massagista_name}</span>
                          <span className="text-xs text-zinc-500">·</span>
                          <span className="text-xs text-zinc-400">{b.user_email}</span>
                        </div>
                        <div className="text-[11px] text-zinc-500 mt-0.5">
                          {b.date} · {b.time} · {b.duration} min · {b.bairro}
                          {isManual && b.payment_method && <span className="ml-2 text-amber-300">· pago via {b.payment_method.toUpperCase()}</span>}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className={`inline-flex items-center rounded-full text-[11px] px-2 py-0.5 font-medium ${statusCls}`}>
                          {b.status === "confirmed" ? "Confirmada" : b.status === "pending_payment" ? "Pendente" : "Cancelada"}
                        </div>
                        <div className="font-display text-base font-semibold text-zinc-50 mt-1">{brl(b.amount)}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            <p className="text-[11px] text-zinc-500 mt-4">
              Lançar atendimento manual cria uma reserva já confirmada — o cliente verá em "Minhas reservas" e poderá deixar a avaliação.
            </p>
          </div>
        )
      ) : loading ? (
        <div className="space-y-3">{[0,1,2].map(i => <div key={i} className="h-24 rounded-2xl bg-zinc-900 animate-pulse" />)}</div>
      ) : items.length === 0 ? (
        <div className="text-center py-20 text-zinc-500">Nenhuma profissional {view === "queue" ? "na fila de verificação" : "encontrada"}.</div>
      ) : (
        <div className="space-y-3">
          {items.map((m) => (
            <div key={m.id} data-testid={`admin-row-${m.id}`} className="bg-zinc-950 rounded-2xl border border-zinc-900 p-4 flex items-center gap-4 flex-wrap">
              <img src={resolveMediaUrl(m.main_image)} alt={m.name} className="h-16 w-16 rounded-xl object-cover" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-display text-lg font-semibold text-zinc-50">{m.name}</h3>
                  <Pill verified={m.verified} />
                </div>
                <div className="text-xs text-zinc-500 mt-1 flex items-center gap-3">
                  <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3" /> {m.bairro}</span>
                  <span className="inline-flex items-center gap-1"><Star className="h-3 w-3 fill-amber-400 text-amber-400" /> {m.rating?.toFixed(1)} · {m.reviews} avaliações</span>
                </div>
                {m.verification?.verified_by && (
                  <div className="text-[10px] text-zinc-600 mt-1">
                    Última ação por <span className="text-zinc-400">{m.verification.verified_by}</span>
                    {m.verification.verified_at && <> · {new Date(m.verification.verified_at).toLocaleString("pt-BR")}</>}
                  </div>
                )}
              </div>
              <div className="flex gap-2 flex-wrap">
                <Button
                  data-testid={`edit-data-${m.id}`}
                  onClick={() => setEditTarget(m)}
                  variant="outline"
                  className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900 hover:text-red-400"
                >
                  <Pencil className="h-4 w-4 mr-1.5" /> Dados
                </Button>
                <Button
                  data-testid={`edit-media-${m.id}`}
                  onClick={() => setMediaTarget(m)}
                  variant="outline"
                  className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900 hover:text-red-400"
                >
                  <ImageIcon className="h-4 w-4 mr-1.5" /> Mídia
                </Button>
                {!m.verified && (
                  <>
                    <Button data-testid={`approve-${m.id}`} onClick={() => openModeration(m, "approve")} className="rounded-full bg-red-600 hover:bg-red-700 text-white">
                      <ShieldCheck className="h-4 w-4 mr-1.5" /> Aprovar
                    </Button>
                    <Button data-testid={`reject-${m.id}`} onClick={() => openModeration(m, "reject")} variant="outline" className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900">
                      Rejeitar
                    </Button>
                  </>
                )}
                {m.verified && (
                  <Button data-testid={`revoke-${m.id}`} onClick={() => revoke(m)} variant="outline" className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900">
                    Revogar selo
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={!!target} onOpenChange={(v) => !v && setTarget(null)}>        <DialogContent className="bg-zinc-950 border border-zinc-900 text-zinc-100 max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-display text-xl text-zinc-50">
              {action === "approve" ? "Aprovar verificação" : "Rejeitar verificação"}
            </DialogTitle>
            <DialogDescription className="text-zinc-400">
              {target?.name} · {target?.bairro}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 mt-2">
            <div className="text-xs uppercase tracking-wider text-zinc-500 flex items-center justify-between">
              <span>Mídia do perfil</span>
              <span className="normal-case tracking-normal text-zinc-600">
                {target?.gallery?.length || 0} {target?.gallery?.length === 1 ? "foto" : "fotos"} · vídeo {target?.video_url ? "sim" : "não"}
              </span>
            </div>
            <div className="grid grid-cols-4 gap-2">
              {(target?.gallery || []).map((url, i) => {
                const isMain = target.main_image === url;
                return (
                  <div key={i} className="relative rounded-lg border border-zinc-800 bg-black aspect-square overflow-hidden">
                    <img src={resolveMediaUrl(url)} alt={`Foto ${i + 1}`} className="w-full h-full object-cover" />
                    <span className="absolute bottom-1 inset-x-1 text-center text-[8px] uppercase tracking-wider bg-black/70 text-zinc-300 rounded px-1 py-0.5">
                      {isMain ? "Principal" : `Foto ${i + 1}`}
                    </span>
                  </div>
                );
              })}
              {target?.video_url ? (
                <div className="relative rounded-lg border border-zinc-800 bg-black aspect-square overflow-hidden flex items-center justify-center">
                  {(target.video_thumb || target.main_image) && (
                    <img src={resolveMediaUrl(target.video_thumb || target.main_image)} alt="Capa do vídeo" className="w-full h-full object-cover opacity-60" />
                  )}
                  <div className="absolute h-7 w-7 rounded-full bg-black/70 flex items-center justify-center">
                    <Play className="h-3.5 w-3.5 text-white fill-white ml-0.5" />
                  </div>
                  <span className="absolute bottom-1 inset-x-1 text-center text-[8px] uppercase tracking-wider bg-black/70 text-zinc-300 rounded px-1 py-0.5">Vídeo</span>
                </div>
              ) : null}
              {(target?.gallery?.length || 0) === 0 && !target?.video_url && (
                <div className="col-span-4 text-center text-zinc-600 text-xs py-3">Nenhuma foto ou vídeo enviado ainda</div>
              )}
            </div>

            <div className="text-xs uppercase tracking-wider text-zinc-500 pt-2">Documentos enviados pela profissional</div>
            <div className="grid grid-cols-3 gap-3">
              {[
                { kind: "id_document_front", label: "Frente do documento", icon: FileText, testid: "doc-id-document-front" },
                { kind: "id_document_back", label: "Verso do documento", icon: FileText, testid: "doc-id-document-back" },
                { kind: "selfie", label: "Selfie", icon: ScanFace, testid: "doc-selfie" },
              ].map(({ kind, label, icon: Icon, testid }) => (
                <div key={kind}>
                  <div className="relative rounded-xl border border-zinc-800 bg-black aspect-[3/4] flex items-center justify-center overflow-hidden">
                    {docsLoading ? (
                      <Loader2 className="h-5 w-5 animate-spin text-zinc-600" />
                    ) : docs[kind]?.isPdf ? (
                      <a href={docs[kind].url} target="_blank" rel="noreferrer" className="text-center text-red-300 px-2 hover:text-red-200" data-testid={testid}>
                        <FileText className="h-6 w-6 mx-auto mb-1" />
                        <span className="text-[10px] underline">Abrir PDF</span>
                      </a>
                    ) : docs[kind] ? (
                      <img src={docs[kind].url} alt={label} className="w-full h-full object-cover" data-testid={testid} />
                    ) : (
                      <div className="text-center text-zinc-600 px-2">
                        <Icon className="h-5 w-5 mx-auto mb-1" />
                        <span className="text-[10px]">Não enviado{kind === "selfie" ? "a" : ""}</span>
                      </div>
                    )}
                  </div>
                  <div className="text-[10px] text-zinc-500 text-center mt-1">{label}</div>
                </div>
              ))}
            </div>

            <div className="text-xs uppercase tracking-wider text-zinc-500 pt-2">Checagens realizadas</div>
            {[
              { k: "id", label: "Documento de identidade conferido" },
              { k: "photo", label: "Foto recente bate com o perfil" },
              { k: "address", label: "Endereço de atendimento confirmado" },
            ].map((c) => (
              <label key={c.k} className="flex items-center gap-3 rounded-xl border border-zinc-800 bg-black px-3 py-2.5 cursor-pointer">
                <Checkbox
                  data-testid={`check-${c.k}`}
                  checked={checks[c.k]}
                  onCheckedChange={(v) => setChecks((s) => ({ ...s, [c.k]: !!v }))}
                  className="border-zinc-700 data-[state=checked]:bg-red-600 data-[state=checked]:border-red-600"
                />
                <span className="text-sm text-zinc-200">{c.label}</span>
              </label>
            ))}

            <div>
              <Label className="text-xs uppercase tracking-wider text-zinc-500">
                {action === "reject" ? (
                  <>Motivo da rejeição <span className="text-red-500">*</span> — a profissional vai ver isso</>
                ) : "Notas internas (opcional)"}
              </Label>
              <Textarea
                data-testid="moderation-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={action === "reject"
                  ? "Ex: foto do documento ilegível, envie novamente com melhor iluminação..."
                  : "Comentários para o histórico interno..."}
                className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100 placeholder:text-zinc-600 resize-none h-20"
              />
            </div>
          </div>

          {action === "approve" && !docsLoading && !docsComplete() && (
            <p className="text-xs text-amber-300 -mt-2" data-testid="missing-docs-warning">
              Faltam documentos obrigatórios antes de aprovar: documento (frente + verso, ou PDF único) e selfie com o documento.
            </p>
          )}

          <DialogFooter className="mt-4">
            <Button variant="outline" onClick={() => setTarget(null)} className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900">Cancelar</Button>
            <Button
              data-testid="confirm-moderation"
              onClick={submitModeration}
              disabled={submitting
                || (action === "approve" && (docsLoading || !docsComplete()))
                || (action === "reject" && !notes.trim())}
              className={`rounded-full text-white ${action === "approve" ? "bg-red-600 hover:bg-red-700" : "bg-zinc-700 hover:bg-zinc-600"}`}
            >
              {submitting && <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />}
              {action === "approve" ? "Confirmar aprovação" : "Confirmar rejeição"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <MediaEditor
        open={!!mediaTarget}
        massagista={mediaTarget}
        onClose={() => setMediaTarget(null)}
        onUpdated={(updated) => {
          setItems((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
          setMediaTarget(updated);
        }}
      />
      <AdminProfileEditor
        open={!!editTarget}
        massagista={editTarget}
        onClose={() => setEditTarget(null)}
        onUpdated={(updated) => {
          setItems((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
        }}
      />
    </div>
  );
}
