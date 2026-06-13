import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api, brl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Calendar } from "@/components/ui/calendar";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Star, MapPin, Clock, ChevronLeft, Play, Languages, Award, Sparkles, ShieldCheck, ShieldAlert, MessageCircle } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

const TIME_SLOTS = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00"];

export default function Detail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user, login } = useAuth();
  const [m, setM] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [videoOpen, setVideoOpen] = useState(false);
  const [bookingOpen, setBookingOpen] = useState(false);

  const [duration, setDuration] = useState(60);
  const [date, setDate] = useState();
  const [time, setTime] = useState("");
  const [locationType, setLocationType] = useState("studio");
  const [address, setAddress] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.get(`/massagistas/${id}`).then(({ data }) => setM(data)).catch(() => {
      toast.error("Profissional não encontrada");
      navigate("/");
    }).finally(() => setLoading(false));
    api.get(`/massagistas/${id}/reviews`).then(({ data }) => setReviews(data)).catch(() => {});
  }, [id, navigate]);

  if (loading || !m) {
    return <div className="max-w-7xl mx-auto px-4 py-20 text-zinc-500">Carregando...</div>;
  }

  const priceFor = (d) => d === 60 ? m.price_60 : d === 90 ? m.price_90 : m.price_120;

  // WhatsApp helpers
  const hasWhatsApp = !!(m.ddd && m.phone);
  const waNumber = hasWhatsApp ? `55${m.ddd}${m.phone}` : null;
  const waMessage = hasWhatsApp
    ? encodeURIComponent(`Olá ${m.name}, te encontrei na Prime Encontros e gostaria de tirar uma dúvida sobre o atendimento.`)
    : "";
  const waUrl = hasWhatsApp ? `https://wa.me/${waNumber}?text=${waMessage}` : null;

  const trackWhatsAppClick = (source) => {
    // fire-and-forget — never blocks the redirect
    try {
      api.post("/whatsapp/click", { massagista_id: m.id, source }).catch(() => {});
    } catch {}
  };

  const startBooking = () => {
    if (!user) { toast.info("Faça login para reservar"); login(); return; }
    setBookingOpen(true);
  };

  const confirmAndPay = async () => {
    if (!date || !time) { toast.error("Selecione data e horário"); return; }
    if (locationType === "home" && !address.trim()) { toast.error("Informe o endereço"); return; }
    setSubmitting(true);
    try {
      const dateStr = date.toISOString().slice(0, 10);
      const { data: booking } = await api.post("/bookings", {
        massagista_id: m.id,
        date: dateStr,
        time,
        duration,
        location_type: locationType,
        address: locationType === "home" ? address : null,
        notes: notes || null,
      });
      const { data: checkout } = await api.post("/checkout/session", {
        booking_id: booking.id,
        origin_url: window.location.origin,
      });
      window.location.href = checkout.url;
    } catch (e) {
      const msg = e?.response?.data?.detail || "Não foi possível iniciar o pagamento";
      toast.error(msg);
      setSubmitting(false);
    }
  };

  return (
    <div data-testid="detail-page" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <Link to="/" className="inline-flex items-center text-sm text-zinc-400 hover:text-red-500 mb-6 transition-colors">
        <ChevronLeft className="h-4 w-4 mr-1" /> Voltar
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: gallery + bio */}
        <div className="lg:col-span-8 space-y-8">
          {/* Bento gallery */}
          <div className="grid grid-cols-4 grid-rows-2 gap-3 h-[320px] sm:h-[460px]">
            <div className="col-span-4 sm:col-span-2 row-span-2 relative rounded-2xl overflow-hidden bg-zinc-900">
              <img src={m.gallery[0]} alt={m.name} className="w-full h-full object-cover" />
            </div>
            <div className="hidden sm:block col-span-1 row-span-1 rounded-2xl overflow-hidden bg-zinc-900">
              <img src={m.gallery[1]} alt="" className="w-full h-full object-cover" />
            </div>
            <div
              data-testid="open-video-button"
              onClick={() => setVideoOpen(true)}
              className="hidden sm:block col-span-1 row-span-1 rounded-2xl overflow-hidden bg-zinc-900 relative cursor-pointer group ring-1 ring-red-600/0 hover:ring-red-600/60 transition-all"
            >
              <img src={m.video_thumb} alt="" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500 opacity-90" />
              <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                <div className="h-14 w-14 rounded-full bg-red-600 flex items-center justify-center shadow-[0_0_30px_rgba(220,38,38,0.6)] group-hover:scale-110 transition-transform">
                  <Play className="h-6 w-6 text-white ml-0.5" />
                </div>
              </div>
              <div className="absolute bottom-2 right-2 text-[10px] uppercase tracking-wider text-white font-semibold bg-red-600 px-2 py-0.5 rounded-full">Vídeo</div>
            </div>
            <div className="hidden sm:block col-span-1 row-span-1 rounded-2xl overflow-hidden bg-zinc-900">
              <img src={m.gallery[2]} alt="" className="w-full h-full object-cover" />
            </div>
            <div className="hidden sm:block col-span-1 row-span-1 rounded-2xl overflow-hidden bg-zinc-900">
              <img src={m.gallery[3]} alt="" className="w-full h-full object-cover" />
            </div>
          </div>

          {/* Header info */}
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-3">
              {m.verified ? (
                <Badge data-testid="verified-badge" className="bg-red-600 text-white hover:bg-red-700 rounded-full border-0 shadow-[0_0_12px_rgba(220,38,38,0.6)]">
                  <ShieldCheck className="h-3 w-3 mr-1" /> Verificada
                </Badge>
              ) : (
                <Badge className="bg-amber-500/10 text-amber-300 border border-amber-500/30 rounded-full">
                  <ShieldAlert className="h-3 w-3 mr-1" /> Não verificada
                </Badge>
              )}
              <Badge className="bg-red-600/15 text-red-400 hover:bg-red-600/20 border border-red-600/40 rounded-full">
                <MapPin className="h-3 w-3 mr-1" /> {m.bairro}
              </Badge>
              <Badge className="bg-zinc-900 text-zinc-300 hover:bg-zinc-900 rounded-full border border-zinc-800">
                <Award className="h-3 w-3 mr-1" /> {m.experience_years} anos de experiência
              </Badge>
              <Badge className="bg-zinc-900 text-zinc-300 hover:bg-zinc-900 rounded-full border border-zinc-800">
                <Languages className="h-3 w-3 mr-1" /> {m.languages.join(", ")}
              </Badge>
            </div>
            <h1 className="font-display text-3xl sm:text-4xl font-medium tracking-tight text-zinc-50">{m.name}</h1>
            <div className="flex items-center gap-3 mt-2 text-zinc-300">
              <div className="flex items-center gap-1">
                <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
                <span className="font-medium">{m.rating.toFixed(1)}</span>
                <span className="text-zinc-500 text-sm">({m.reviews} avaliações)</span>
              </div>
            </div>
          </div>

          <Tabs defaultValue="sobre" className="w-full">
            <TabsList className="bg-zinc-950 border border-zinc-900 rounded-full p-1">
              <TabsTrigger value="sobre" className="rounded-full data-[state=active]:bg-red-600 data-[state=active]:text-white text-zinc-400" data-testid="tab-sobre">Sobre</TabsTrigger>
              <TabsTrigger value="especialidades" className="rounded-full data-[state=active]:bg-red-600 data-[state=active]:text-white text-zinc-400" data-testid="tab-specs">Especialidades</TabsTrigger>
              <TabsTrigger value="avaliacoes" className="rounded-full data-[state=active]:bg-red-600 data-[state=active]:text-white text-zinc-400" data-testid="tab-reviews">Avaliações</TabsTrigger>
              <TabsTrigger value="verificacao" className="rounded-full data-[state=active]:bg-red-600 data-[state=active]:text-white text-zinc-400" data-testid="tab-verification">Verificação</TabsTrigger>
            </TabsList>
            <TabsContent value="sobre" className="mt-6 text-zinc-300 leading-relaxed">
              <p>{m.bio}</p>
            </TabsContent>
            <TabsContent value="especialidades" className="mt-6">
              <div className="flex flex-wrap gap-2">
                {m.specialties.map((s) => (
                  <span key={s} className="inline-flex items-center rounded-full bg-red-600/10 text-red-300 border border-red-600/30 px-3 py-1.5 text-sm">
                    <Sparkles className="h-3.5 w-3.5 mr-1.5" /> {s}
                  </span>
                ))}
              </div>
            </TabsContent>
            <TabsContent value="avaliacoes" className="mt-6">
              {reviews.length === 0 ? (
                <div className="text-sm text-zinc-400">
                  {m.reviews > 0
                    ? `${m.reviews} avaliações com média de ${m.rating.toFixed(1)} estrelas. Atendimento pontual, profissional e acolhedor — segundo nossos clientes verificados.`
                    : "Ainda sem avaliações públicas. Seja o primeiro!"}
                </div>
              ) : (
                <div className="space-y-3">
                  {reviews.map((r) => (
                    <div key={r.id} data-testid={`review-${r.id}`} className="rounded-2xl border border-zinc-900 bg-zinc-950 p-4">
                      <div className="flex items-center gap-3">
                        {r.user_picture ? (
                          <img src={r.user_picture} alt="" className="h-9 w-9 rounded-full object-cover" />
                        ) : (
                          <div className="h-9 w-9 rounded-full bg-zinc-800 text-zinc-300 flex items-center justify-center text-sm font-semibold">
                            {(r.user_name || "?")[0]}
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="text-sm text-zinc-200 font-medium">{r.user_name}</div>
                          <div className="text-[11px] text-zinc-500">{new Date(r.created_at).toLocaleDateString("pt-BR")}</div>
                        </div>
                        <div className="flex items-center gap-0.5">
                          {[1,2,3,4,5].map(n => (
                            <Star key={n} className={`h-3.5 w-3.5 ${n <= r.rating ? "fill-amber-400 text-amber-400" : "text-zinc-700"}`} />
                          ))}
                        </div>
                      </div>
                      {r.comment && <p className="text-sm text-zinc-300 mt-3 leading-relaxed">{r.comment}</p>}
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>
            <TabsContent value="verificacao" className="mt-6">
              <div className="rounded-2xl border border-zinc-900 bg-zinc-950 p-5">
                <div className="flex items-center gap-3 mb-4">
                  {m.verified ? (
                    <>
                      <div className="h-10 w-10 rounded-full bg-red-600 flex items-center justify-center shadow-[0_0_20px_rgba(220,38,38,0.5)]">
                        <ShieldCheck className="h-5 w-5 text-white" />
                      </div>
                      <div>
                        <div className="font-display text-lg font-semibold text-zinc-50">Profissional verificada</div>
                        <div className="text-xs text-zinc-500">
                          {m.verification?.verified_at && (
                            <>Verificada em {new Date(m.verification.verified_at).toLocaleDateString("pt-BR")}</>
                          )}
                        </div>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="h-10 w-10 rounded-full bg-amber-500/20 flex items-center justify-center">
                        <ShieldAlert className="h-5 w-5 text-amber-400" />
                      </div>
                      <div>
                        <div className="font-display text-lg font-semibold text-zinc-50">Verificação pendente</div>
                        <div className="text-xs text-zinc-500">A profissional ainda passará pela checagem oficial.</div>
                      </div>
                    </>
                  )}
                </div>
                <div className="space-y-2">
                  {[
                    { k: "id_check", label: "Documento de identidade conferido" },
                    { k: "photo_check", label: "Foto recente bate com o perfil" },
                    { k: "address_check", label: "Endereço de atendimento confirmado" },
                  ].map((c) => {
                    const ok = !!m.verification?.[c.k];
                    return (
                      <div key={c.k} className="flex items-center gap-3 rounded-xl border border-zinc-900 bg-black px-3 py-2.5">
                        {ok ? (
                          <ShieldCheck className="h-4 w-4 text-red-500 shrink-0" />
                        ) : (
                          <ShieldAlert className="h-4 w-4 text-zinc-600 shrink-0" />
                        )}
                        <span className={`text-sm ${ok ? "text-zinc-200" : "text-zinc-500"}`}>{c.label}</span>
                      </div>
                    );
                  })}
                </div>
                <p className="text-xs text-zinc-500 mt-4 leading-relaxed">
                  O selo de verificação é concedido após checagem manual da equipe Prime Encontros. Profissionais verificadas têm prioridade nos resultados e badge especial no perfil.
                </p>
              </div>
            </TabsContent>
          </Tabs>
        </div>

        {/* Right: booking widget */}
        <aside className="lg:col-span-4">
          <div className="lg:sticky lg:top-24 bg-zinc-950 rounded-2xl border border-zinc-900 shadow-2xl shadow-red-950/20 p-6">
            <p className="text-xs uppercase tracking-[0.22em] text-red-500 font-bold mb-2">Reservar agora</p>
            <div className="flex items-baseline gap-2 mb-6">
              <span className="font-display text-3xl font-semibold text-zinc-50">{brl(priceFor(duration))}</span>
              <span className="text-zinc-500 text-sm">/ {duration} min</span>
            </div>

            <div className="space-y-2 mb-5">
              {[60, 90, 120].map((d) => (
                <button
                  key={d}
                  data-testid={`duration-${d}`}
                  onClick={() => setDuration(d)}
                  className={`w-full flex items-center justify-between rounded-xl px-4 py-3 border transition-all text-left
                    ${duration === d
                      ? "border-red-600 bg-red-600/10 shadow-inner"
                      : "border-zinc-800 hover:border-zinc-700 bg-black"}`}
                >
                  <span className="flex items-center text-sm font-medium text-zinc-200">
                    <Clock className="h-4 w-4 mr-2 text-zinc-500" /> {d} minutos
                  </span>
                  <span className="font-semibold text-zinc-50">{brl(priceFor(d))}</span>
                </button>
              ))}
            </div>

            <Button
              data-testid="open-booking-button"
              onClick={startBooking}
              className="w-full h-12 rounded-xl bg-red-600 hover:bg-red-700 text-white text-base font-medium shadow-lg shadow-red-600/25"
            >
              Continuar para agendamento
            </Button>
            {hasWhatsApp && (
              <a
                href={waUrl}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => trackWhatsAppClick("detail")}
                data-testid="whatsapp-button"
                className="mt-2 w-full h-12 rounded-xl inline-flex items-center justify-center gap-2 bg-[#25D366] hover:bg-[#1ebd5a] text-white text-base font-medium shadow-lg shadow-[#25D366]/25 transition-colors"
              >
                <MessageCircle className="h-5 w-5" />
                Falar no WhatsApp
              </a>
            )}
            <p className="text-xs text-zinc-500 text-center mt-3">
              Pagamento seguro via Stripe · Confirmação imediata
            </p>
          </div>
        </aside>
      </div>

      {/* Video dialog */}
      <Dialog open={videoOpen} onOpenChange={setVideoOpen}>
        <DialogContent className="max-w-3xl p-0 overflow-hidden bg-black border border-zinc-900">
          <DialogHeader className="sr-only">
            <DialogTitle>Vídeo de {m.name}</DialogTitle>
          </DialogHeader>
          <video src={m.video_url} controls autoPlay className="w-full h-auto" data-testid="profile-video" />
        </DialogContent>
      </Dialog>

      {/* Booking dialog */}
      <Dialog open={bookingOpen} onOpenChange={setBookingOpen}>
        <DialogContent className="max-w-2xl bg-zinc-950 border border-zinc-900 text-zinc-100">
          <DialogHeader>
            <DialogTitle className="font-display text-2xl text-zinc-50">Agendar com {m.name}</DialogTitle>
            <DialogDescription className="text-zinc-400">{duration} min · {brl(priceFor(duration))} · {m.bairro}</DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-2">
            <div>
              <Label className="text-xs uppercase tracking-wider text-zinc-500">Data</Label>
              <div className="mt-2 rounded-xl border border-zinc-800 bg-black flex justify-center" data-testid="booking-calendar">
                <Calendar
                  mode="single"
                  selected={date}
                  onSelect={setDate}
                  disabled={(d) => d < new Date(new Date().setHours(0, 0, 0, 0))}
                  className="text-zinc-200"
                  classNames={{
                    day_selected: "bg-red-600 text-white hover:bg-red-700 focus:bg-red-700",
                    day_today: "bg-zinc-800 text-red-400",
                    head_cell: "text-zinc-500 rounded-md w-8 font-normal text-[0.8rem]",
                  }}
                />
              </div>
            </div>
            <div className="space-y-5">
              <div>
                <Label className="text-xs uppercase tracking-wider text-zinc-500">Horário</Label>
                <div className="mt-2 grid grid-cols-3 gap-2">
                  {TIME_SLOTS.map((t) => (
                    <button
                      key={t}
                      data-testid={`slot-${t}`}
                      onClick={() => setTime(t)}
                      className={`rounded-lg py-2 text-sm font-medium border transition-colors
                        ${time === t
                          ? "bg-red-600 border-red-600 text-white"
                          : "border-zinc-800 text-zinc-300 hover:border-zinc-700 bg-black"}`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider text-zinc-500">Local</Label>
                <RadioGroup value={locationType} onValueChange={setLocationType} className="mt-2 space-y-2">
                  <div className="flex items-center gap-2 rounded-xl border border-zinc-800 bg-black p-3">
                    <RadioGroupItem value="studio" id="loc-studio" data-testid="loc-studio" className="border-zinc-700 text-red-500" />
                    <Label htmlFor="loc-studio" className="flex-1 cursor-pointer">
                      <div className="text-sm font-medium text-zinc-100">No estúdio</div>
                      <div className="text-xs text-zinc-500">{m.bairro} · Rio de Janeiro</div>
                    </Label>
                  </div>
                  <div className="flex items-center gap-2 rounded-xl border border-zinc-800 bg-black p-3">
                    <RadioGroupItem value="home" id="loc-home" data-testid="loc-home" className="border-zinc-700 text-red-500" />
                    <Label htmlFor="loc-home" className="flex-1 cursor-pointer">
                      <div className="text-sm font-medium text-zinc-100">Em domicílio</div>
                      <div className="text-xs text-zinc-500">Atendimento no seu endereço</div>
                    </Label>
                  </div>
                </RadioGroup>
                {locationType === "home" && (
                  <Input
                    data-testid="booking-address"
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    placeholder="Rua, número, bairro..."
                    className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100 placeholder:text-zinc-600"
                  />
                )}
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider text-zinc-500">Observações (opcional)</Label>
                <Textarea
                  data-testid="booking-notes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Preferências, alergias, dores..."
                  className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100 placeholder:text-zinc-600 resize-none h-20"
                />
              </div>
            </div>
          </div>

          <DialogFooter className="mt-6">
            <div className="w-full flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="text-sm text-zinc-300">
                Total: <span className="font-display text-xl font-semibold text-red-500 ml-1">{brl(priceFor(duration))}</span>
              </div>
              <div className="flex items-center gap-2 flex-wrap justify-end">
                {hasWhatsApp && (
                  <a
                    href={waUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={() => trackWhatsAppClick("modal")}
                    data-testid="whatsapp-button-modal"
                    className="rounded-xl bg-[#25D366] hover:bg-[#1ebd5a] text-white px-4 h-11 inline-flex items-center gap-2 text-sm font-medium shadow-lg shadow-[#25D366]/25 transition-colors"
                  >
                    <MessageCircle className="h-4 w-4" /> WhatsApp
                  </a>
                )}
                <Button
                  data-testid="checkout-pay-button"
                  onClick={confirmAndPay}
                  disabled={submitting}
                  className="rounded-xl bg-red-600 hover:bg-red-700 text-white px-6 h-11"
                >
                  {submitting ? "Redirecionando..." : "Pagar com Stripe"}
                </Button>
              </div>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
