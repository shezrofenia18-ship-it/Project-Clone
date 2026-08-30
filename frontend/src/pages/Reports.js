import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { useRealtimeReload } from "@/lib/hooks";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { formatRupiah, formatWeight, formatPct, formatDate, PAYMENT_LABELS } from "@/lib/format";
import { Printer, Download, FileDown, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from "recharts";

function todayISO() { return new Date().toISOString().slice(0, 10); }
function daysAgoISO(n) { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().slice(0, 10); }

// PDF dibuat di server (reportlab) supaya hasil cetaknya rapi & seragam,
// lengkap dengan kop toko, periode, dan kolom tanda tangan.
function PdfButton({ path, filename, testid }) {
  const [busy, setBusy] = useState(false);
  const click = async () => {
    setBusy(true);
    try {
      const r = await api.get(path, { responseType: "blob" });
      const cd = r.headers["content-disposition"] || "";
      const m = /filename="?([^";]+)"?/.exec(cd);
      const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = m ? m[1] : filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      toast.success("Laporan PDF terunduh");
    } catch {
      toast.error("Gagal membuat PDF. Periksa koneksi lalu coba lagi.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button variant="outline" size="sm" data-testid={testid} disabled={busy} onClick={click}>
      {busy ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <FileDown className="w-4 h-4 mr-1" />}
      {busy ? "Menyiapkan..." : "Unduh PDF"}
    </Button>
  );
}

function csvExport(filename, rows) {
  const sep = ";";
  const csv = rows
    .map((r) => r.map((c) => {
      if (typeof c === "number") return String(c);
      const s = String(c ?? "");
      return /[";\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    }).join(sep))
    .join("\r\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

function currentMonth() { return new Date().toISOString().slice(0, 7); }

export default function Reports() {
  const [start, setStart] = useState(daysAgoISO(30));
  const [end, setEnd] = useState(todayISO());
  const [pl, setPl] = useState(null);
  const [sales, setSales] = useState(null);
  const [stock, setStock] = useState(null);
  const [tab, setTab] = useState("pl");
  // Laporan bulanan berdiri sendiri (pemilih bulan), untuk arsip pembukuan toko.
  const [month, setMonth] = useState(currentMonth());
  const [monthly, setMonthly] = useState(null);

  const load = useCallback(() => {
    api.get(`/reports/profit-loss?start=${start}&end=${end}`).then((r) => setPl(r.data));
    api.get(`/reports/sales?start=${start}&end=${end}`).then((r) => setSales(r.data));
    api.get(`/reports/stock`).then((r) => setStock(r.data));
  }, [start, end]);
  useEffect(() => { load(); }, [load]);

  const loadMonthly = useCallback(() => {
    if (!month) return;
    api.get(`/reports/monthly?month=${month}`)
      .then((r) => setMonthly(r.data))
      .catch(() => toast.error("Gagal memuat laporan bulanan"));
  }, [month]);
  useEffect(() => { loadMonthly(); }, [loadMonthly]);

  // Laporan ikut segar begitu ada penjualan/pembelian/pengeluaran baru.
  useRealtimeReload(["sales", "expenses", "incomes", "purchases", "stock", "dashboard"],
    useCallback(() => { load(); loadMonthly(); }, [load, loadMonthly]));

  return (
    <div className="bam-fade">
      <PageHeader title="Laporan" subtitle="Laba rugi, penjualan & nilai stok"
        actions={<Button variant="outline" data-testid="print-btn" onClick={() => window.print()}><Printer className="w-4 h-4 mr-1" /> Cetak</Button>} />
      {tab !== "monthly" && (
        <Card className="p-4 mb-4 flex flex-wrap items-end gap-3">
          <div><Label className="text-xs">Dari</Label><Input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="mt-1" /></div>
          <div><Label className="text-xs">Sampai</Label><Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="mt-1" /></div>
          <Button data-testid="apply-filter" onClick={load}>Terapkan</Button>
        </Card>
      )}

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex-wrap h-auto"><TabsTrigger value="pl" data-testid="tab-pl">Laba Rugi</TabsTrigger><TabsTrigger value="monthly" data-testid="tab-monthly">Bulanan (Arsip)</TabsTrigger><TabsTrigger value="sales" data-testid="tab-sales">Penjualan</TabsTrigger><TabsTrigger value="stock" data-testid="tab-stock">Stok</TabsTrigger></TabsList>

        <TabsContent value="monthly">
          <Card className="p-4 mb-4 flex flex-wrap items-end gap-3">
            <div>
              <Label className="text-xs">Bulan</Label>
              <Input type="month" data-testid="monthly-month" value={month} max={currentMonth()}
                onChange={(e) => setMonth(e.target.value)} className="mt-1 w-44" />
            </div>
            <Button variant="outline" data-testid="monthly-this" onClick={() => setMonth(currentMonth())}>Bulan Ini</Button>
            <div className="ml-auto flex gap-2">
              <PdfButton testid="pdf-monthly" path={`/reports/monthly/pdf?month=${month}`}
                filename={`laba-rugi-bulanan_${month}.pdf`} />
              {monthly && (
                <Button variant="outline" size="sm" data-testid="export-monthly"
                  onClick={() => csvExport(`laba-rugi-bulanan_${month}.csv`, [
                    ["Tanggal", "Transaksi", "Berat (kg)", "Ekor", "Omzet (Rp)", "HPP (Rp)", "Laba Kotor (Rp)", "Beban (Rp)", "Laba Bersih (Rp)"],
                    ...(monthly.daily || []).map((d) => [formatDate(d.date), d.txn_count, d.weight, d.ekor,
                      Math.round(d.omzet), Math.round(d.hpp), Math.round(d.gross_profit), Math.round(d.opex), Math.round(d.net_profit)]),
                    ["TOTAL", monthly.txn_count, monthly.weight, monthly.ekor, Math.round(monthly.omzet),
                      Math.round(monthly.hpp), Math.round(monthly.gross_profit), Math.round(monthly.opex), Math.round(monthly.net_profit)],
                  ])}><Download className="w-4 h-4 mr-1" /> Export CSV</Button>
              )}
            </div>
          </Card>

          {monthly && (
            <>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
                <MonthStat label="Omzet" value={formatRupiah(monthly.omzet)} growth={monthly.growth?.omzet} prev={monthly.prev?.label} testid="m-omzet" />
                <MonthStat label="Laba Kotor" value={formatRupiah(monthly.gross_profit)} sub={`Margin ${formatPct(monthly.gross_margin)}`} testid="m-gross" />
                <MonthStat label="Laba Bersih Usaha" value={formatRupiah(monthly.net_profit)} growth={monthly.growth?.net_profit} prev={monthly.prev?.label} testid="m-net" />
                <MonthStat label="Transaksi" value={`${monthly.txn_count}`} sub={`${formatWeight(monthly.weight)} · ${monthly.ekor} ekor`} testid="m-txn" />
              </div>

              <div className="grid lg:grid-cols-2 gap-4 mb-4">
                <Card className="p-6">
                  <h3 className="font-head font-bold mb-1">Laba Rugi {monthly.label}</h3>
                  <p className="text-xs text-muted-foreground mb-4">
                    {formatDate(monthly.start)} — {formatDate(monthly.end)} · {monthly.active_days} hari ada transaksi
                    · rata-rata {formatRupiah(monthly.avg_omzet_per_day)}/hari
                  </p>
                  <div className="space-y-2.5 text-sm" data-testid="monthly-pl">
                    <Row label="Total Omzet" value={formatRupiah(monthly.omzet)} />
                    <Row label="HPP" value={`- ${formatRupiah(monthly.hpp)}`} tone="text-muted-foreground" />
                    <div className="border-t border-border pt-2.5"><Row label="Laba Kotor" value={formatRupiah(monthly.gross_profit)} bold tone="text-success" /></div>
                    <Row label="Biaya Operasional" value={`- ${formatRupiah(monthly.opex)}`} tone="text-muted-foreground" />
                    <div className="border-t border-border pt-2.5"><Row label="Laba Bersih Usaha" value={formatRupiah(monthly.net_profit)} bold tone="text-primary" /></div>
                    <div className="flex flex-wrap gap-2 pt-2">
                      <Badge variant="secondary">Margin Kotor {formatPct(monthly.gross_margin)}</Badge>
                      <Badge variant="secondary">Margin Bersih {formatPct(monthly.net_margin)}</Badge>
                    </div>
                    <div className="mt-4 pt-3 border-t border-dashed border-border">
                      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Arus Kas Bulan Ini</p>
                      <Row label="Uang Masuk" value={formatRupiah(monthly.cash_in)} tone="text-success" />
                      <Row label="Uang Keluar (termasuk beli ayam)" value={`- ${formatRupiah(monthly.cash_out)}`} tone="text-muted-foreground" />
                      <div className="border-t border-border pt-2.5 mt-2">
                        <Row label="Uang Bersih (Kas)" value={formatRupiah(monthly.net_cash)} bold
                          tone={monthly.net_cash < 0 ? "text-destructive" : "text-success"} />
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-2">
                        Modal ayam bulan ini {formatRupiah(monthly.modal_value)} · piutang baru {formatRupiah(monthly.piutang_baru)}.
                      </p>
                    </div>
                  </div>
                </Card>

                <Card className="p-6">
                  <h3 className="font-head font-bold mb-4">Dibanding {monthly.prev?.label || "Bulan Lalu"}</h3>
                  <div className="space-y-2.5 text-sm" data-testid="monthly-compare">
                    <Row label={`Omzet ${monthly.prev?.label || ""}`} value={formatRupiah(monthly.prev?.omzet || 0)} />
                    <Row label={`Laba Bersih ${monthly.prev?.label || ""}`} value={formatRupiah(monthly.prev?.net_profit || 0)} />
                    <Row label={`Transaksi ${monthly.prev?.label || ""}`} value={`${monthly.prev?.txn_count || 0}`} />
                    <div className="border-t border-border pt-3 flex flex-wrap gap-2">
                      <GrowthBadge label="Omzet" value={monthly.growth?.omzet} />
                      <GrowthBadge label="Laba Bersih" value={monthly.growth?.net_profit} />
                    </div>
                  </div>
                  <h3 className="font-head font-bold mt-6 mb-3">Beban per Kategori</h3>
                  <div className="space-y-1.5 text-sm">
                    {(monthly.expenses_by_category || []).length === 0 && <p className="text-muted-foreground text-sm">Tidak ada beban tercatat.</p>}
                    {(monthly.expenses_by_category || []).map((e) => (
                      <div key={e.category} className="flex justify-between">
                        <span className="text-muted-foreground">{e.category}</span>
                        <span className="tabular">{formatRupiah(e.amount)}</span>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>

              <Card className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground">
                    <th className="px-4 py-3">Tanggal</th><th className="px-4 py-3 text-right">Trx</th>
                    <th className="px-4 py-3 text-right">Berat</th><th className="px-4 py-3 text-right">Ekor</th>
                    <th className="px-4 py-3 text-right">Omzet</th><th className="px-4 py-3 text-right">HPP</th>
                    <th className="px-4 py-3 text-right">Laba Kotor</th><th className="px-4 py-3 text-right">Beban</th>
                    <th className="px-4 py-3 text-right">Laba Bersih</th>
                  </tr></thead>
                  <tbody data-testid="monthly-daily">
                    {(monthly.daily || []).map((d) => (
                      <tr key={d.date} className="border-t border-border">
                        <td className="px-4 py-2.5 whitespace-nowrap">{formatDate(d.date)}</td>
                        <td className="px-4 py-2.5 text-right tabular">{d.txn_count}</td>
                        <td className="px-4 py-2.5 text-right tabular">{formatWeight(d.weight)}</td>
                        <td className="px-4 py-2.5 text-right tabular">{d.ekor}</td>
                        <td className="px-4 py-2.5 text-right tabular">{formatRupiah(d.omzet)}</td>
                        <td className="px-4 py-2.5 text-right tabular text-muted-foreground">{formatRupiah(d.hpp)}</td>
                        <td className="px-4 py-2.5 text-right tabular text-success">{formatRupiah(d.gross_profit)}</td>
                        <td className="px-4 py-2.5 text-right tabular text-muted-foreground">{formatRupiah(d.opex)}</td>
                        <td className="px-4 py-2.5 text-right tabular font-semibold">{formatRupiah(d.net_profit)}</td>
                      </tr>
                    ))}
                    {(monthly.daily || []).length === 0 && (
                      <tr><td colSpan={9} className="px-4 py-8 text-center text-muted-foreground">Belum ada aktivitas pada bulan ini.</td></tr>
                    )}
                  </tbody>
                  <tfoot><tr className="border-t-2 border-border font-bold">
                    <td className="px-4 py-3">TOTAL</td>
                    <td className="px-4 py-3 text-right tabular">{monthly.txn_count}</td>
                    <td className="px-4 py-3 text-right tabular">{formatWeight(monthly.weight)}</td>
                    <td className="px-4 py-3 text-right tabular">{monthly.ekor}</td>
                    <td className="px-4 py-3 text-right tabular">{formatRupiah(monthly.omzet)}</td>
                    <td className="px-4 py-3 text-right tabular">{formatRupiah(monthly.hpp)}</td>
                    <td className="px-4 py-3 text-right tabular">{formatRupiah(monthly.gross_profit)}</td>
                    <td className="px-4 py-3 text-right tabular">{formatRupiah(monthly.opex)}</td>
                    <td className="px-4 py-3 text-right tabular">{formatRupiah(monthly.net_profit)}</td>
                  </tr></tfoot>
                </table>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="pl">
          {pl && (
            <>
              <div className="flex justify-end mb-3">
                <PdfButton testid="pdf-pl" path={`/reports/profit-loss/pdf?start=${start}&end=${end}`}
                  filename={`laba-rugi_${start}_${end}.pdf`} />
              </div>
              <div className="grid lg:grid-cols-2 gap-4">
              <Card className="p-6">
                <h3 className="font-head font-bold mb-4">Ringkasan Laba Rugi</h3>
                <div className="space-y-2.5 text-sm">
                  <Row label="Total Omzet" value={formatRupiah(pl.omzet)} />
                  <Row label="HPP" value={`- ${formatRupiah(pl.hpp)}`} tone="text-muted-foreground" />
                  <div className="border-t border-border pt-2.5"><Row label="Laba Kotor" value={formatRupiah(pl.gross_profit)} bold tone="text-success" /></div>
                  <Row label="Biaya Operasional" value={`- ${formatRupiah(pl.opex)}`} tone="text-muted-foreground" />
                  <div className="border-t border-border pt-2.5"><Row label="Laba Bersih Usaha" value={formatRupiah(pl.net_profit)} bold tone="text-primary" /></div>
                  <div className="flex gap-2 pt-2"><Badge variant="secondary">Margin Kotor {formatPct(pl.gross_margin)}</Badge><Badge variant="secondary">Margin Bersih {formatPct(pl.net_margin)}</Badge></div>
                  {/* Arus kas: di sinilah uang beli ayam & pelunasan hutang dihitung,
                      supaya biaya ayam tidak dikurangi dua kali dari laba. */}
                  <div className="mt-4 pt-3 border-t border-dashed border-border" data-testid="pl-cashflow">
                    <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Arus Kas Periode Ini</p>
                    <Row label="Uang Masuk" value={formatRupiah(pl.cash_in)} tone="text-success" />
                    <Row label="Uang Keluar (termasuk beli ayam)" value={`- ${formatRupiah(pl.cash_out)}`} tone="text-muted-foreground" />
                    <div className="border-t border-border pt-2.5 mt-2">
                      <Row label="Uang Bersih (Kas)" value={formatRupiah(pl.net_cash)} bold
                        tone={pl.net_cash < 0 ? "text-destructive" : "text-success"} />
                    </div>
                    <p className="text-[11px] text-muted-foreground mt-2">
                      Modal ayam periode ini {formatRupiah(pl.modal_value)} · dibayar tunai {formatRupiah(pl.modal_cash)}.
                      Biaya ayam sudah termasuk di HPP, jadi tidak dikurangi lagi dari laba.
                    </p>
                  </div>
                </div>
              </Card>
              <Card className="p-6">
                <h3 className="font-head font-bold mb-4">Pengeluaran per Kategori</h3>
                {pl.expenses_by_category?.length ? (
                  <ResponsiveContainer width="100%" height={240}>
                    <PieChart>
                      <Pie data={pl.expenses_by_category} dataKey="amount" nameKey="category" cx="50%" cy="50%" outerRadius={90}>
                        {pl.expenses_by_category.map((entry, i) => <Cell key={entry.category} fill={`hsl(var(--chart-${(i % 5) + 1}))`} />)}
                      </Pie>
                      <Tooltip formatter={(v) => formatRupiah(v)} /><Legend />
                    </PieChart>
                  </ResponsiveContainer>
                ) : <p className="text-sm text-muted-foreground">Tidak ada data.</p>}
              </Card>
            </div>
            </>
          )}
        </TabsContent>

        <TabsContent value="sales">
          {sales && (
            <>
              <div className="flex justify-end gap-2 mb-3">
                <PdfButton testid="pdf-sales" path={`/reports/sales/pdf?start=${start}&end=${end}`}
                  filename={`penjualan_${start}_${end}.pdf`} />
                <Button variant="outline" size="sm" data-testid="export-sales" onClick={() => csvExport(`penjualan_${start}_${end}.csv`, [["Tanggal", "Kasir", "Pelanggan", "Metode", "Jumlah Item", "Total (Rp)", "HPP (Rp)", "Laba (Rp)"], ...sales.sales.map((s) => [formatDate(s.date), s.cashier_name, s.customer_name, PAYMENT_LABELS[s.payment_method] || s.payment_method, (s.items || []).length, Math.round(s.total), Math.round(s.total_hpp || 0), Math.round((s.total || 0) - (s.total_hpp || 0))])])}><Download className="w-4 h-4 mr-1" /> Export CSV</Button>
              </div>
              <div className="grid sm:grid-cols-3 gap-4 mb-4">
                <Card className="p-4"><p className="text-xs text-muted-foreground">Total Transaksi</p><p className="font-head font-extrabold text-2xl">{sales.count}</p></Card>
                <Card className="p-4"><p className="text-xs text-muted-foreground">Total Penjualan</p><p className="font-head font-extrabold text-2xl tabular">{formatRupiah(sales.total)}</p></Card>
                <Card className="p-4"><p className="text-xs text-muted-foreground mb-1">Per Metode</p>{sales.by_method.map((m) => <div key={m.method} className="flex justify-between text-xs"><span>{PAYMENT_LABELS[m.method] || m.method}</span><span className="tabular">{formatRupiah(m.total)}</span></div>)}</Card>
              </div>
              <Card className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground"><th className="px-4 py-3">Tanggal</th><th className="px-4 py-3">Kasir</th><th className="px-4 py-3">Pelanggan</th><th className="px-4 py-3">Metode</th><th className="px-4 py-3 text-right">Total</th></tr></thead>
                  <tbody>{sales.sales.slice(0, 100).map((s) => (
                    <tr key={s.id} className="border-t border-border"><td className="px-4 py-2.5">{formatDate(s.date)}</td><td className="px-4 py-2.5">{s.cashier_name}</td><td className="px-4 py-2.5 text-muted-foreground">{s.customer_name}</td><td className="px-4 py-2.5"><Badge variant="secondary" className="text-[10px]">{PAYMENT_LABELS[s.payment_method] || s.payment_method}</Badge></td><td className="px-4 py-2.5 text-right tabular font-semibold">{formatRupiah(s.total)}</td></tr>
                  ))}</tbody>
                </table>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="stock">
          {stock && (
            <>
              <div className="flex justify-end gap-2 mb-3">
                <PdfButton testid="pdf-stock" path="/reports/stock/pdf" filename="nilai-stok.pdf" />
                <Button variant="outline" size="sm" data-testid="export-stock" onClick={() => csvExport("nilai_stok.csv", [["Produk", "Kategori", "Ekor", "Kg", "Pcs", "HPP/kg (Rp)", "Nilai Stok (Rp)"], ...stock.items.map((s) => [s.name, s.category, s.stock_ekor, s.stock_kg, s.stock_pcs || 0, Math.round(s.hpp_kg || 0), Math.round(s.value || 0)])])}><Download className="w-4 h-4 mr-1" /> Export CSV</Button>
              </div>
              <Card className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground"><th className="px-4 py-3">Produk</th><th className="px-4 py-3 text-right">Ekor</th><th className="px-4 py-3 text-right">Kg</th><th className="px-4 py-3 text-right">HPP/kg</th><th className="px-4 py-3 text-right">Nilai Stok</th></tr></thead>
                <tbody>{stock.items.map((s) => (
                  <tr key={s.name} className="border-t border-border"><td className="px-4 py-2.5 font-medium">{s.name}</td><td className="px-4 py-2.5 text-right tabular">{s.stock_ekor}</td><td className="px-4 py-2.5 text-right tabular">{formatWeight(s.stock_kg)}</td><td className="px-4 py-2.5 text-right tabular">{formatRupiah(s.hpp_kg)}</td><td className="px-4 py-2.5 text-right tabular font-semibold">{formatRupiah(s.value)}</td></tr>
                ))}</tbody>
                <tfoot><tr className="border-t-2 border-border font-bold"><td className="px-4 py-3" colSpan={4}>Total Nilai Stok</td><td className="px-4 py-3 text-right tabular">{formatRupiah(stock.total_value)}</td></tr></tfoot>
              </table>
            </Card>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Row({ label, value, bold, tone }) {
  return <div className="flex justify-between"><span className={bold ? "font-bold" : "text-muted-foreground"}>{label}</span><span className={`tabular ${bold ? "font-bold" : ""} ${tone || ""}`}>{value}</span></div>;
}

function GrowthBadge({ label, value }) {
  if (value === null || value === undefined) {
    return <Badge variant="secondary">{label}: belum ada pembanding</Badge>;
  }
  const naik = value >= 0;
  return (
    <Badge className={naik ? "bg-success text-white" : "bg-destructive text-white"}>
      {label} {naik ? "naik" : "turun"} {formatPct(Math.abs(value))}
    </Badge>
  );
}

function MonthStat({ label, value, sub, growth, prev, testid }) {
  let info = sub;
  if (growth !== null && growth !== undefined) {
    info = `${growth >= 0 ? "+" : ""}${formatPct(growth)} vs ${prev || "bulan lalu"}`;
  } else if (!sub && prev) {
    info = `belum ada pembanding (${prev})`;
  }
  const tone = growth === null || growth === undefined ? "text-muted-foreground"
    : (growth >= 0 ? "text-success" : "text-destructive");
  return (
    <Card className="p-4" data-testid={testid}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-head font-extrabold text-xl tabular mt-0.5">{value}</p>
      {info && <p className={`text-[11px] mt-0.5 ${growth === null || growth === undefined ? "text-muted-foreground" : tone}`}>{info}</p>}
    </Card>
  );
}
