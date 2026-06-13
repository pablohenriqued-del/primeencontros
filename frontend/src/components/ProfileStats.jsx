import { useEffect, useState } from "react";
import { api, brl } from "@/lib/api";
import { Eye, MessageCircle, CalendarCheck, DollarSign, Star, TrendingUp, Clock, ChevronDown, ChevronUp } from "lucide-react";

const STATUS_LABEL = {
  pending_payment: "Pgto. pendente",
  confirmed: "Confirmada",
  completed: "Concluída",
  cancelled: "Cancelada",
};

const STATUS_BADGE = {
  pending_payment: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  confirmed: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  completed: "bg-red-600/15 text-red-300 border-red-600/40",
  cancelled: "bg-zinc-700/20 text-zinc-400 border-zinc-700",
};

function Card({ icon: Icon, label, value, sub, testid }) {
  return (
    <div
      data-testid={testid}
      className="rounded-2xl border border-zinc-900 bg-zinc-950 p-4 sm:p-5 hover:border-red-600/40 transition-colors"
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] uppercase tracking-[0.18em] text-zinc-500 font-semibold">{label}</span>
        <Icon className="h-4 w-4 text-red-500" />
      </div>
      <div className="font-display text-2xl sm:text-3xl text-zinc-50 font-semibold">{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}

export default function ProfileStats() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api.get("/me/stats")
      .then(({ data }) => { if (!cancelled) setStats(data); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="rounded-2xl border border-zinc-900 bg-zinc-950 p-6 text-zinc-500 text-sm">
        Carregando estatísticas...
      </div>
    );
  }
  if (!stats) return null;

  const { views, whatsapp_clicks, bookings, revenue, rating, conversion_rate_pct, recent_bookings } = stats;

  return (
    <section data-testid="profile-stats" className="space-y-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        data-testid="stats-toggle"
        className="w-full flex items-center justify-between rounded-2xl border border-zinc-900 bg-black px-5 py-3 hover:border-red-600/40 transition-colors"
      >
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-red-500" />
          <span className="font-display text-lg text-zinc-50">Painel de desempenho</span>
          <span className="text-xs text-zinc-500 hidden sm:inline">· últimos 30 dias entre parênteses</span>
        </div>
        {open ? <ChevronUp className="h-4 w-4 text-zinc-400" /> : <ChevronDown className="h-4 w-4 text-zinc-400" />}
      </button>

      {open && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <Card
              icon={Eye}
              label="Visitas ao perfil"
              value={views.total}
              sub={`${views.last_30d} nos últimos 30d`}
              testid="stat-views"
            />
            <Card
              icon={MessageCircle}
              label="Cliques WhatsApp"
              value={whatsapp_clicks.total}
              sub={`${whatsapp_clicks.last_30d} nos últimos 30d`}
              testid="stat-whatsapp"
            />
            <Card
              icon={CalendarCheck}
              label="Reservas confirmadas"
              value={bookings.confirmed + bookings.completed}
              sub={`${bookings.pending_payment} pendentes · ${bookings.cancelled} canc.`}
              testid="stat-bookings"
            />
            <Card
              icon={DollarSign}
              label="Faturamento"
              value={brl(revenue.confirmed || 0)}
              sub="Total de reservas confirmadas"
              testid="stat-revenue"
            />
            <Card
              icon={Star}
              label="Avaliação"
              value={rating.count > 0 ? rating.average.toFixed(1) : "—"}
              sub={`${rating.count} avaliações públicas`}
              testid="stat-rating"
            />
          </div>

          {conversion_rate_pct !== null && conversion_rate_pct !== undefined && (
            <div className="rounded-2xl border border-zinc-900 bg-zinc-950 p-4 flex items-center gap-3" data-testid="stat-conversion">
              <div className="h-9 w-9 rounded-full bg-red-600/15 border border-red-600/40 flex items-center justify-center">
                <TrendingUp className="h-4 w-4 text-red-400" />
              </div>
              <div className="flex-1">
                <div className="text-xs uppercase tracking-wider text-zinc-500">Taxa de conversão (visita → reserva)</div>
                <div className="font-display text-xl text-zinc-50">{conversion_rate_pct}%</div>
              </div>
              <div className="text-xs text-zinc-500 max-w-[180px] text-right hidden sm:block">
                Boas fotos e bio detalhada elevam essa taxa rapidamente.
              </div>
            </div>
          )}

          {recent_bookings && recent_bookings.length > 0 && (
            <div className="rounded-2xl border border-zinc-900 bg-zinc-950 overflow-hidden">
              <div className="px-5 py-3 border-b border-zinc-900 flex items-center gap-2">
                <Clock className="h-4 w-4 text-zinc-500" />
                <span className="text-xs uppercase tracking-wider text-zinc-400 font-semibold">Últimas reservas</span>
              </div>
              <div className="divide-y divide-zinc-900">
                {recent_bookings.map((b) => (
                  <div key={b.id} data-testid={`recent-booking-${b.id}`} className="flex items-center gap-3 px-5 py-3">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-zinc-200 font-medium truncate">{b.user_email}</div>
                      <div className="text-xs text-zinc-500">
                        {b.date} · {b.time} · {b.duration} min
                      </div>
                    </div>
                    <div className="text-sm font-semibold text-zinc-100 whitespace-nowrap">{brl(b.amount)}</div>
                    <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full border ${STATUS_BADGE[b.status] || "border-zinc-700 text-zinc-400"}`}>
                      {STATUS_LABEL[b.status] || b.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
