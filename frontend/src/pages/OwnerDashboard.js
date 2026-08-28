import { usePoll } from "@/lib/hooks";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import {
  formatRupiah, formatRupiahShort, formatWeight, formatNumber, formatPct,
  formatTime, CATEGORY_LABELS, PAYMENT_LABELS,
} from "@/lib/format";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar, Cell,
} from "recharts";
import {
  Wallet, TrendingUp, Scale, Percent, Target as TargetIcon, Boxes,
  ShoppingCart, Truck, Scissors, Factory, AlertTriangle, CreditCard, Package,
} from "lucide-react";

const ACT_ICON = { sale: ShoppingCart, purchase: Truck, slaughter: Scissors, production: Factory, stock_low: AlertTriangle, cancel: AlertTriangle, payment: CreditCard, adjust: Boxes };
const ACT_COLOR = { sale: "text-success", purchase: "text-chart-4", slaughter: "text-chart-5", production: "text-chart-5", stock_low: "text-warning", cancel: "text-destructive", payment: "text-secondary", adjust: "text-muted-foreground" };

function Stat({ icon: Icon, label, value, sub, tone = "primary", testid }) {
  const tones = { primary: "bg-primary/10 text-primary", success: "bg-success/10 text-success", warning: "bg-warning/20 text-warning", chart4: "bg-chart-4/10 text-chart-4" };
  return (
    <Card className="p-5 bam-card-hover" data-testid={testid}>
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
          <p className="font-head font-extrabold text-2xl mt-1.5 tabular truncate">{value}</p>
          {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
        </div>
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${tones[tone]}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </Card>
  );
}

const TICK_SM = { fontSize: 11 };
const TICK_MD = { fontSize: 12 };
const TOOLTIP_STYLE = { borderRadius: 12, border: "1px solid hsl(var(--border))" };
const AREA_MARGIN = { left: -10, right: 8 };
const BAR_MARGIN = { left: -10 };
const BAR_RADIUS = [6, 6, 0, 0];
const jtFmt = (v) => `${v / 1000000}jt`;

export default function OwnerDashboard() {
  const { data: d } = usePoll("/dashboard", 8000);

  if (!d) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 8 }).map((_, i) => <div key={`skel-${i}`} className="h-28 rounded-xl bg-muted animate-pulse" />)}
      </div>
    );
  }

  const ach = d.target.achievement || 0;

  return (
    <div className="bam-fade">
      <PageHeader title="Dashboard Owner" subtitle="Ringkasan bisnis hari ini · diperbarui otomatis" testid="owner-dashboard" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat testid="stat-omzet" icon={Wallet} label="Omzet Hari Ini" value={formatRupiah(d.omzet)} sub={`${d.txn_count} transaksi`} tone="primary" />
        <Stat testid="stat-terjual" icon={Scale} label="Ayam Terjual" value={formatWeight(d.weight)} sub={`${formatNumber(d.ekor)} ekor`} tone="chart4" />
        <Stat testid="stat-laba" icon={TrendingUp} label="Laba Kotor" value={formatRupiah(d.laba)} sub={`HPP ${formatRupiahShort(d.hpp)}`} tone="success" />
        <Stat testid="stat-margin" icon={Percent} label="Margin" value={formatPct(d.margin)} sub={`Laba bersih ${formatRupiahShort(d.net_profit)}`} tone="warning" />
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mt-4">
        {/* target */}
        <Card className="p-5 lg:col-span-1" data-testid="target-card">
          <div className="flex items-center gap-2 mb-4">
            <TargetIcon className="w-4 h-4 text-primary" />
            <h3 className="font-head font-bold">Target Hari Ini</h3>
          </div>
          {d.target.omzet ? (
            <>
              <div className="flex items-end justify-between mb-1">
                <span className="text-sm text-muted-foreground">Omzet</span>
                <span className="font-bold tabular">{formatPct(ach)}</span>
              </div>
              <Progress value={Math.min(ach, 100)} className="h-2.5" />
              <p className="text-xs text-muted-foreground mt-1.5">{formatRupiah(d.omzet)} / {formatRupiah(d.target.omzet)}</p>
              <div className="grid grid-cols-3 gap-2 mt-5 text-center">
                <div><p className="text-[11px] text-muted-foreground">Berat</p><p className="font-bold text-sm tabular">{formatWeight(d.weight, 0)}</p><p className="text-[10px] text-muted-foreground">/{formatNumber(d.target.weight)}kg</p></div>
                <div><p className="text-[11px] text-muted-foreground">Ekor</p><p className="font-bold text-sm tabular">{formatNumber(d.ekor)}</p><p className="text-[10px] text-muted-foreground">/{formatNumber(d.target.ekor)}</p></div>
                <div><p className="text-[11px] text-muted-foreground">Laba</p><p className="font-bold text-sm tabular">{formatRupiahShort(d.laba)}</p><p className="text-[10px] text-muted-foreground">/{formatRupiahShort(d.target.laba)}</p></div>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground py-6 text-center">Target belum diatur untuk hari ini.</p>
          )}
        </Card>

        {/* sales chart */}
        <Card className="p-5 lg:col-span-2" data-testid="sales-chart">
          <h3 className="font-head font-bold mb-4">Grafik Penjualan 7 Hari</h3>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={d.chart} margin={AREA_MARGIN}>
              <defs>
                <linearGradient id="gOmzet" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis dataKey="label" tick={TICK_MD} stroke="hsl(var(--muted-foreground))" />
              <YAxis tick={TICK_SM} stroke="hsl(var(--muted-foreground))" tickFormatter={jtFmt} />
              <Tooltip formatter={(v) => formatRupiah(v)} contentStyle={TOOLTIP_STYLE} />
              <Area type="monotone" dataKey="omzet" name="Omzet" stroke="hsl(var(--primary))" strokeWidth={2.5} fill="url(#gOmzet)" />
              <Area type="monotone" dataKey="laba" name="Laba" stroke="hsl(var(--success))" strokeWidth={2} fillOpacity={0} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mt-4">
        {/* product performance */}
        <Card className="p-5 lg:col-span-2" data-testid="product-perf">
          <h3 className="font-head font-bold mb-4">Performa Produk</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={d.products_perf.map((p) => ({ ...p, label: CATEGORY_LABELS[p.category] || p.category }))} margin={BAR_MARGIN}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis dataKey="label" tick={TICK_SM} stroke="hsl(var(--muted-foreground))" />
              <YAxis tick={TICK_SM} stroke="hsl(var(--muted-foreground))" tickFormatter={jtFmt} />
              <Tooltip formatter={(v) => formatRupiah(v)} contentStyle={TOOLTIP_STYLE} />
              <Bar dataKey="penjualan" name="Penjualan" radius={BAR_RADIUS}>
                {d.products_perf.map((p, i) => <Cell key={p.category} fill={`hsl(var(--chart-${(i % 5) + 1}))`} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
            {d.products_perf.map((p) => (
              <div key={p.category} className="rounded-lg border border-border p-2.5">
                <p className="text-xs font-semibold truncate">{CATEGORY_LABELS[p.category] || p.category}</p>
                <p className="text-sm font-bold tabular">{formatRupiahShort(p.penjualan)}</p>
                <p className="text-[11px] text-success">Margin {formatPct(p.margin)}</p>
              </div>
            ))}
          </div>
        </Card>

        {/* activity feed */}
        <Card className="p-5" data-testid="activity-feed">
          <h3 className="font-head font-bold mb-4">Aktivitas Toko</h3>
          <div className="space-y-3 max-h-[360px] overflow-y-auto no-scrollbar">
            {d.activities.length === 0 && <p className="text-sm text-muted-foreground">Belum ada aktivitas.</p>}
            {d.activities.map((a) => {
              const Icon = ACT_ICON[a.type] || ShoppingCart;
              return (
                <div key={a.id} className="flex gap-3">
                  <div className={`w-8 h-8 rounded-lg bg-accent flex items-center justify-center shrink-0 ${ACT_COLOR[a.type] || ""}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold">{a.title}</p>
                    <p className="text-xs text-muted-foreground truncate">{a.message}</p>
                  </div>
                  <div className="text-right shrink-0">
                    {a.amount > 0 && <p className="text-sm font-bold tabular">{formatRupiahShort(a.amount)}</p>}
                    <p className="text-[10px] text-muted-foreground">{formatTime(a.created_at)}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mt-4">
        {/* recent transactions */}
        <Card className="p-5 lg:col-span-2" data-testid="recent-sales">
          <h3 className="font-head font-bold mb-4">Transaksi Terbaru</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted-foreground border-b border-border">
                  <th className="pb-2 font-semibold">Waktu</th><th className="pb-2 font-semibold">Kasir</th>
                  <th className="pb-2 font-semibold">Pelanggan</th><th className="pb-2 font-semibold">Bayar</th>
                  <th className="pb-2 font-semibold text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {d.recent_sales.length === 0 && <tr><td colSpan={5} className="py-6 text-center text-muted-foreground">Belum ada transaksi hari ini.</td></tr>}
                {d.recent_sales.map((s) => (
                  <tr key={s.id} className="border-b border-border/60 last:border-0">
                    <td className="py-2.5">{formatTime(s.created_at)}</td>
                    <td className="py-2.5">{s.cashier_name}</td>
                    <td className="py-2.5 text-muted-foreground">{s.customer_name}</td>
                    <td className="py-2.5"><Badge variant="secondary" className="text-[10px]">{PAYMENT_LABELS[s.payment_method] || s.payment_method}</Badge></td>
                    <td className="py-2.5 text-right font-bold tabular">{formatRupiah(s.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* critical stock + prices */}
        <div className="space-y-4">
          <Card className="p-5" data-testid="critical-stock">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="w-4 h-4 text-warning" />
              <h3 className="font-head font-bold">Stok Kritis</h3>
            </div>
            {d.critical_stock.length === 0 ? (
              <p className="text-sm text-success">Semua stok aman.</p>
            ) : (
              <div className="space-y-2">
                {d.critical_stock.map((c) => (
                  <div key={c.name} className="flex items-center justify-between">
                    <span className="text-sm">{c.name}</span>
                    <Badge className="bg-warning text-warning-foreground">{formatWeight(c.stock_kg)}</Badge>
                  </div>
                ))}
              </div>
            )}
          </Card>
          <Card className="p-5" data-testid="price-list">
            <div className="flex items-center gap-2 mb-3">
              <Package className="w-4 h-4 text-primary" />
              <h3 className="font-head font-bold">Harga Ayam Terkini</h3>
            </div>
            <div className="space-y-2">
              {d.prices.map((p) => (
                <div key={p.name} className="flex items-center justify-between text-sm">
                  <span className="truncate">{p.name}</span>
                  <span className="font-bold tabular">{formatRupiah(p.price_kg)}<span className="text-muted-foreground font-normal">/kg</span></span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
