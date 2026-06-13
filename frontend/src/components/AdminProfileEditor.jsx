import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Loader2, Save, Plus, X } from "lucide-react";
import { toast } from "sonner";

const DEFAULT_SPECS = ["Relaxante", "Sueca", "Pedras Quentes", "Shiatsu", "Drenagem Linfática", "Esportiva", "Ortopédica", "Gestante", "Aromaterapia", "Tailandesa", "Reflexologia", "Bambuterapia"];

export default function AdminProfileEditor({ open, massagista, onClose, onUpdated }) {
  const [bairros, setBairros] = useState([]);
  const [saving, setSaving] = useState(false);
  const [newSpec, setNewSpec] = useState("");
  const [form, setForm] = useState({
    name: "", bairro_slug: "", bio: "",
    specialties: [], price_60: "", price_90: "", price_120: "",
    experience_years: "", languages: [],
  });

  useEffect(() => {
    api.get("/bairros").then(({ data }) => setBairros(data));
  }, []);

  useEffect(() => {
    if (!massagista) return;
    setForm({
      name: massagista.name || "",
      bairro_slug: massagista.bairro_slug || "",
      bio: massagista.bio || "",
      specialties: massagista.specialties || [],
      price_60: String(massagista.price_60 ?? ""),
      price_90: String(massagista.price_90 ?? ""),
      price_120: String(massagista.price_120 ?? ""),
      experience_years: String(massagista.experience_years ?? ""),
      languages: massagista.languages || ["Português"],
    });
  }, [massagista]);

  if (!massagista) return null;

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
    const name = form.name.trim();
    if (name.length < 2) { toast.error("Informe o nome"); return; }
    if (!form.bairro_slug) { toast.error("Selecione o bairro"); return; }
    if (form.bio.trim().length < 10) { toast.error("Bio precisa ter no mínimo 10 caracteres"); return; }
    if (form.specialties.length === 0) { toast.error("Escolha ao menos uma especialidade"); return; }
    const p60 = parseFloat(form.price_60);
    if (!p60 || p60 <= 0) { toast.error("Preço 60min precisa ser maior que zero"); return; }

    setSaving(true);
    try {
      const payload = {
        name,
        bairro_slug: form.bairro_slug,
        bio: form.bio.trim(),
        specialties: form.specialties,
        price_60: p60,
        price_90: form.price_90 ? parseFloat(form.price_90) : undefined,
        price_120: form.price_120 ? parseFloat(form.price_120) : undefined,
        experience_years: parseInt(form.experience_years, 10) || 0,
        languages: form.languages,
      };
      const { data } = await api.put(`/admin/massagistas/${massagista.id}`, payload);
      toast.success("Perfil atualizado");
      onUpdated?.(data);
      onClose?.();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      let msg = "Erro ao salvar";
      if (typeof detail === "string") msg = detail;
      else if (Array.isArray(detail) && detail[0]?.msg) msg = `Campo inválido: ${detail[0].msg}`;
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose?.()}>
      <DialogContent className="bg-zinc-950 border border-zinc-900 text-zinc-100 max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display text-xl text-zinc-50">Editar dados · {massagista.name}</DialogTitle>
          <DialogDescription className="text-zinc-400">
            Atualiza nome, bairro, bio, especialidades, preços e idiomas.
            {massagista.owner_user_id && <span className="block text-[11px] text-amber-400 mt-1">⚠ Perfil autocadastrado por {massagista.owner_user_id} — alterações sobrescrevem o que a profissional preencheu.</span>}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 mt-2">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="text-xs uppercase tracking-wider text-zinc-500">Nome</Label>
              <Input data-testid="admin-edit-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-zinc-500">Bairro</Label>
              <Select value={form.bairro_slug} onValueChange={(v) => setForm({ ...form, bairro_slug: v })}>
                <SelectTrigger data-testid="admin-edit-bairro" className="mt-2 h-10 rounded-xl bg-black border-zinc-800 text-zinc-200">
                  <SelectValue placeholder="Selecione" />
                </SelectTrigger>
                <SelectContent className="bg-zinc-950 border-zinc-800 text-zinc-200">
                  {bairros.map(b => <SelectItem key={b.slug} value={b.slug}>{b.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">Bio</Label>
            <Textarea data-testid="admin-edit-bio" value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} maxLength={600} className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100 resize-none h-24" />
          </div>

          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">Especialidades</Label>
            <div className="mt-2 flex flex-wrap gap-2">
              {[...new Set([...DEFAULT_SPECS, ...form.specialties])].map(s => {
                const on = form.specialties.includes(s);
                return (
                  <button
                    key={s}
                    type="button"
                    data-testid={`admin-spec-${s}`}
                    onClick={() => toggleSpec(s)}
                    className={`text-sm rounded-full px-3 py-1.5 border transition-colors
                      ${on ? "bg-red-600 border-red-600 text-white" : "border-zinc-800 text-zinc-300 hover:border-zinc-700"}`}
                  >
                    {s}{!DEFAULT_SPECS.includes(s) && on && <X className="h-3 w-3 inline ml-1" />}
                  </button>
                );
              })}
            </div>
            <div className="mt-2 flex gap-2">
              <Input value={newSpec} onChange={(e) => setNewSpec(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustomSpec())} placeholder="Adicionar outra..." className="flex-1 h-9 rounded-xl bg-black border-zinc-800 text-zinc-100" />
              <Button type="button" onClick={addCustomSpec} variant="outline" className="rounded-xl border-zinc-700 text-zinc-200 hover:bg-zinc-900 h-9"><Plus className="h-4 w-4" /></Button>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label className="text-xs uppercase tracking-wider text-zinc-500">60 min (R$)</Label>
              <Input data-testid="admin-edit-price-60" type="number" min="0" step="10" value={form.price_60} onChange={(e) => setForm({ ...form, price_60: e.target.value })} className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-zinc-500">90 min (R$)</Label>
              <Input data-testid="admin-edit-price-90" type="number" min="0" step="10" value={form.price_90} onChange={(e) => setForm({ ...form, price_90: e.target.value })} className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-zinc-500">120 min (R$)</Label>
              <Input data-testid="admin-edit-price-120" type="number" min="0" step="10" value={form.price_120} onChange={(e) => setForm({ ...form, price_120: e.target.value })} className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="text-xs uppercase tracking-wider text-zinc-500">Anos de experiência</Label>
              <Input data-testid="admin-edit-experience" type="number" min="0" max="60" value={form.experience_years} onChange={(e) => setForm({ ...form, experience_years: e.target.value })} className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-zinc-500">Idiomas (vírgula)</Label>
              <Input data-testid="admin-edit-languages" value={form.languages.join(", ")} onChange={(e) => setForm({ ...form, languages: e.target.value.split(",").map(s => s.trim()).filter(Boolean) })} className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
            </div>
          </div>
        </div>

        <DialogFooter className="mt-2">
          <Button variant="outline" onClick={() => onClose?.()} className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900">Cancelar</Button>
          <Button
            data-testid="admin-save-edit"
            onClick={save}
            disabled={saving}
            className="rounded-full bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-600/25"
          >
            {saving ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Save className="h-4 w-4 mr-1.5" />}
            Salvar alterações
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
