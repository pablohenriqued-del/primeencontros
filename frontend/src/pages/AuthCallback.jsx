import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

export default function AuthCallback() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const hash = window.location.hash || "";
    const m = hash.match(/session_id=([^&]+)/);
    if (!m) { navigate("/"); return; }
    const sessionId = m[1];

    api.post("/auth/session", null, { headers: { "X-Session-ID": sessionId } })
      .then(({ data }) => {
        setToken(data.session_token);
        setUser(data.user);
        toast.success(`Bem-vindo(a), ${data.user.name?.split(" ")[0] || ""}!`);
        // Clean URL fragment
        window.history.replaceState(null, "", window.location.pathname);
        navigate("/", { state: { user: data.user }, replace: true });
      })
      .catch(() => {
        toast.error("Falha na autenticação. Tente novamente.");
        navigate("/", { replace: true });
      });
  }, [navigate, setUser]);

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-stone-500">
      <div className="h-10 w-10 rounded-full border-2 border-emerald-800 border-t-transparent animate-spin mb-4" />
      Autenticando...
    </div>
  );
}
