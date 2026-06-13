import { useEffect, useState, useRef } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, brl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { CheckCircle2, Clock, XCircle } from "lucide-react";

export default function CheckoutSuccess() {
  const [sp] = useSearchParams();
  const sessionId = sp.get("session_id");
  const [state, setState] = useState({ status: "polling", info: null });
  const attempts = useRef(0);
  const cancelled = useRef(false);

  useEffect(() => {
    if (!sessionId) { setState({ status: "error", info: null }); return; }

    const poll = async () => {
      if (cancelled.current) return;
      try {
        const { data } = await api.get(`/checkout/status/${sessionId}`);
        if (data.payment_status === "paid") {
          setState({ status: "paid", info: data });
          return;
        }
        if (data.status === "expired") {
          setState({ status: "expired", info: data });
          return;
        }
        attempts.current += 1;
        if (attempts.current >= 6) {
          setState({ status: "pending", info: data });
          return;
        }
        setTimeout(poll, 2000);
      } catch {
        setState({ status: "error", info: null });
      }
    };
    poll();
    return () => { cancelled.current = true; };
  }, [sessionId]);

  return (
    <div className="max-w-xl mx-auto px-4 py-20 text-center">
      {state.status === "polling" && (
        <>
          <div className="mx-auto h-16 w-16 rounded-full border-2 border-red-600 border-t-transparent animate-spin mb-6" />
          <h1 className="font-display text-2xl font-medium text-zinc-50">Confirmando seu pagamento...</h1>
          <p className="text-zinc-400 mt-2">Não feche esta página.</p>
        </>
      )}
      {state.status === "paid" && (
        <div data-testid="payment-success">
          <CheckCircle2 className="h-16 w-16 text-red-500 mx-auto mb-4" />
          <h1 className="font-display text-3xl font-medium text-zinc-50">Reserva confirmada!</h1>
          <p className="text-zinc-400 mt-2">
            Pagamento de {brl((state.info.amount_total || 0) / 100)} recebido com sucesso.
          </p>
          <div className="mt-8 flex gap-3 justify-center">
            <Button asChild className="rounded-full bg-red-600 hover:bg-red-700 shadow-lg shadow-red-600/25">
              <Link to="/minhas-reservas" data-testid="go-to-bookings">Ver minhas reservas</Link>
            </Button>
            <Button asChild variant="outline" className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900 hover:text-zinc-50">
              <Link to="/">Voltar à home</Link>
            </Button>
          </div>
        </div>
      )}
      {state.status === "pending" && (
        <>
          <Clock className="h-16 w-16 text-amber-400 mx-auto mb-4" />
          <h1 className="font-display text-2xl font-medium text-zinc-50">Pagamento em processamento</h1>
          <p className="text-zinc-400 mt-2">Você receberá uma confirmação por e-mail em instantes.</p>
          <Button asChild className="mt-6 rounded-full bg-red-600 hover:bg-red-700"><Link to="/minhas-reservas">Ver minhas reservas</Link></Button>
        </>
      )}
      {(state.status === "expired" || state.status === "error") && (
        <>
          <XCircle className="h-16 w-16 text-red-600 mx-auto mb-4" />
          <h1 className="font-display text-2xl font-medium text-zinc-50">Não conseguimos confirmar o pagamento</h1>
          <p className="text-zinc-400 mt-2">Tente novamente ou escolha outro horário.</p>
          <Button asChild className="mt-6 rounded-full bg-red-600 hover:bg-red-700"><Link to="/">Voltar à home</Link></Button>
        </>
      )}
    </div>
  );
}
