import { useState, useEffect, useCallback } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useOffline } from "@/context/OfflineContext";
import { useRealtimeReload } from "@/lib/hooks";
import api from "@/lib/api";
import {
  LayoutDashboard, ShoppingCart, Package, Boxes, Truck, Factory,
  Users as UsersIcon, Building2, Wallet, Target, FileBarChart, ScrollText,
  UserCog, Settings as SettingsIcon, LogOut, Menu, Bell, Wifi, WifiOff, History, Drumstick, RefreshCw, CloudOff,
  BookCheck, Zap,
} from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { formatTime } from "@/lib/format";
import PendingSales from "@/components/PendingSales";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["owner", "admin"] },
  { to: "/pos", label: "POS Kasir", icon: ShoppingCart, roles: ["owner", "admin", "kasir"] },
  { to: "/riwayat", label: "Riwayat Transaksi", icon: History, roles: ["owner", "admin", "kasir"] },
  { to: "/produk", label: "Produk & Harga", icon: Package, roles: ["owner", "admin"] },
  { to: "/stok", label: "Stok", icon: Boxes, roles: ["owner", "admin", "kasir"] },
  { to: "/pembelian", label: "Pembelian", icon: Truck, roles: ["owner", "admin"] },
  { to: "/produksi", label: "Produksi Potong", icon: Factory, roles: ["owner", "admin", "kasir"] },
  { to: "/pelanggan", label: "Pelanggan", icon: UsersIcon, roles: ["owner", "admin", "kasir"] },
  { to: "/supplier", label: "Supplier", icon: Building2, roles: ["owner", "admin"] },
  { to: "/keuangan", label: "Keuangan", icon: Wallet, roles: ["owner", "admin", "kasir"] },
  { to: "/target", label: "Target", icon: Target, roles: ["owner", "admin"] },
  { to: "/laporan", label: "Laporan", icon: FileBarChart, roles: ["owner", "admin"] },
  { to: "/tutup-buku", label: "Tutup Buku", icon: BookCheck, roles: ["owner", "admin"] },
  { to: "/audit", label: "Audit Log", icon: ScrollText, roles: ["owner", "admin"] },
  { to: "/pengguna", label: "Pengguna", icon: UserCog, roles: ["owner"] },
  { to: "/pengaturan", label: "Pengaturan", icon: SettingsIcon, roles: ["owner"] },
];

const ROLE_LABEL = { owner: "Owner", admin: "Admin", kasir: "Kasir", operator: "Operator" };
const LEVEL_DOT = { danger: "bg-destructive", warning: "bg-warning", success: "bg-success", info: "bg-chart-4" };

