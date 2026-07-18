import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, brl, resolveMediaUrl } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Calendar, MapPin, Clock, Home, Star } from "lucide-react";
import { toast } from "sonner";
import ReviewDialog from "@/components/ReviewDialog";

const STATUS = {
  pending_payment: { label: "Aguardando pagamento", cls: "bg-amber-500/15 text-amber-300 border border-amber-500/30" },
  confirmed: { label: "Confirmada", cls: "bg-red-600/15 text-red-300 border border-red-600/40" },
  cancelled: { label: "Cancelada", cls: "bg-zinc-800 text-zinc-400 border border-zinc-800" },
};

export default function MyBookings() {
  const { user, loading: authLoading, login } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reviewedIds, setReviewedIds] = useState(new Set());
  const [target, setTarget] = useState(null);
  const navigate = useNavigate();

  const fetchData = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/bookings/me");
      setItems(data);
      // For each confirmed booking, check if user already left a review (one per booking by user)
      const confirmed = data.filter(b => b.status === "confirmed");
      const reviewed = new Set();
      await Promise.all(confirmed.map(async (b) => {
        try {
          const { data: rs } = await api.get(`/massagistas/${b.massagista_id}/reviews`);
          if (rs.some(r => r.booking_id === b.id)) reviewed.add(b.id);
        } catch {}
      }));
      setReviewedIds(reviewed);
    } catch {
      toast.error("Erro ao carregar suas reservas");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (authLoading) return;
    if (!user) { setLoading(false); return; }
    fetchData();
    /* eslint-disable-next-line */
  }, [authLoading, user]);

  if (authLoading) return <div className="max-w-7xl mx-auto px-4 py-20 text-zinc-500">Carregando...</div>;

  if (!user) {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h2 className="font-display text-2xl font-medium text-zinc-50">Suas reservas</h2>
        <p className="text-zinc-400 mt-2 mb-6">Faça login para ver suas reservas e histórico de atendimentos.</p>
        <Button onClick={login} className="rounded-full bg-red-600 hover:bg-red-700 text-white px-6 h-11 shadow-lg shadow-red-600/25" data-testid="login-from-bookings">
          Entrar com Google
        </Button>
      </div>
    );
  }

  return (
    <div data-testid="bookings-page" className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <h1 className="font-display text-3xl sm:text-4xl font-medium tracking-tight text-zinc-50">Minhas reservas</h1>
      <p className="text-zinc-400 mt-1">Olá, {user.name?.split(" ")[0]} — aqui estão seus agendamentos.</p>

      {loading ? (
        <div className="mt-10 space-y-4">{[0,1,2].map(i => <div key={i} className="h-28 rounded-2xl bg-zinc-900 animate-pulse" />)}</div>
      ) : items.length === 0 ? (
        <div className="mt-12 bg-zinc-950 rounded-2xl border border-zinc-900 p-10 text-center">
          <p className="text-zinc-400">Você ainda não tem reservas.</p>
          <Button onClick={() => navigate("/")} className="mt-5 rounded-full bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-600/25">
            Encontrar uma profissional
          </Button>
        </div>
      ) : (
        <div className="mt-8 space-y-4">
          {items.map((b) => {
            const s = STATUS[b.status] || STATUS.pending_payment;
            return (
              <div key={b.id} data-testid={`booking-${b.id}`} className="bg-zinc-950 rounded-2xl border border-zinc-900 p-4 sm:p-5 flex flex-col sm:flex-row items-start gap-4 hover:border-red-600/30 transition-colors">
                <Link to={`/massagista/${b.massagista_id}`} className="shrink-0">
                  <img src={resolveMediaUrl(b.massagista_image)} alt={b.massagista_name} className="h-20 w-20 sm:h-24 sm:w-24 rounded-xl object-cover" />
                </Link>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div>
                      <h3 className="font-display text-lg font-semibold text-zinc-50">{b.massagista_name}</h3>
                      <div className="text-xs text-zinc-500 flex items-center gap-1 mt-0.5">
                        <MapPin className="h-3 w-3" /> {b.bairro}
                      </div>
                    </div>
                    <Badge className={`rounded-full ${s.cls}`}>{s.label}</Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm text-zinc-300">
                    <span className="inline-flex items-center gap-1.5"><Calendar className="h-4 w-4 text-zinc-500" /> {b.date}</span>
                    <span className="inline-flex items-center gap-1.5"><Clock className="h-4 w-4 text-zinc-500" /> {b.time} · {b.duration} min</span>
                    <span className="inline-flex items-center gap-1.5"><Home className="h-4 w-4 text-zinc-500" /> {b.location_type === "studio" ? "No estúdio" : "Em domicílio"}</span>
                  </div>
                </div>
                <div className="text-right sm:ml-auto flex flex-col items-end gap-2">
                  <div>
                    <div className="text-xs text-zinc-500">Total</div>
                    <div className="font-display text-xl font-semibold text-red-500">{brl(b.amount)}</div>
                  </div>
                  {b.status === "confirmed" && !reviewedIds.has(b.id) && (
                    <Button
                      size="sm"
                      data-testid={`review-${b.id}`}
                      onClick={() => setTarget(b)}
                      className="rounded-full bg-red-600 hover:bg-red-700 text-white text-xs h-8"
                    >
                      <Star className="h-3.5 w-3.5 mr-1" /> Avaliar
                    </Button>
                  )}
                  {b.status === "confirmed" && reviewedIds.has(b.id) && (
                    <span className="text-[11px] text-zinc-500 inline-flex items-center gap-1">
                      <Star className="h-3 w-3 fill-amber-400 text-amber-400" /> Avaliada
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
      <ReviewDialog
        open={!!target}
        booking={target}
        onClose={() => setTarget(null)}
        onSubmitted={() => fetchData()}
      />
    </div>
  );
}
