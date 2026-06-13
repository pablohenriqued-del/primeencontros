import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, brl } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import MediaEditor from "@/components/MediaEditor";
import { ShieldAlert, ShieldCheck, Star, ImageIcon, Save, Plus, X, Loader2 } from "lucide-react";
import { toast } from "sonner";

const DEFAULT_SPECS = ["Relaxante", "Sueca", "Pedras Quentes", "Shiatsu", "Drenagem Linfática", "Esportiva", "Ortopédica", "Gestante", "Aromaterapia", "Tailandesa"];

export default function MyProfile() {
  const { user, loading: authLoading, login } = useAuth();
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [bairros, setBairros] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [media, setMedia] = useState(false);

  // form state
  const [form, setForm] = useState({
    name: "", bairro_slug: "", bio: "",
    specialties: [], price_60: "", price_90: "", price_120: "",
    experience_years: "", languages: ["Português"],
  });
  const [newSpec, setNewSpec] = useState("");

  useEffect(() => {
    api.get("/bairros").then(({ data }) => setBairros(data));
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!user) { setLoading(false); return; }
    api.get("/me/profile")
      .then(({ data }) => {
        if (data.profile) {
          setProfile(data.profile);
          setForm({
            name: data.profile.name,
            bairro_slug: data.profile.bairro_slug,
            bio: data.profile.bio,
            specialties: data.profile.specialties || [],
            price_60: String(data.profile.price_60 || ""),
            price_90: String(data.profile.price_90 || ""),
            price_120: String(data.profile.price_120 || ""),
            experience_years: String(data.profile.experience_years || ""),
            languages: data.profile.languages || ["Português"],
          });
        } else {
          setForm((f) => ({ ...f, name: user.name || "" }));
        }
      })
      .catch(() => toast.error("Erro ao carregar perfil"))
      .finally(() => setLoading(false));
  }, [user, authLoading]);

  if (authLoading || loading) return <div className="max-w-7xl mx-auto px-4 py-20 text-zinc-500">Carregando...</div>;

  if (!user) {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h2 className="font-display text-2xl font-medium text-zinc-50">Sou profissional</h2>
        <p className="text-zinc-400 mt-2 mb-6">Entre com Google para cadastrar seu perfil de massoterapeuta na plataforma.</p>
        <Button onClick={login} className="rounded-full bg-red-600 hover:bg-red-700 text-white px-6 h-11">Entrar com Google</Button>
      </div>
    );
  }

  const toggleSpec = (s) => setForm((f) => ({
    ...f,
    specialties: f.specialties.includes(s) ? f.specialties.filter(x => x !== s) : [...f.specialties, s],
  }));

  const addCustomSpec = () => {
    const s = newSpec.trim();
    if (!s) return;
    if (!form.specialties.includes(s)) {
      setForm((f) => ({ ...f, specialties: [...f.specialties, s] }));
    }
    setNewSpec("");
  };

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        bairro_slug: form.bairro_slug,
        bio: form.bio,
        specialties: form.specialties,
        price_60: parseFloat(form.price_60),
        price_90: form.price_90 ? parseFloat(form.price_90) : undefined,
        price_120: form.price_120 ? parseFloat(form.price_120) : undefined,
        experience_years: parseInt(form.experience_years, 10) || 0,
        languages: form.languages,
      };
      if (profile) {
        const { data } = await api.put("/me/profile", payload);
        setProfile(data);
        toast.success("Perfil atualizado");
      } else {
        const { data } = await api.post("/me/profile", payload);
        setProfile(data);
        toast.success("Perfil criado · aguardando verificação");
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div data-testid="my-profile-page" className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex items-end justify-between flex-wrap gap-3 mb-6">
        <div>
          <h1 className="font-display text-3xl font-medium text-zinc-50">{profile ? "Meu perfil profissional" : "Cadastrar perfil profissional"}</h1>
          <p className="text-zinc-400 text-sm mt-1">{profile ? "Edite seus dados, preços e disponibilidade." : "Preencha os dados abaixo para começar a receber clientes."}</p>
        </div>
        {profile && (
          <div className="flex items-center gap-2">
            {profile.verified ? (
              <Badge className="bg-red-600 text-white rounded-full border-0 shadow-[0_0_12px_rgba(220,38,38,0.6)]">
                <ShieldCheck className="h-3 w-3 mr-1" /> Verificada
              </Badge>
            ) : (
              <Badge className="bg-amber-500/15 text-amber-300 border border-amber-500/40 rounded-full">
                <ShieldAlert className="h-3 w-3 mr-1" /> Aguardando verificação
              </Badge>
            )}
            <Button data-testid="edit-my-media" onClick={() => setMedia(true)} variant="outline" className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900">
              <ImageIcon className="h-4 w-4 mr-1.5" /> Editar fotos / vídeo
            </Button>
          </div>
        )}
      </div>

      {profile && (
        <div className="bg-zinc-950 border border-zinc-900 rounded-2xl p-4 mb-6 flex items-center gap-4">
          <img src={profile.main_image} alt="" className="h-16 w-16 rounded-xl object-cover" />
          <div className="flex-1">
            <div className="text-xs text-zinc-500">Como aparece para clientes</div>
            <div className="font-display text-lg text-zinc-50">{profile.name}</div>
            <div className="text-xs text-zinc-400 flex items-center gap-3 mt-0.5">
              <span>{profile.bairro}</span>
              <span className="inline-flex items-center gap-1"><Star className="h-3 w-3 fill-amber-400 text-amber-400" /> {profile.rating?.toFixed(1)} ({profile.reviews})</span>
              <span>{profile.gallery?.length || 0} fotos</span>
            </div>
          </div>
        </div>
      )}

      <div className="bg-zinc-950 border border-zinc-900 rounded-2xl p-5 sm:p-6 space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">Nome profissional</Label>
            <Input data-testid="profile-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Como você aparece para os clientes" className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">Bairro de atendimento</Label>
            <Select value={form.bairro_slug} onValueChange={(v) => setForm({ ...form, bairro_slug: v })}>
              <SelectTrigger data-testid="profile-bairro" className="mt-2 h-10 rounded-xl bg-black border-zinc-800 text-zinc-200">
                <SelectValue placeholder="Selecione" />
              </SelectTrigger>
              <SelectContent className="bg-zinc-950 border-zinc-800 text-zinc-200">
                {bairros.map(b => <SelectItem key={b.slug} value={b.slug}>{b.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div>
          <Label className="text-xs uppercase tracking-wider text-zinc-500">Bio · descreva seu trabalho</Label>
          <Textarea data-testid="profile-bio" value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} maxLength={600} placeholder="Conte sua formação, técnicas, abordagem..." className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100 resize-none h-28" />
        </div>

        <div>
          <Label className="text-xs uppercase tracking-wider text-zinc-500">Especialidades</Label>
          <div className="mt-2 flex flex-wrap gap-2">
            {DEFAULT_SPECS.map(s => {
              const on = form.specialties.includes(s);
              return (
                <button
                  key={s}
                  type="button"
                  data-testid={`spec-${s}`}
                  onClick={() => toggleSpec(s)}
                  className={`text-sm rounded-full px-3 py-1.5 border transition-colors
                    ${on ? "bg-red-600 border-red-600 text-white" : "border-zinc-800 text-zinc-300 hover:border-zinc-700"}`}
                >
                  {s}
                </button>
              );
            })}
            {form.specialties.filter(s => !DEFAULT_SPECS.includes(s)).map(s => (
              <button
                key={s}
                type="button"
                onClick={() => toggleSpec(s)}
                className="text-sm rounded-full px-3 py-1.5 border bg-red-600 border-red-600 text-white inline-flex items-center gap-1"
              >
                {s} <X className="h-3 w-3" />
              </button>
            ))}
          </div>
          <div className="mt-2 flex gap-2">
            <Input value={newSpec} onChange={(e) => setNewSpec(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustomSpec())} placeholder="Adicionar outra..." className="flex-1 h-9 rounded-xl bg-black border-zinc-800 text-zinc-100" data-testid="profile-new-spec" />
            <Button type="button" onClick={addCustomSpec} variant="outline" className="rounded-xl border-zinc-700 text-zinc-200 hover:bg-zinc-900 h-9"><Plus className="h-4 w-4" /></Button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">60 min (R$)</Label>
            <Input data-testid="price-60" type="number" min="0" step="10" value={form.price_60} onChange={(e) => setForm({ ...form, price_60: e.target.value })} className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">90 min (R$)</Label>
            <Input data-testid="price-90" type="number" min="0" step="10" value={form.price_90} onChange={(e) => setForm({ ...form, price_90: e.target.value })} placeholder="auto" className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">120 min (R$)</Label>
            <Input data-testid="price-120" type="number" min="0" step="10" value={form.price_120} onChange={(e) => setForm({ ...form, price_120: e.target.value })} placeholder="auto" className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">Anos de experiência</Label>
            <Input data-testid="profile-experience" type="number" min="0" max="60" value={form.experience_years} onChange={(e) => setForm({ ...form, experience_years: e.target.value })} className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">Idiomas (separados por vírgula)</Label>
            <Input data-testid="profile-languages" value={form.languages.join(", ")} onChange={(e) => setForm({ ...form, languages: e.target.value.split(",").map(s => s.trim()).filter(Boolean) })} className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 pt-2 border-t border-zinc-900">
          {!profile && (
            <Button onClick={() => navigate("/")} variant="outline" className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900">Cancelar</Button>
          )}
          <Button
            data-testid="save-profile"
            onClick={save}
            disabled={saving}
            className="rounded-full bg-red-600 hover:bg-red-700 text-white px-5 shadow-lg shadow-red-600/25"
          >
            {saving ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Save className="h-4 w-4 mr-1.5" />}
            {profile ? "Salvar alterações" : "Criar perfil"}
          </Button>
        </div>
      </div>

      {profile && (
        <MediaEditor
          open={media}
          massagista={profile}
          owner
          onClose={() => setMedia(false)}
          onUpdated={(updated) => setProfile(updated)}
        />
      )}
    </div>
  );
}
