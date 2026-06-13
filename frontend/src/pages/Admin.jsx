import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, brl } from "@/lib/api";
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
import { ShieldCheck, ShieldAlert, ShieldX, MapPin, Star, Loader2 } from "lucide-react";
import { toast } from "sonner";

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
  const [view, setView] = useState("queue"); // queue | all
  const [target, setTarget] = useState(null); // currently moderating
  const [action, setAction] = useState("approve"); // approve | reject
  const [checks, setChecks] = useState({ id: true, photo: true, address: true });
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

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

  useEffect(() => {
    if (authLoading) return;
    if (!user) { setLoading(false); return; }
    fetchList();
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

  const openModeration = (m, act) => {
    setTarget(m);
    setAction(act);
    setChecks({ id: true, photo: true, address: true });
    setNotes("");
  };

  const submitModeration = async () => {
    if (!target) return;
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
    } catch {
      toast.error("Não foi possível concluir a moderação");
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
          </TabsList>
        </Tabs>
      </div>

      {loading ? (
        <div className="space-y-3">{[0,1,2].map(i => <div key={i} className="h-24 rounded-2xl bg-zinc-900 animate-pulse" />)}</div>
      ) : items.length === 0 ? (
        <div className="text-center py-20 text-zinc-500">Nenhuma profissional {view === "queue" ? "na fila de verificação" : "encontrada"}.</div>
      ) : (
        <div className="space-y-3">
          {items.map((m) => (
            <div key={m.id} data-testid={`admin-row-${m.id}`} className="bg-zinc-950 rounded-2xl border border-zinc-900 p-4 flex items-center gap-4 flex-wrap">
              <img src={m.main_image} alt={m.name} className="h-16 w-16 rounded-xl object-cover" />
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
              <div className="flex gap-2">
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

      <Dialog open={!!target} onOpenChange={(v) => !v && setTarget(null)}>
        <DialogContent className="bg-zinc-950 border border-zinc-900 text-zinc-100 max-w-md">
          <DialogHeader>
            <DialogTitle className="font-display text-xl text-zinc-50">
              {action === "approve" ? "Aprovar verificação" : "Rejeitar verificação"}
            </DialogTitle>
            <DialogDescription className="text-zinc-400">
              {target?.name} · {target?.bairro}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 mt-2">
            <div className="text-xs uppercase tracking-wider text-zinc-500">Checagens realizadas</div>
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
              <Label className="text-xs uppercase tracking-wider text-zinc-500">Notas internas (opcional)</Label>
              <Textarea
                data-testid="moderation-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Comentários para o histórico interno..."
                className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100 placeholder:text-zinc-600 resize-none h-20"
              />
            </div>
          </div>

          <DialogFooter className="mt-4">
            <Button variant="outline" onClick={() => setTarget(null)} className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900">Cancelar</Button>
            <Button
              data-testid="confirm-moderation"
              onClick={submitModeration}
              disabled={submitting}
              className={`rounded-full text-white ${action === "approve" ? "bg-red-600 hover:bg-red-700" : "bg-zinc-700 hover:bg-zinc-600"}`}
            >
              {submitting && <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />}
              {action === "approve" ? "Confirmar aprovação" : "Confirmar rejeição"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