function NavItems({ role, onClick }) {
  const items = NAV.filter((n) => n.roles.includes(role));
  return (
    <nav className="flex flex-col gap-1 px-3">
      {items.map((n) => {
        const Icon = n.icon;
        return (
          <NavLink
            key={n.to}
            to={n.to}
            onClick={onClick}
            data-testid={`nav-${n.to.slice(1)}`}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150 ${
                isActive ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"
              }`
            }
          >
            <Icon className="w-[18px] h-[18px] shrink-0" />
            <span>{n.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-5 py-5">
      <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shadow-sm">
        <Drumstick className="w-5 h-5 text-primary-foreground" />
      </div>
      <div className="leading-tight">
        <p className="font-head font-extrabold text-[15px] text-foreground">Berkah Ayam Mili</p>
        <p className="text-[11px] text-muted-foreground">Ayam Potong & Fillet</p>
      </div>
    </div>
  );
}

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [notifs, setNotifs] = useState([]);
  const [pendingOpen, setPendingOpen] = useState(false);
  const { online, syncing, pending, failed } = useOffline();

  useEffect(() => { setOpen(false); }, [location.pathname]);

  const loadNotifs = useCallback(async () => {
    try {
      const r = await api.get("/notifications");
      setNotifs(r.data);
    } catch (e) {
      if (e.response && process.env.NODE_ENV !== "production") console.error("Gagal memuat notifikasi:", e);
      /* network errors are reflected by OfflineContext status */
    }
  }, []);

  // Notifikasi didorong server lewat WebSocket. Polling tetap ada sebagai
  // jaring pengaman (jarang saat live, cepat saat socket mati).
  const live = useRealtimeReload(["notifications"], loadNotifs);

  useEffect(() => {
    loadNotifs();
    const id = setInterval(loadNotifs, live ? 60000 : 12000);
    return () => clearInterval(id);
  }, [loadNotifs, live]);

  const unread = notifs.filter((n) => !n.read).length;
  const markRead = async () => { await api.post("/notifications/read-all"); setNotifs((p) => p.map((n) => ({ ...n, read: true }))); };

  return (
    <div className="min-h-screen bg-background flex">
      {/* desktop sidebar */}
      <aside className="hidden lg:flex w-64 flex-col border-r border-border bg-card fixed inset-y-0 z-30">
        <Brand />
        <div className="flex-1 overflow-y-auto no-scrollbar pb-6">
          <NavItems role={user.role} />
        </div>
      </aside>

      <div className="flex-1 min-w-0 lg:pl-64 flex flex-col min-h-screen">
        {/* top bar */}
        <header className="sticky top-0 z-20 h-16 border-b border-border bg-card/80 backdrop-blur-xl flex items-center justify-between px-4 lg:px-6">
          <div className="flex items-center gap-3">
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger asChild>
                <button data-testid="menu-toggle" className="lg:hidden p-2 rounded-lg hover:bg-accent">
                  <Menu className="w-5 h-5" />
                </button>
              </SheetTrigger>
              <SheetContent side="left" className="p-0 w-72 bg-card">
                <Brand />
                <div className="overflow-y-auto no-scrollbar h-[calc(100vh-80px)] pb-6">
                  <NavItems role={user.role} onClick={() => setOpen(false)} />
                </div>
              </SheetContent>
            </Sheet>
            <div className="flex items-center gap-2" data-testid="connection-status">
              {syncing ? (
                <span className="flex items-center gap-1.5 text-xs font-semibold text-chart-4">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" /> SINKRONISASI{pending > 0 ? ` (${pending})` : ""}
                </span>
              ) : online ? (
                <span className="flex items-center gap-1.5 text-xs font-semibold text-success">
                  <span className="relative flex h-2 w-2"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-60" /><span className="relative inline-flex rounded-full h-2 w-2 bg-success" /></span>
                  <Wifi className="w-3.5 h-3.5" /> ONLINE
                </span>
              ) : (
                <span className="flex items-center gap-1.5 text-xs font-semibold text-destructive">
                  <WifiOff className="w-3.5 h-3.5" /> OFFLINE
                </span>
              )}

              {live && online && !syncing && (
                <span data-testid="live-badge" title="Data diperbarui seketika dari server (realtime)"
                  className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border border-chart-4/40 bg-chart-4/10 text-chart-4">
                  <Zap className="w-3 h-3" /> LIVE
                </span>
              )}

              {(pending > 0 || failed > 0) && (
                <button
                  data-testid="pending-badge"
                  onClick={() => setPendingOpen(true)}
                  title="Lihat transaksi yang menunggu sinkron"
                  className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-[11px] font-bold border transition-colors ${
                    failed > 0
                      ? "border-destructive/40 bg-destructive/10 text-destructive hover:bg-destructive/20"
                      : "border-warning/40 bg-warning/10 text-warning hover:bg-warning/20"
                  }`}
                >
                  <CloudOff className="w-3.5 h-3.5" />
                  {pending > 0 ? `${pending} antre` : ""}
                  {pending > 0 && failed > 0 ? " · " : ""}
                  {failed > 0 ? `${failed} ditolak` : ""}
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <DropdownMenu onOpenChange={(o) => o && unread && markRead()}>
              <DropdownMenuTrigger asChild>
                <button data-testid="notif-btn" className="relative p-2 rounded-lg hover:bg-accent">
                  <Bell className="w-5 h-5" />
                  {unread > 0 && <span className="absolute -top-0.5 -right-0.5 w-4 h-4 text-[10px] rounded-full bg-primary text-primary-foreground flex items-center justify-center">{unread}</span>}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-80 bg-popover">
                <DropdownMenuLabel>Notifikasi</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <div className="max-h-80 overflow-y-auto">
                  {notifs.length === 0 && <p className="px-3 py-6 text-center text-sm text-muted-foreground">Belum ada notifikasi</p>}
                  {notifs.slice(0, 15).map((n) => (
                    <div key={n.id} className="flex gap-2.5 px-3 py-2.5 hover:bg-accent">
                      <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${LEVEL_DOT[n.level] || "bg-muted-foreground"}`} />
                      <div className="min-w-0">
                        <p className="text-sm font-semibold truncate">{n.title}</p>
                        <p className="text-xs text-muted-foreground">{n.message}</p>
                        <p className="text-[10px] text-muted-foreground mt-0.5">{formatTime(n.created_at)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </DropdownMenuContent>
            </DropdownMenu>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button data-testid="user-menu" className="flex items-center gap-2 pl-2 pr-1 py-1 rounded-lg hover:bg-accent">
                  <div className="w-8 h-8 rounded-full bg-secondary text-secondary-foreground flex items-center justify-center font-bold text-sm">
                    {user.name?.charAt(0)}
                  </div>
                  <div className="hidden sm:block text-left leading-tight">
                    <p className="text-sm font-semibold">{user.name}</p>
                    <p className="text-[11px] text-muted-foreground">{ROLE_LABEL[user.role]}</p>
                  </div>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48 bg-popover">
                <DropdownMenuLabel>
                  <p className="text-sm">{user.name}</p>
                  <p className="text-xs text-muted-foreground font-normal">{user.username}</p>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem data-testid="logout-btn" onClick={logout} className="text-destructive">
                  <LogOut className="w-4 h-4 mr-2" /> Keluar
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main className="flex-1 min-w-0 p-4 lg:p-6">{children}</main>
      </div>

      {pendingOpen && <PendingSales onClose={() => setPendingOpen(false)} />}
    </div>
  );
}

export { Badge };
