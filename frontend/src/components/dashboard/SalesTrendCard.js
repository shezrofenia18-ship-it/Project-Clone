// Grafik penjualan: harian (7 hari) atau tren bulanan (3/6/12/24 bulan).
// Komponen ini yang memuat sendiri data bulanannya, supaya halaman dashboard
// tidak perlu ikut mengurus state & pemanggilan API-nya.
import { useCallback, useEffect, useState } from "react";
import api from "@/lib/api";
import { useRealtimeReload } from "@/lib/hooks";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatRupiah, formatRupiahShort, formatPct } from "@/lib/format";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
  ComposedChart, Bar, Line, Legend,
} from "recharts";
import { ArrowUpRight, ArrowDownRight, Loader2 } from "lucide-react";
import {
  TICK_SM, TICK_MD, TOOLTIP_STYLE, AREA_MARGIN, BAR_RADIUS, LEGEND_STYLE, jtFmt, shortFmt,
} from "./chartTheme";

// Rentang bulan yang bisa dipilih owner pada grafik tren.
const MONTH_OPTIONS = [3, 6, 12, 24];

function TrendBit({ label, value, tone = "", note }) {
  return (
    <div className="rounded-lg border border-border p-2.5 min-w-0">
      <p className="text-[11px] text-muted-foreground truncate">{label}</p>
      <p className={`font-bold text-sm tabular truncate ${tone}`}>{value}</p>
      {note && <p className="text-[10px] text-muted-foreground truncate">{note}</p>}
    </div>
  );
}

function GrowthBadge({ value, testid }) {
  if (value === null || value === undefined) {
    return <Badge variant="secondary" className="text-[10px]" data-testid={testid}>Belum ada pembanding</Badge>;
  }
  const up = value >= 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <Badge data-testid={testid}
      className={`text-[10px] gap-0.5 ${up ? "bg-success/15 text-success hover:bg-success/15" : "bg-destructive/15 text-destructive hover:bg-destructive/15"}`}>
      <Icon className="w-3 h-3" />{up ? "+" : ""}{formatPct(value)}
    </Badge>
  );
}

function RangeToggle({ range, months, onRange, onMonths }) {
  const btn = (active) =>
    `px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${active ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground"}`;
  return (
    <div className="flex items-center gap-2">
      {range === "bulanan" && (
        <select data-testid="months-select" value={months} aria-label="Jumlah bulan"
          onChange={(e) => onMonths(Number(e.target.value))}
          className="h-8 rounded-lg border border-border bg-background px-2 text-xs font-semibold">
          {MONTH_OPTIONS.map((m) => <option key={m} value={m}>{m} bulan</option>)}
        </select>
      )}
      <div className="inline-flex rounded-lg border border-border bg-muted/40 p-0.5" data-testid="chart-range-toggle">
        <button type="button" data-testid="range-7d" onClick={() => onRange("7d")} className={btn(range === "7d")}>
          7 Hari
        </button>
        <button type="button" data-testid="range-12m" onClick={() => onRange("bulanan")} className={btn(range === "bulanan")}>
          Bulanan
        </button>
      </div>
    </div>
  );
}

function DailyChart({ chart }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={chart} margin={AREA_MARGIN}>
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
  );
}

function MonthlyGrowth({ summary }) {
  const kosong = summary.growth_omzet === null && summary.growth_laba_bersih === null;
  return (
    <div className="flex items-center flex-wrap gap-2 mt-3 mb-2">
      {kosong ? (
        <span className="text-xs text-muted-foreground" data-testid="growth-empty">
          Belum ada bulan pembanding — pertumbuhan mulai terlihat bulan depan
        </span>
      ) : (
        <>
          <span className="text-xs text-muted-foreground">Omzet vs {summary.prev_month || "bulan lalu"}</span>
          <GrowthBadge value={summary.growth_omzet} testid="growth-omzet" />
          <span className="text-xs text-muted-foreground ml-2">Laba bersih</span>
          <GrowthBadge value={summary.growth_laba_bersih} testid="growth-laba" />
        </>
      )}
    </div>
  );
}

