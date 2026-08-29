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

export default function Reports() {
  const [start, setStart] = useState(daysAgoISO(30));
  const [end, setEnd] = useState(todayISO());
  const [pl, setPl] = useState(null);
  const [sales, setSales] = useState(null);
  const [stock, setStock] = useState(null);

  const load = useCallback(() => {
    api.get(`/reports/profit-loss?start=${start}&end=${end}`).then((r) => setPl(r.data));
    api.get(`/reports/sales?start=${start}&end=${end}`).then((r) => setSales(r.data));
    api.get(`/reports/stock`).then((r) => setStock(r.data));
  }, [start, end]);
  useEffect(() => { load(); }, [load]);
  // Laporan ikut segar begitu ada penjualan/pembelian/pengeluaran baru.
  useRealtimeReload(["sales", "expenses", "incomes", "purchases", "stock", "dashboard"], load);

  return (
    <div className="bam-fade">
      <PageHeader title="Laporan" subtitle="Laba rugi, penjualan & nilai stok"
        actions={<Button variant="outline" data-testid="print-btn" onClick={() => window.print()}><Printer className="w-4 h-4 mr-1" /> Cetak</Button>} />
      <Card className="p-4 mb-4 flex flex-wrap items-end gap-3">
        <div><Label className="text-xs">Dari</Label><Input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="mt-1" /></div>
        <div><Label className="text-xs">Sampai</Label><Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="mt-1" /></div>
        <Button data-testid="apply-filter" onClick={load}>Terapkan</Button>
      </Card>

      <Tabs defaultValue="pl">
        <TabsList><TabsTrigger value="pl" data-testid="tab-pl">Laba Rugi</TabsTrigger><TabsTrigger value="sales" data-testid="tab-sales">Penjualan</TabsTrigger><TabsTrigger value="stock" data-testid="tab-stock">Stok</TabsTrigger></TabsList>

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
