import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Drumstick, Loader2 } from "lucide-react";

const DEMO = [
  { role: "Owner", email: "shezrofenia18@gmail.com", pass: "berkahayam1" },
  { role: "Admin", email: "admin@berkahayam.com", pass: "admin123" },
  { role: "Kasir", email: "kasir@berkahayam.com", pass: "kasir123" },
  { role: "Operator", email: "operator@berkahayam.com", pass: "operator123" },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e, ov) => {
    e?.preventDefault();
    setLoading(true);
    const em = ov?.email || email;
    const pw = ov?.pass || password;
    const res = await login(em, pw);
    setLoading(false);
    if (res.ok) {
      toast.success(`Selamat datang, ${res.user.name}`);
      navigate("/");
    } else {
      toast.error(res.error);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background">
      {/* hero */}
      <div className="hidden lg:flex relative bam-hero overflow-hidden">
        <img
          src="https://images.pexels.com/photos/35023463/pexels-photo-35023463.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=900&w=940"
          alt="Butcher shop" className="absolute inset-0 w-full h-full object-cover mix-blend-overlay opacity-40"
        />
        <div className="relative z-10 flex flex-col justify-between p-12 text-white">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-white/15 backdrop-blur flex items-center justify-center">
              <Drumstick className="w-6 h-6" />
            </div>
            <span className="font-head font-extrabold text-xl">Berkah Ayam Mili</span>
          </div>
          <div>
            <h1 className="font-head font-extrabold text-4xl xl:text-5xl leading-tight tracking-tight">
              Sistem POS & Manajemen<br />Bisnis Ayam Potong
            </h1>
            <p className="mt-4 text-white/85 max-w-md">
              Kelola penjualan, stok, pemotongan, HPP, laba, dan pantau bisnis Anda
              secara real-time dari mana saja.
            </p>
          </div>
          <p className="text-white/70 text-sm">Ayam Broiler · Kampung · Pejantan · Fillet</p>
        </div>
      </div>

      {/* form */}
      <div className="flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-sm bam-fade">
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
              <Drumstick className="w-5 h-5 text-primary-foreground" />
            </div>
            <span className="font-head font-extrabold text-lg">Berkah Ayam Mili</span>
          </div>
          <h2 className="font-head font-bold text-2xl mb-1">Masuk</h2>
          <p className="text-muted-foreground text-sm mb-6">Silakan masuk untuk melanjutkan</p>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" data-testid="login-email" type="email" value={email}
                onChange={(e) => setEmail(e.target.value)} placeholder="nama@berkahayam.com" className="mt-1.5" required />
            </div>
            <div>
              <Label htmlFor="password">Kata Sandi</Label>
              <Input id="password" data-testid="login-password" type="password" value={password}
                onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" className="mt-1.5" required />
            </div>
            <Button data-testid="login-submit" type="submit" disabled={loading} className="w-full h-11 rounded-lg font-semibold">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Masuk"}
            </Button>
          </form>

          <div className="mt-8">
            <p className="text-xs text-muted-foreground mb-2">Login cepat (demo):</p>
            <div className="grid grid-cols-2 gap-2">
              {DEMO.map((d) => (
                <button key={d.role} data-testid={`quick-login-${d.role.toLowerCase()}`}
                  onClick={(e) => submit(e, { email: d.email, pass: d.pass })}
                  className="text-left px-3 py-2 rounded-lg border border-border hover:border-primary hover:bg-accent transition-colors">
                  <p className="text-sm font-semibold">{d.role}</p>
                  <p className="text-[11px] text-muted-foreground truncate">{d.email}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
