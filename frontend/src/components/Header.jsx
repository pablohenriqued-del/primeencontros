import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuSeparator, DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { Flame, CalendarCheck, LogOut, User as UserIcon, ShieldCheck, Briefcase } from "lucide-react";

export default function Header() {
  const { user, login, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-40 glass-nav border-b border-zinc-900/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link to="/" data-testid="logo-link" className="flex items-center gap-2.5 group">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-red-600 text-white shadow-[0_0_20px_rgba(220,38,38,0.5)]">
            <Flame className="h-5 w-5" />
          </span>
          <div className="leading-tight">
            <div className="font-display text-lg font-semibold tracking-tight text-zinc-50">
              Prime <span className="text-red-500">Encontros</span>
            </div>
            <div className="text-[10px] uppercase tracking-[0.22em] text-red-500/80 -mt-0.5">Massagem Premium · RJ</div>
          </div>
        </Link>

        <nav className="hidden md:flex items-center gap-7 text-sm text-zinc-300">
          <Link to="/" className="hover:text-red-500 transition-colors" data-testid="nav-explore">Massagistas</Link>
          {user && (
            <Link to="/minhas-reservas" className="hover:text-red-500 transition-colors" data-testid="nav-bookings">
              Minhas reservas
            </Link>
          )}
          {user && (
            <Link to="/sou-profissional" className="hover:text-red-500 transition-colors" data-testid="nav-pro">
              Sou profissional
            </Link>
          )}
          {user?.is_admin && (
            <Link to="/admin" className="inline-flex items-center gap-1.5 text-red-500 hover:text-red-400 transition-colors" data-testid="nav-admin">
              <ShieldCheck className="h-4 w-4" /> Admin
            </Link>
          )}
        </nav>

        <div className="flex items-center gap-3">
          {!user ? (
            <Button
              data-testid="google-login-button"
              onClick={login}
              className="rounded-full bg-red-600 hover:bg-red-700 text-white px-5 shadow-lg shadow-red-600/20"
            >
              Entrar com Google
            </Button>
          ) : (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button data-testid="user-menu-trigger" className="flex items-center gap-2 rounded-full pl-1 pr-3 py-1 hover:bg-zinc-900 transition-colors">
                  <Avatar className="h-8 w-8 ring-1 ring-red-500/30">
                    <AvatarImage src={user.picture} alt={user.name} />
                    <AvatarFallback className="bg-zinc-900 text-zinc-200">{user.name?.[0] || "U"}</AvatarFallback>
                  </Avatar>
                  <span className="hidden sm:inline text-sm font-medium text-zinc-200">{user.name?.split(" ")[0]}</span>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56 bg-zinc-950 border-zinc-800 text-zinc-200">
                <DropdownMenuLabel className="text-xs text-zinc-500">{user.email}</DropdownMenuLabel>
                <DropdownMenuSeparator className="bg-zinc-800" />
                <DropdownMenuItem data-testid="menu-my-bookings" onClick={() => navigate("/minhas-reservas")} className="focus:bg-zinc-900 focus:text-red-400">
                  <CalendarCheck className="h-4 w-4 mr-2" /> Minhas reservas
                </DropdownMenuItem>
                <DropdownMenuItem data-testid="menu-pro" onClick={() => navigate("/sou-profissional")} className="focus:bg-zinc-900 focus:text-red-400">
                  <Briefcase className="h-4 w-4 mr-2" /> Sou profissional
                </DropdownMenuItem>
                {user.is_admin && (
                  <DropdownMenuItem data-testid="menu-admin" onClick={() => navigate("/admin")} className="focus:bg-zinc-900 focus:text-red-400">
                    <ShieldCheck className="h-4 w-4 mr-2" /> Painel Admin
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem data-testid="menu-profile" disabled>
                  <UserIcon className="h-4 w-4 mr-2" /> Meu perfil
                </DropdownMenuItem>
                <DropdownMenuSeparator className="bg-zinc-800" />
                <DropdownMenuItem data-testid="menu-logout" onClick={logout} className="focus:bg-zinc-900 focus:text-red-400">
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
