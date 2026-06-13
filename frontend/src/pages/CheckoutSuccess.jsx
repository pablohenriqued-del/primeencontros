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
          <div className="mx-auto h-16 w-16 rounded-full border-2 border-emerald-800 border-t-transparent animate-spin mb-6" />
          <h1 className="font-display text-2xl font-medium text-stone-900">Confirmando seu pagamento...</h1>
          <p className="text-stone-500 mt-2">Não feche esta página.</p>
        </>
      )}
      {state.status === "paid" && (
        <div data-testid="payment-success">
          <CheckCircle2 className="h-16 w-16 text-emerald-700 mx-auto mb-4" />
          <h1 className="font-display text-3xl font-medium text-stone-900">Reserva confirmada!</h1>
          <p className="text-stone-500 mt-2">
            Pagamento de {brl((state.info.amount_total || 0) / 100)} recebido com sucesso.
          </p>
          <div className="mt-8 flex gap-3 justify-center">
            <Button asChild className="rounded-full bg-emerald-800 hover:bg-emerald-900">
              <Link to="/minhas-reservas" data-testid="go-to-bookings">Ver minhas reservas</Link>
            </Button>
            <Button asChild variant="outline" className="rounded-full">
              <Link to="/">Voltar à home</Link>
            </Button>
          </div>
        </div>
      )}
      {state.status === "pending" && (
        <>
          <Clock className="h-16 w-16 text-amber-600 mx-auto mb-4" />
          <h1 className="font-display text-2xl font-medium text-stone-900">Pagamento em processamento</h1>
          <p className="text-stone-500 mt-2">Você receberá uma confirmação por e-mail em instantes.</p>
          <Button asChild className="mt-6 rounded-full"><Link to="/minhas-reservas">Ver minhas reservas</Link></Button>
        </>
      )}
      {(state.status === "expired" || state.status === "error") && (
        <>
          <XCircle className="h-16 w-16 text-rose-600 mx-auto mb-4" />
          <h1 className="font-display text-2xl font-medium text-stone-900">Não conseguimos confirmar o pagamento</h1>
          <p className="text-stone-500 mt-2">Tente novamente ou escolha outro horário.</p>
          <Button asChild className="mt-6 rounded-full bg-emerald-800 hover:bg-emerald-900"><Link to="/">Voltar à home</Link></Button>
        </>
      )}
    </div>
  );
}
