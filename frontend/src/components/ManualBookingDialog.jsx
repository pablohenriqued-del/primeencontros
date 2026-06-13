import { useEffect, useState } from "react";
import { api, brl } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";
import { Loader2, Save } from "lucide-react";
import { toast } from "sonner";

const PAYMENT_METHODS = [
  { v: "whatsapp", label: "WhatsApp (fora da plataforma)" },
  { v: "pix", label: "PIX" },
  { v: "cash", label: "Dinheiro" },
  { v: "manual", label: "Outro / manual" },
];
const DURATIONS = [60, 90, 120];

export default function ManualBookingDialog({ open, onClose, onCreated }) {
  const [massagistas, setMassagistas] = useState([]);
  const [saving, setSaving] = useState(false);
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    massagista_id: "",
    user_email: "",
    date: today,
    time: "15:00",
    duration: 60,
    payment_method: "whatsapp",
    notes: "",
  });

  useEffect(() => {
    if (!open) return;
    api.get("/massagistas").then(({ data }) => setMassagistas(data)).catch(() => {});
  }, [open]);

  const selected = massagistas.find(m => m.id === form.massagista_id);
  const previewPrice = selected ? (form.duration === 60 ? selected.price_60 : form.duration === 90 ? selected.price_90 : selected.price_120) : 0;

  const submit = async () => {
    if (!form.massagista_id) { toast.error("Escolha a profissional"); return; }
    if (!form.user_email.trim()) { toast.error("Informe o e-mail do cliente (precisa ter logado pelo menos 1x)"); return; }
    if (!form.date || !form.time) { toast.error("Informe data e horário"); return; }
    setSaving(true);
    try {
      const { data } = await api.post("/admin/bookings/manual", {
        massagista_id: form.massagista_id,
        user_email: form.user_email.trim().toLowerCase(),
        date: form.date,
        time: form.time,
        duration: Number(form.duration),
        payment_method: form.payment_method,
        notes: form.notes || null,
      });
      toast.success("Atendimento lançado · cliente poderá avaliar");
      onCreated?.(data);
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Erro ao lançar atendimento");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose?.()}>
      <DialogContent className="bg-zinc-950 border border-zinc-900 text-zinc-100 max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display text-xl text-zinc-50">Lançar atendimento manual</DialogTitle>
          <DialogDescription className="text-zinc-400">
            Use quando o cliente conversou no WhatsApp e pagou fora do Stripe (PIX, dinheiro). Cria uma reserva já <span className="text-red-400 font-medium">confirmada</span> — libera o botão "Avaliar" pra ele.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 mt-2">
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">Profissional</Label>
            <Select value={form.massagista_id} onValueChange={(v) => setForm({ ...form, massagista_id: v })}>
              <SelectTrigger data-testid="manual-massagista" className="mt-2 h-10 rounded-xl bg-black border-zinc-800 text-zinc-200">
                <SelectValue placeholder="Selecione a profissional" />
              </SelectTrigger>
              <SelectContent className="bg-zinc-950 border-zinc-800 text-zinc-200 max-h-72">
                {massagistas.map(m => (
                  <SelectItem key={m.id} value={m.id}>{m.name} · {m.bairro}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">E-mail do cliente</Label>
            <Input
              data-testid="manual-user-email"
              type="email"
              value={form.user_email}
              onChange={(e) => setForm({ ...form, user_email: e.target.value })}
              placeholder="cliente@email.com"
              className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100"
            />
            <p className="text-[11px] text-zinc-500 mt-1">O cliente precisa ter feito login na Prime Encontros pelo menos uma vez.</p>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label className="text-xs uppercase tracking-wider text-zinc-500">Data</Label>
              <Input data-testid="manual-date" type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-zinc-500">Hora</Label>
              <Input data-testid="manual-time" type="time" value={form.time} onChange={(e) => setForm({ ...form, time: e.target.value })} className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
            </div>
            <div>
              <Label className="text-xs uppercase tracking-wider text-zinc-500">Duração</Label>
              <Select value={String(form.duration)} onValueChange={(v) => setForm({ ...form, duration: Number(v) })}>
                <SelectTrigger data-testid="manual-duration" className="mt-2 h-10 rounded-xl bg-black border-zinc-800 text-zinc-200">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-950 border-zinc-800 text-zinc-200">
                  {DURATIONS.map(d => <SelectItem key={d} value={String(d)}>{d} min</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">Forma de pagamento</Label>
            <Select value={form.payment_method} onValueChange={(v) => setForm({ ...form, payment_method: v })}>
              <SelectTrigger data-testid="manual-payment" className="mt-2 h-10 rounded-xl bg-black border-zinc-800 text-zinc-200">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-zinc-950 border-zinc-800 text-zinc-200">
                {PAYMENT_METHODS.map(p => <SelectItem key={p.v} value={p.v}>{p.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">Observações</Label>
            <Textarea data-testid="manual-notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Detalhes sobre o atendimento..." maxLength={400} className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100 resize-none h-20" />
          </div>

          {selected && (
            <div className="rounded-xl bg-black border border-zinc-800 px-4 py-3 flex items-center justify-between">
              <span className="text-xs text-zinc-500 uppercase tracking-wider">Valor registrado</span>
              <span className="font-display text-xl font-semibold text-red-500">{brl(previewPrice)}</span>
            </div>
          )}
        </div>

        <DialogFooter className="mt-3">
          <Button variant="outline" onClick={() => onClose?.()} className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900">Cancelar</Button>
          <Button
            data-testid="manual-submit"
            onClick={submit}
            disabled={saving}
            className="rounded-full bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-600/25"
          >
            {saving ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Save className="h-4 w-4 mr-1.5" />}
            Lançar atendimento
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
