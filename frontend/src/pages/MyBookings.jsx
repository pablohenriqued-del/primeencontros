import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, brl } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Calendar, MapPin, Clock, Home } from "lucide-react";
import { toast } from "sonner";

const STATUS = {
  pending_payment: { label: "Aguardando pagamento", cls: "bg-amber-100 text-amber-800" },
  confirmed: { label: "Confirmada", cls: "bg-emerald-100 text-emerald-800" },
  cancelled: { label: "Cancelada", cls: "bg-stone-200 text-stone-700" },
};

export default function MyBookings() {
  const { user, loading: authLoading, login } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    if (authLoading) return;
    if (!user) { setLoading(false); return; }
    api.get("/bookings/me")
      .then(({ data }) => setItems(data))
      .catch(() => toast.error("Erro ao carregar suas reservas"))
      .finally(() => setLoading(false));
  }, [authLoading, user]);

  if (authLoading) return <div className="max-w-7xl mx-auto px-4 py-20 text-stone-500">Carregando...</div>;

  if (!user) {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h2 className="font-display text-2xl font-medium text-stone-900">Suas reservas</h2>
        <p className="text-stone-500 mt-2 mb-6">Faça login para ver suas reservas e histórico de atendimentos.</p>
        <Button onClick={login} className="rounded-full bg-stone-900 hover:bg-stone-800 text-white px-6 h-11" data-testid="login-from-bookings">
          Entrar com Google
        </Button>
      </div>
    );
  }

  return (
    <div data-testid="bookings-page" className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <h1 className="font-display text-3xl sm:text-4xl font-medium tracking-tight text-stone-900">Minhas reservas</h1>
      <p className="text-stone-500 mt-1">Olá, {user.name?.split(" ")[0]} — aqui estão seus agendamentos.</p>

      {loading ? (
        <div className="mt-10 space-y-4">{[0,1,2].map(i => <div key={i} className="h-28 rounded-2xl bg-stone-100 animate-pulse" />)}</div>
      ) : items.length === 0 ? (
        <div className="mt-12 bg-white rounded-2xl border border-stone-100 p-10 text-center">
          <p className="text-stone-600">Você ainda não tem reservas.</p>
          <Button onClick={() => navigate("/")} className="mt-5 rounded-full bg-emerald-800 hover:bg-emerald-900 text-white">
            Encontrar uma profissional
          </Button>
        </div>
      ) : (
        <div className="mt-8 space-y-4">
          {items.map((b) => {
            const s = STATUS[b.status] || STATUS.pending_payment;
            return (
              <div key={b.id} data-testid={`booking-${b.id}`} className="bg-white rounded-2xl border border-stone-100 p-4 sm:p-5 flex flex-col sm:flex-row items-start gap-4">
                <Link to={`/massagista/${b.massagista_id}`} className="shrink-0">
                  <img src={b.massagista_image} alt={b.massagista_name} className="h-20 w-20 sm:h-24 sm:w-24 rounded-xl object-cover" />
                </Link>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div>
                      <h3 className="font-display text-lg font-semibold text-stone-900">{b.massagista_name}</h3>
                      <div className="text-xs text-stone-500 flex items-center gap-1 mt-0.5">
                        <MapPin className="h-3 w-3" /> {b.bairro}
                      </div>
                    </div>
                    <Badge className={`rounded-full ${s.cls} border-0`}>{s.label}</Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm text-stone-700">
                    <span className="inline-flex items-center gap-1.5"><Calendar className="h-4 w-4 text-stone-400" /> {b.date}</span>
                    <span className="inline-flex items-center gap-1.5"><Clock className="h-4 w-4 text-stone-400" /> {b.time} · {b.duration} min</span>
                    <span className="inline-flex items-center gap-1.5"><Home className="h-4 w-4 text-stone-400" /> {b.location_type === "studio" ? "No estúdio" : "Em domicílio"}</span>
                  </div>
                </div>
                <div className="text-right sm:ml-auto">
                  <div className="text-xs text-stone-500">Total</div>
                  <div className="font-display text-xl font-semibold text-emerald-800">{brl(b.amount)}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
