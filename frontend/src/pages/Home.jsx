import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, brl } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";
import { MapPin, Star, Search, Navigation, Clock, Heart, Flame } from "lucide-react";
import { toast } from "sonner";

const HERO_BG = "https://images.unsplash.com/photo-1679957631642-94f406206544?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODd8MHwxfHNlYXJjaHwzfHxyaW8lMjBkZSUyMGphbmVpcm8lMjBpcGFuZW1hJTIwbGFuZHNjYXBlfGVufDB8fHx8MTc4MTMxMTk3NXww&ixlib=rb-4.1.0&q=85";

export default function Home() {
  const [bairros, setBairros] = useState([]);
  const [bairro, setBairro] = useState("all");
  const [q, setQ] = useState("");
  const [coords, setCoords] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [locating, setLocating] = useState(false);

  useEffect(() => {
    api.get("/bairros").then(({ data }) => setBairros(data));
  }, []);

  const fetchList = async () => {
    setLoading(true);
    try {
      const params = {};
      if (bairro && bairro !== "all") params.bairro = bairro;
      if (q) params.q = q;
      if (coords) { params.lat = coords.lat; params.lng = coords.lng; }
      const { data } = await api.get("/massagistas", { params });
      setItems(data);
    } catch {
      toast.error("Não foi possível carregar as profissionais");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchList(); /* eslint-disable-next-line */ }, [bairro, coords]);

  const useMyLocation = () => {
    if (!navigator.geolocation) { toast.error("Geolocalização indisponível"); return; }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocating(false);
        toast.success("Mostrando profissionais mais próximas de você");
      },
      () => {
        setLocating(false);
        toast.error("Permissão negada — selecione um bairro manualmente");
      },
      { timeout: 8000 }
    );
  };

  const clearLocation = () => { setCoords(null); };

  return (
    <div data-testid="home-page" className="pb-24">
      {/* Hero */}
      <section className="relative">
        <div className="absolute inset-0">
          <img src={HERO_BG} alt="Rio de Janeiro" className="w-full h-full object-cover opacity-50" />
          <div className="absolute inset-0 bg-gradient-to-b from-black/70 via-black/60 to-black" />
          <div className="absolute inset-0 grain opacity-40" />
        </div>
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-28 md:pt-28 md:pb-36">
          <div className="max-w-2xl">
            <p className="inline-flex items-center text-xs font-bold uppercase tracking-[0.22em] text-red-500 mb-4">
              <Flame className="h-3.5 w-3.5 mr-2" /> Premium · Rio de Janeiro
            </p>
            <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-light tracking-tighter text-white text-shadow-lg leading-[1.05]">
              Massagem profissional, <em className="not-italic font-medium text-red-500">onde você estiver</em>.
            </h1>
            <p className="mt-5 text-base sm:text-lg text-zinc-300 max-w-xl">
              Profissionais verificados em Ipanema, Leblon, Copacabana e mais 9 bairros do Rio.
              Agende em segundos e pague com segurança.
            </p>
          </div>
        </div>

        {/* Floating search bar */}
        <div className="relative max-w-5xl mx-auto px-4 sm:px-6 -mt-14 z-10">
          <div className="bg-zinc-950/95 backdrop-blur-xl rounded-2xl shadow-2xl shadow-red-900/10 border border-zinc-800 p-4 md:p-5 grid grid-cols-1 md:grid-cols-12 gap-3 md:gap-4">
            <div className="md:col-span-5 flex items-center gap-2 bg-black rounded-xl px-4 py-3 border border-zinc-800">
              <Search className="h-4 w-4 text-zinc-500" />
              <Input
                data-testid="search-input"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && fetchList()}
                placeholder="Buscar por especialidade, nome ou bairro..."
                className="border-0 bg-transparent shadow-none focus-visible:ring-0 px-0 h-7 text-zinc-100 placeholder:text-zinc-500"
              />
            </div>
            <div className="md:col-span-4">
              <Select value={bairro} onValueChange={setBairro}>
                <SelectTrigger data-testid="bairro-select" className="h-12 rounded-xl bg-black border-zinc-800 text-zinc-200">
                  <SelectValue placeholder="Todos os bairros" />
                </SelectTrigger>
                <SelectContent className="bg-zinc-950 border-zinc-800 text-zinc-200">
                  <SelectItem value="all">Todos os bairros</SelectItem>
                  {bairros.map((b) => (
                    <SelectItem key={b.slug} value={b.slug}>{b.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="md:col-span-3 flex gap-2">
              <Button
                data-testid="near-me-button"
                onClick={coords ? clearLocation : useMyLocation}
                disabled={locating}
                className={`flex-1 h-12 rounded-xl border ${coords
                  ? "bg-red-600 hover:bg-red-700 border-red-600 text-white"
                  : "bg-transparent hover:bg-zinc-900 border-zinc-800 text-zinc-200"}`}
              >
                <Navigation className="h-4 w-4 mr-2" />
                {locating ? "Localizando..." : coords ? "Perto de mim ✓" : "Perto de mim"}
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Results */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-16">
        <div className="flex items-end justify-between mb-8">
          <div>
            <h2 className="font-display text-2xl sm:text-3xl font-medium tracking-tight text-zinc-50">
              {coords ? "Mais perto de você" : bairro !== "all" ? `Profissionais em ${bairros.find(b => b.slug === bairro)?.name}` : "Profissionais em destaque"}
            </h2>
            <p className="text-sm text-zinc-500 mt-1">
              {items.length} {items.length === 1 ? "profissional" : "profissionais"} disponíveis agora
            </p>
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 md:gap-8">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-[420px] rounded-2xl bg-zinc-900 animate-pulse" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-20 text-zinc-500">Nenhuma profissional encontrada — tente outro filtro.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 md:gap-8">
            {items.map((m, i) => (
              <Link
                key={m.id}
                to={`/massagista/${m.id}`}
                data-testid={`therapist-card-${m.id}`}
                className="group block bg-zinc-950 rounded-2xl border border-zinc-900 overflow-hidden hover:border-red-600/50 hover:shadow-[0_8px_40px_-12px_rgba(220,38,38,0.35)] hover:-translate-y-1 transition-all duration-300"
                style={{ animationDelay: `${i * 40}ms` }}
              >
                <div className="relative aspect-[4/5] overflow-hidden bg-zinc-900">
                  <img
                    src={m.main_image}
                    alt={m.name}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
                  <div className="absolute top-3 left-3 flex flex-wrap gap-1.5">
                    <Badge className="bg-black/70 backdrop-blur text-zinc-100 hover:bg-black/80 rounded-full px-2.5 py-0.5 text-xs font-medium border border-zinc-800">
                      <MapPin className="h-3 w-3 mr-1" /> {m.bairro}
                    </Badge>
                    {m.distance_km !== undefined && (
                      <Badge className="bg-red-600 text-white hover:bg-red-700 rounded-full px-2.5 py-0.5 text-xs font-medium border-0">
                        {m.distance_km < 1 ? `${Math.round(m.distance_km * 1000)} m` : `${m.distance_km.toFixed(1)} km`}
                      </Badge>
                    )}
                  </div>
                  <button
                    onClick={(e) => { e.preventDefault(); }}
                    className="absolute top-3 right-3 h-8 w-8 rounded-full bg-black/60 backdrop-blur flex items-center justify-center hover:bg-red-600/80 transition-colors border border-zinc-800"
                    data-testid={`favorite-${m.id}`}
                  >
                    <Heart className="h-4 w-4 text-zinc-100" />
                  </button>
                </div>
                <div className="p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-display text-lg font-semibold text-zinc-50 leading-tight">{m.name}</h3>
                      <p className="text-xs text-zinc-500 mt-0.5">{m.specialties.slice(0, 2).join(" · ")}</p>
                    </div>
                    <div className="flex items-center gap-1 text-sm text-zinc-200 shrink-0">
                      <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
                      <span className="font-medium">{m.rating.toFixed(1)}</span>
                      <span className="text-zinc-500 text-xs">({m.reviews})</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between mt-4 pt-4 border-t border-zinc-900">
                    <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                      <Clock className="h-3.5 w-3.5" /> 60 min
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-zinc-500">a partir de</div>
                      <div className="font-display text-lg font-semibold text-red-500">{brl(m.price_60)}</div>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
