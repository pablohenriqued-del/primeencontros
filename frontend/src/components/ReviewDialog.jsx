import { useState } from "react";
import { api } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Star } from "lucide-react";
import { toast } from "sonner";

export default function ReviewDialog({ open, booking, onClose, onSubmitted }) {
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!booking) return null;

  const submit = async () => {
    if (rating < 1) { toast.error("Escolha de 1 a 5 estrelas"); return; }
    setSubmitting(true);
    try {
      const { data } = await api.post(`/bookings/${booking.id}/review`, { rating, comment: comment || null });
      toast.success("Avaliação enviada · obrigado!");
      onSubmitted?.(data);
      onClose?.();
      setRating(0); setHover(0); setComment("");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Erro ao enviar avaliação");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose?.()}>
      <DialogContent className="bg-zinc-950 border border-zinc-900 text-zinc-100 max-w-md">
        <DialogHeader>
          <DialogTitle className="font-display text-xl text-zinc-50">Avaliar atendimento</DialogTitle>
          <DialogDescription className="text-zinc-400">
            {booking.massagista_name} · {booking.date} às {booking.time}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-2 space-y-4">
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">Sua nota</Label>
            <div className="mt-2 flex items-center gap-1" data-testid="star-picker">
              {[1, 2, 3, 4, 5].map((n) => {
                const filled = (hover || rating) >= n;
                return (
                  <button
                    key={n}
                    data-testid={`star-${n}`}
                    onMouseEnter={() => setHover(n)}
                    onMouseLeave={() => setHover(0)}
                    onClick={() => setRating(n)}
                    className="p-1"
                    type="button"
                  >
                    <Star className={`h-8 w-8 transition-transform ${filled ? "fill-amber-400 text-amber-400 scale-105" : "text-zinc-700"}`} />
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">Comentário (opcional)</Label>
            <Textarea
              data-testid="review-comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Como foi sua experiência?"
              maxLength={600}
              className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100 placeholder:text-zinc-600 resize-none h-24"
            />
            <div className="text-[10px] text-zinc-600 text-right mt-1">{comment.length}/600</div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onClose?.()} className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900">
            Cancelar
          </Button>
          <Button
            data-testid="submit-review"
            onClick={submit}
            disabled={submitting || rating < 1}
            className="rounded-full bg-red-600 hover:bg-red-700 text-white"
          >
            {submitting ? "Enviando..." : "Enviar avaliação"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