function MonthlyChart({ monthly, months, dimmed }) {
  const s = monthly.summary;
  return (
    <div data-testid="monthly-chart" className={dimmed ? "opacity-60 transition-opacity" : "transition-opacity"}>
      <ResponsiveContainer width="100%" height={230}>
        <ComposedChart data={monthly.series} margin={AREA_MARGIN}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
          <XAxis dataKey="label" tick={TICK_SM} stroke="hsl(var(--muted-foreground))" interval={0} angle={-30} textAnchor="end" height={48} />
          <YAxis tick={TICK_SM} stroke="hsl(var(--muted-foreground))" tickFormatter={shortFmt} />
          <Tooltip formatter={(v) => formatRupiah(v)} contentStyle={TOOLTIP_STYLE} />
          <Legend wrapperStyle={LEGEND_STYLE} />
          <Bar dataKey="omzet" name="Omzet" fill="hsl(var(--primary))" radius={BAR_RADIUS} maxBarSize={26} />
          <Line type="monotone" dataKey="laba_kotor" name="Laba Kotor" stroke="hsl(var(--success))" strokeWidth={2.5} dot={false} />
          <Line type="monotone" dataKey="laba_bersih" name="Laba Bersih" stroke="hsl(var(--chart-4))" strokeWidth={2} strokeDasharray="5 3" dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
      <MonthlyGrowth summary={s} />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2" data-testid="monthly-summary">
        <TrendBit label={`Bulan ini (${s.this_month || "-"})`} value={formatRupiahShort(s.this_omzet)}
          note={`Laba bersih ${formatRupiahShort(s.this_laba_bersih)}`} />
        <TrendBit label="Bulan terbaik" value={s.best_month || "-"} tone="text-success"
          note={formatRupiahShort(s.best_omzet)} />
        <TrendBit label="Rata-rata omzet/bulan" value={formatRupiahShort(s.avg_omzet)}
          note={`${s.active_months} bulan berjalan`} />
        <TrendBit label={`Total ${months} bulan`} value={formatRupiahShort(s.total_omzet)}
          note={`Laba bersih ${formatRupiahShort(s.total_laba_bersih)}`} />
      </div>
    </div>
  );
}

export default function SalesTrendCard({ chart }) {
  // Tren bulanan dimuat hanya saat owner menekan tombol "Bulanan" (hemat data).
  const [range, setRange] = useState("7d");
  const [months, setMonths] = useState(12);
  const [monthly, setMonthly] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadMonthly = useCallback(async (n) => {
    setLoading(true);
    try {
      const r = await api.get(`/dashboard/monthly?months=${n}`);
      setMonthly(r.data);
    } catch (e) {
      if (process.env.NODE_ENV !== "production") console.error("tren bulanan gagal:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (range === "bulanan") loadMonthly(months);
  }, [range, months, loadMonthly]);

  // Kalau ada transaksi baru, tren bulanan yang sedang dilihat ikut disegarkan.
  const refresh = useCallback(() => {
    if (range === "bulanan") loadMonthly(months);
  }, [range, months, loadMonthly]);
  useRealtimeReload(["dashboard"], refresh);

  return (
    <Card className="p-5 lg:col-span-2" data-testid="sales-chart">
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <h3 className="font-head font-bold">
          {range === "7d" ? "Grafik Penjualan 7 Hari" : `Tren ${months} Bulan`}
        </h3>
        <RangeToggle range={range} months={months} onRange={setRange} onMonths={setMonths} />
      </div>

      {range === "7d" && <DailyChart chart={chart} />}
      {range === "bulanan" && !monthly && (
        <div className="h-[220px] flex items-center justify-center text-sm text-muted-foreground gap-2" data-testid="monthly-loading">
          <Loader2 className="w-4 h-4 animate-spin" /> Memuat tren bulanan…
        </div>
      )}
      {range === "bulanan" && monthly && (
        <MonthlyChart monthly={monthly} months={months} dimmed={loading} />
      )}
    </Card>
  );
}
