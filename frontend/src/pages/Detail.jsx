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
import { Star, MapPin, Clock, ChevronLeft, Play, Languages, Award, Sparkles } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

const TIME_SLOTS = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00"];

export default function Detail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user, login } = useAuth();
  const [m, setM] = useState(null);
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
  }, [id, navigate]);

  if (loading || !m) {
    return <div className="max-w-7xl mx-auto px-4 py-20 text-stone-500">Carregando...</div>;
  }

  const priceFor = (d) => d === 60 ? m.price_60 : d === 90 ? m.price_90 : m.price_120;

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
      <Link to="/" className="inline-flex items-center text-sm text-stone-600 hover:text-emerald-800 mb-6">
        <ChevronLeft className="h-4 w-4 mr-1" /> Voltar
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: gallery + bio */}
        <div className="lg:col-span-8 space-y-8">
          {/* Bento gallery */}
          <div className="grid grid-cols-4 grid-rows-2 gap-3 h-[320px] sm:h-[460px]">
            <div className="col-span-4 sm:col-span-2 row-span-2 relative rounded-2xl overflow-hidden bg-stone-100">
              <img src={m.gallery[0]} alt={m.name} className="w-full h-full object-cover" />
            </div>
            <div className="hidden sm:block col-span-1 row-span-1 rounded-2xl overflow-hidden bg-stone-100">
              <img src={m.gallery[1]} alt="" className="w-full h-full object-cover" />
            </div>
            <div
              data-testid="open-video-button"
              onClick={() => setVideoOpen(true)}
              className="hidden sm:block col-span-1 row-span-1 rounded-2xl overflow-hidden bg-stone-100 relative cursor-pointer group"
            >
              <img src={m.video_thumb} alt="" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
              <div className="absolute inset-0 bg-stone-900/30 flex items-center justify-center">
                <div className="h-14 w-14 rounded-full bg-white/90 backdrop-blur flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform">
                  <Play className="h-6 w-6 text-stone-900 ml-0.5" />
                </div>
              </div>
              <div className="absolute bottom-2 right-2 text-[10px] uppercase tracking-wider text-white font-semibold bg-stone-900/60 backdrop-blur px-2 py-0.5 rounded-full">Vídeo</div>
            </div>
            <div className="hidden sm:block col-span-1 row-span-1 rounded-2xl overflow-hidden bg-stone-100">
              <img src={m.gallery[2]} alt="" className="w-full h-full object-cover" />
            </div>
            <div className="hidden sm:block col-span-1 row-span-1 rounded-2xl overflow-hidden bg-stone-100">
              <img src={m.gallery[3]} alt="" className="w-full h-full object-cover" />
            </div>
          </div>

          {/* Header info */}
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <Badge className="bg-emerald-50 text-emerald-800 hover:bg-emerald-50 border-emerald-200 rounded-full">
                <MapPin className="h-3 w-3 mr-1" /> {m.bairro}
              </Badge>
              <Badge className="bg-stone-100 text-stone-800 hover:bg-stone-100 rounded-full border-0">
                <Award className="h-3 w-3 mr-1" /> {m.experience_years} anos de experiência
              </Badge>
              <Badge className="bg-stone-100 text-stone-800 hover:bg-stone-100 rounded-full border-0">
                <Languages className="h-3 w-3 mr-1" /> {m.languages.join(", ")}
              </Badge>
            </div>
            <h1 className="font-display text-3xl sm:text-4xl font-medium tracking-tight text-stone-900">{m.name}</h1>
            <div className="flex items-center gap-3 mt-2 text-stone-700">
              <div className="flex items-center gap-1">
                <Star className="h-4 w-4 fill-amber-500 text-amber-500" />
                <span className="font-medium">{m.rating.toFixed(1)}</span>
                <span className="text-stone-400 text-sm">({m.reviews} avaliações)</span>
              </div>
            </div>
          </div>

          <Tabs defaultValue="sobre" className="w-full">
            <TabsList className="bg-stone-100 rounded-full p-1">
              <TabsTrigger value="sobre" className="rounded-full data-[state=active]:bg-white" data-testid="tab-sobre">Sobre</TabsTrigger>
              <TabsTrigger value="especialidades" className="rounded-full data-[state=active]:bg-white" data-testid="tab-specs">Especialidades</TabsTrigger>
              <TabsTrigger value="avaliacoes" className="rounded-full data-[state=active]:bg-white" data-testid="tab-reviews">Avaliações</TabsTrigger>
            </TabsList>
            <TabsContent value="sobre" className="mt-6 text-stone-700 leading-relaxed">
              <p>{m.bio}</p>
            </TabsContent>
            <TabsContent value="especialidades" className="mt-6">
              <div className="flex flex-wrap gap-2">
                {m.specialties.map((s) => (
                  <span key={s} className="inline-flex items-center rounded-full bg-emerald-50 text-emerald-800 border border-emerald-100 px-3 py-1.5 text-sm">
                    <Sparkles className="h-3.5 w-3.5 mr-1.5" /> {s}
                  </span>
                ))}
              </div>
            </TabsContent>
            <TabsContent value="avaliacoes" className="mt-6 text-stone-700">
              <div className="text-sm text-stone-500">
                {m.reviews} avaliações com média de {m.rating.toFixed(1)} estrelas. Atendimento pontual, profissional e acolhedor — segundo nossos clientes verificados.
              </div>
            </TabsContent>
          </Tabs>
        </div>

        {/* Right: booking widget */}
        <aside className="lg:col-span-4">
          <div className="lg:sticky lg:top-24 bg-white rounded-2xl border border-stone-100 shadow-sm p-6">
            <p className="text-xs uppercase tracking-[0.18em] text-emerald-700 font-bold mb-2">Reservar agora</p>
            <div className="flex items-baseline gap-2 mb-6">
              <span className="font-display text-3xl font-semibold text-stone-900">{brl(priceFor(duration))}</span>
              <span className="text-stone-500 text-sm">/ {duration} min</span>
            </div>

            <div className="space-y-2 mb-5">
              {[60, 90, 120].map((d) => (
                <button
                  key={d}
                  data-testid={`duration-${d}`}
                  onClick={() => setDuration(d)}
                  className={`w-full flex items-center justify-between rounded-xl px-4 py-3 border transition-colors text-left
                    ${duration === d ? "border-emerald-800 bg-emerald-50/50" : "border-stone-200 hover:border-stone-300"}`}
                >
                  <span className="flex items-center text-sm font-medium text-stone-800">
                    <Clock className="h-4 w-4 mr-2 text-stone-500" /> {d} minutos
                  </span>
                  <span className="font-semibold text-stone-900">{brl(priceFor(d))}</span>
                </button>
              ))}
            </div>

            <Button
              data-testid="open-booking-button"
              onClick={startBooking}
              className="w-full h-12 rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white text-base font-medium"
            >
              Continuar para agendamento
            </Button>
            <p className="text-xs text-stone-500 text-center mt-3">
              Pagamento seguro via Stripe · Confirmação imediata
            </p>
          </div>
        </aside>
      </div>

      {/* Video dialog */}
      <Dialog open={videoOpen} onOpenChange={setVideoOpen}>
        <DialogContent className="max-w-3xl p-0 overflow-hidden bg-stone-900 border-0">
          <DialogHeader className="sr-only">
            <DialogTitle>Vídeo de {m.name}</DialogTitle>
          </DialogHeader>
          <video src={m.video_url} controls autoPlay className="w-full h-auto" data-testid="profile-video" />
        </DialogContent>
      </Dialog>

      {/* Booking dialog */}
      <Dialog open={bookingOpen} onOpenChange={setBookingOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="font-display text-2xl">Agendar com {m.name}</DialogTitle>
            <DialogDescription>{duration} min · {brl(priceFor(duration))} · {m.bairro}</DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-2">
            <div>
              <Label className="text-xs uppercase tracking-wider text-stone-500">Data</Label>
              <div className="mt-2 rounded-xl border border-stone-200 flex justify-center" data-testid="booking-calendar">
                <Calendar
                  mode="single"
                  selected={date}
                  onSelect={setDate}
                  disabled={(d) => d < new Date(new Date().setHours(0, 0, 0, 0))}
                />
              </div>
            </div>
            <div className="space-y-5">
              <div>
                <Label className="text-xs uppercase tracking-wider text-stone-500">Horário</Label>
                <div className="mt-2 grid grid-cols-3 gap-2">
                  {TIME_SLOTS.map((t) => (
                    <button
                      key={t}
                      data-testid={`slot-${t}`}
                      onClick={() => setTime(t)}
                      className={`rounded-lg py-2 text-sm font-medium border transition-colors
                        ${time === t ? "bg-emerald-800 border-emerald-800 text-white" : "border-stone-200 text-stone-700 hover:border-stone-300"}`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider text-stone-500">Local</Label>
                <RadioGroup value={locationType} onValueChange={setLocationType} className="mt-2 space-y-2">
                  <div className="flex items-center gap-2 rounded-xl border border-stone-200 p-3">
                    <RadioGroupItem value="studio" id="loc-studio" data-testid="loc-studio" />
                    <Label htmlFor="loc-studio" className="flex-1 cursor-pointer">
                      <div className="text-sm font-medium">No estúdio</div>
                      <div className="text-xs text-stone-500">{m.bairro} · Rio de Janeiro</div>
                    </Label>
                  </div>
                  <div className="flex items-center gap-2 rounded-xl border border-stone-200 p-3">
                    <RadioGroupItem value="home" id="loc-home" data-testid="loc-home" />
                    <Label htmlFor="loc-home" className="flex-1 cursor-pointer">
                      <div className="text-sm font-medium">Em domicílio</div>
                      <div className="text-xs text-stone-500">Atendimento no seu endereço</div>
                    </Label>
                  </div>
                </RadioGroup>
                {locationType === "home" && (
                  <Input
                    data-testid="booking-address"
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    placeholder="Rua, número, bairro..."
                    className="mt-2 rounded-xl"
                  />
                )}
              </div>
              <div>
                <Label className="text-xs uppercase tracking-wider text-stone-500">Observações (opcional)</Label>
                <Textarea
                  data-testid="booking-notes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Preferências, alergias, dores..."
                  className="mt-2 rounded-xl resize-none h-20"
                />
              </div>
            </div>
          </div>

          <DialogFooter className="mt-6">
            <div className="w-full flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="text-sm text-stone-700">
                Total: <span className="font-display text-xl font-semibold text-stone-900 ml-1">{brl(priceFor(duration))}</span>
              </div>
              <Button
                data-testid="checkout-pay-button"
                onClick={confirmAndPay}
                disabled={submitting}
                className="rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white px-6 h-11"
              >
                {submitting ? "Redirecionando..." : "Pagar com Stripe"}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
