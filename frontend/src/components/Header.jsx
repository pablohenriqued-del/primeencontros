import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuSeparator, DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { Sparkles, CalendarCheck, LogOut, User as UserIcon } from "lucide-react";

export default function Header() {
  const { user, login, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-40 glass-nav border-b border-stone-200/70">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link to="/" data-testid="logo-link" className="flex items-center gap-2 group">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-800 text-white">
            <Sparkles className="h-5 w-5" />
          </span>
          <div className="leading-tight">
            <div className="font-display text-lg font-semibold tracking-tight text-stone-900">Oásis Rio</div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-emerald-700 -mt-0.5">Massagem · RJ</div>
          </div>
        </Link>

        <nav className="hidden md:flex items-center gap-7 text-sm text-stone-700">
          <Link to="/" className="hover:text-emerald-800 transition-colors" data-testid="nav-explore">Explorar</Link>
          {user && (
            <Link to="/minhas-reservas" className="hover:text-emerald-800 transition-colors" data-testid="nav-bookings">
              Minhas reservas
            </Link>
          )}
        </nav>

        <div className="flex items-center gap-3">
          {!user ? (
            <Button
              data-testid="google-login-button"
              onClick={login}
              className="rounded-full bg-stone-900 hover:bg-stone-800 text-white px-5"
            >
              Entrar com Google
            </Button>
          ) : (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button data-testid="user-menu-trigger" className="flex items-center gap-2 rounded-full pl-1 pr-3 py-1 hover:bg-stone-100 transition-colors">
                  <Avatar className="h-8 w-8">
                    <AvatarImage src={user.picture} alt={user.name} />
                    <AvatarFallback>{user.name?.[0] || "U"}</AvatarFallback>
                  </Avatar>
                  <span className="hidden sm:inline text-sm font-medium text-stone-800">{user.name?.split(" ")[0]}</span>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel className="text-xs text-stone-500">{user.email}</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem data-testid="menu-my-bookings" onClick={() => navigate("/minhas-reservas")}>
                  <CalendarCheck className="h-4 w-4 mr-2" /> Minhas reservas
                </DropdownMenuItem>
                <DropdownMenuItem data-testid="menu-profile" disabled>
                  <UserIcon className="h-4 w-4 mr-2" /> Meu perfil
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem data-testid="menu-logout" onClick={logout}>
                  <LogOut className="h-4 w-4 mr-2" /> Sair
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>
    </header>
  );
}
