import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import Header from "@/components/Header";
import Home from "@/pages/Home";
import Detail from "@/pages/Detail";
import MyBookings from "@/pages/MyBookings";
import AuthCallback from "@/pages/AuthCallback";
import CheckoutSuccess from "@/pages/CheckoutSuccess";
import { Toaster } from "@/components/ui/sonner";

function AppRouter() {
  const location = useLocation();
  // CRITICAL: synchronously route to AuthCallback if fragment contains session_id
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/massagista/:id" element={<Detail />} />
      <Route path="/minhas-reservas" element={<MyBookings />} />
      <Route path="/checkout/success" element={<CheckoutSuccess />} />
      <Route path="*" element={<Home />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="min-h-screen bg-stone-50">
          <Header />
          <AppRouter />
          <footer className="border-t border-stone-200 bg-white">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 text-sm text-stone-500 flex flex-col sm:flex-row items-center justify-between gap-3">
              <div>© {new Date().getFullYear()} Oásis Rio · Massagem terapêutica profissional</div>
              <div className="text-xs">Atendimento em Ipanema · Leblon · Copacabana · Botafogo · Barra · e mais</div>
            </div>
          </footer>
        </div>
        <Toaster richColors position="top-right" />
      </AuthProvider>
    </BrowserRouter>
  );
}
