import React, { useCallback, useEffect, useState } from "react";
import api, { apiError } from "@/lib/api";
import { useRealtimeReload } from "@/lib/hooks";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  formatRupiah, formatRupiahShort, formatWeight, formatNumber, formatPct,
  formatTime, PAYMENT_LABELS,
} from "@/lib/format";
import {
  BookCheck, Wallet, TrendingUp, Boxes, FileDown, Loader2, Lock, Eye,
  ReceiptText, HandCoins, AlertTriangle,
} from "lucide-react";

const todayISO = () => {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};

function Stat({ icon: Icon, label, value, sub, tone = "primary", testid }) {
  const tones = {
    primary: "bg-primary/10 text-primary",
    success: "bg-success/10 text-success",
    warning: "bg-warning/20 text-warning",
    chart4: "bg-chart-4/10 text-chart-4",
  };
  return (
    <Card className="p-5" data-testid={testid}>
      <div className="flex items-start justify-between gap-2">
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

function Section({ title, children, hint }) {
  return (
    <Card className="p-5 mt-4">
      <div className="flex items-baseline justify-between gap-3 mb-3">
        <h3 className="font-head font-bold text-base">{title}</h3>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
      {children}
    </Card>
  );
}

function Row({ label, value, strong, tone }) {
  const toneCls = tone === "pos" ? "text-success" : tone === "neg" ? "text-destructive" : "";
  return (
    <div className="flex items-center justify-between py-2 border-b border-border last:border-0">
      <span className={`text-sm ${strong ? "font-semibold" : "text-muted-foreground"}`}>{label}</span>
      <span className={`text-sm tabular ${strong ? "font-bold" : ""} ${toneCls}`}>{value}</span>
    </div>
  );
}

function PdfButton({ path, testid, label = "Unduh PDF" }) {
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
      a.download = m ? m[1] : "tutup-buku.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      toast.success("PDF tutup buku terunduh");
    } catch {
      toast.error("Gagal membuat PDF. Periksa koneksi lalu coba lagi.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button variant="outline" size="sm" data-testid={testid} disabled={busy} onClick={click}>
      {busy ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <FileDown className="w-4 h-4 mr-1" />}
      {busy ? "Menyiapkan..." : label}
    </Button>
  );
}

// Rincian angka satu hari — dipakai untuk pratinjau maupun melihat riwayat.
export function ClosingDetail({ d }) {
  if (!d) return null;
  return (
    <div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat testid="closing-omzet" icon={Wallet} label="Omzet" value={formatRupiah(d.omzet)}
          sub={`${formatNumber(d.txn_count)} transaksi${d.cancelled_count ? ` · ${d.cancelled_count} batal` : ""}`} />
        <Stat testid="closing-laba" icon={TrendingUp} label="Laba Kotor" value={formatRupiah(d.gross_profit)}
          sub={`HPP ${formatRupiahShort(d.hpp)} · margin ${formatPct(d.margin)}`} tone="success" />
        <Stat testid="closing-net" icon={ReceiptText} label="Laba Bersih" value={formatRupiah(d.net_profit)}
          sub={`Beban operasional ${formatRupiahShort(d.opex)}`} tone="warning" />
        <Stat testid="closing-stock" icon={Boxes} label="Nilai Stok Sisa" value={formatRupiah(d.stock_value)}
          sub={`${d.stock_items?.length || 0} produk bersisa`} tone="chart4" />
      </div>

      <div className="grid lg:grid-cols-2 gap-4 mt-4">
        <Card className="p-5">
          <h3 className="font-head font-bold text-base mb-2">Uang Masuk & Piutang</h3>
          <Row label="Kas dari penjualan" value={formatRupiah(d.kas_dari_penjualan)} />
          <Row label="Pembayaran piutang masuk" value={formatRupiah(d.bayar_piutang_masuk)} />
          <Row label="Total uang masuk" value={formatRupiah(d.kas_masuk_total)} strong tone="pos" />
          <Row label="Piutang baru hari ini" value={formatRupiah(d.piutang_baru)} tone={d.piutang_baru ? "neg" : undefined} />
          <Row label="Total piutang belum lunas" value={formatRupiah(d.receivable_outstanding)} />
          <Row label="Total hutang supplier belum lunas" value={formatRupiah(d.payable_outstanding)} />
        </Card>
        <Card className="p-5">
          <h3 className="font-head font-bold text-base mb-2">Volume & Pengeluaran</h3>
          <Row label="Berat terjual" value={formatWeight(d.weight)} />
          <Row label="Ayam terjual" value={`${formatNumber(d.ekor)} ekor`} />
          <Row label="Potongan terjual" value={`${formatNumber(d.pcs)} pcs`} />
          <Row label="Diskon diberikan" value={formatRupiah(d.diskon)} />
          <Row label={`Pembelian ayam (${formatNumber(d.purchase?.count)} nota)`}
            value={formatRupiah(d.purchase?.total_modal)} />
          <Row label="Total pengeluaran tercatat" value={formatRupiah(d.expense_total)} strong />
        </Card>
      </div>

      {!!(d.by_method || []).length && (
        <Section title="Rincian per Metode Pembayaran">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-xs text-muted-foreground">
                <tr className="text-left">
                  <th className="px-3 py-2 font-semibold">Metode</th>
                  <th className="px-3 py-2 font-semibold text-right">Transaksi</th>
                  <th className="px-3 py-2 font-semibold text-right">Penjualan</th>
                  <th className="px-3 py-2 font-semibold text-right">Uang Diterima</th>
                </tr>
              </thead>
              <tbody>
                {d.by_method.map((m) => (
                  <tr key={m.method} className="border-t border-border">
                    <td className="px-3 py-2 font-semibold">{PAYMENT_LABELS[m.method] || m.method}</td>
                    <td className="px-3 py-2 text-right tabular">{formatNumber(m.count)}</td>
                    <td className="px-3 py-2 text-right tabular">{formatRupiah(m.total)}</td>
                    <td className="px-3 py-2 text-right tabular font-semibold">{formatRupiah(m.kas)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {!!(d.top_products || []).length && (
        <Section title="Produk Terjual Hari Ini">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-xs text-muted-foreground">
                <tr className="text-left">
                  <th className="px-3 py-2 font-semibold">Produk</th>
                  <th className="px-3 py-2 font-semibold text-right">Kg</th>
                  <th className="px-3 py-2 font-semibold text-right">Ekor</th>
                  <th className="px-3 py-2 font-semibold text-right">Pcs</th>
                  <th className="px-3 py-2 font-semibold text-right">Penjualan</th>
                  <th className="px-3 py-2 font-semibold text-right">Laba</th>
                </tr>
              </thead>
              <tbody>
                {d.top_products.map((p) => (
                  <tr key={p.name} className="border-t border-border">
                    <td className="px-3 py-2 font-semibold">{p.name}</td>
                    <td className="px-3 py-2 text-right tabular">{formatNumber(p.qty_kg, 2)}</td>
                    <td className="px-3 py-2 text-right tabular">{formatNumber(p.qty_ekor)}</td>
                    <td className="px-3 py-2 text-right tabular">{formatNumber(p.qty_pcs)}</td>
                    <td className="px-3 py-2 text-right tabular">{formatRupiah(p.penjualan)}</td>
                    <td className="px-3 py-2 text-right tabular text-success">{formatRupiah(p.laba)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {!!(d.stock_items || []).length && (
        <Section title="Stok Sisa Akhir Hari"
          hint="Nilai stok dihitung dari berat (kg) + satuan pcs agar tidak dobel dengan stok ekor">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-xs text-muted-foreground">
                <tr className="text-left">
                  <th className="px-3 py-2 font-semibold">Produk</th>
                  <th className="px-3 py-2 font-semibold text-right">Ekor</th>
                  <th className="px-3 py-2 font-semibold text-right">Berat</th>
                  <th className="px-3 py-2 font-semibold text-right">Pcs</th>
                  <th className="px-3 py-2 font-semibold text-right">Berat/ekor</th>
                  <th className="px-3 py-2 font-semibold text-right">Nilai</th>
                </tr>
              </thead>
              <tbody>
                {d.stock_items.map((s) => (
                  <tr key={s.name} className="border-t border-border">
                    <td className="px-3 py-2 font-semibold">{s.name}</td>
                    <td className="px-3 py-2 text-right tabular">{formatNumber(s.stock_ekor)}</td>
                    <td className="px-3 py-2 text-right tabular">{formatWeight(s.stock_kg)}</td>
                    <td className="px-3 py-2 text-right tabular">{formatNumber(s.stock_pcs)}</td>
                    <td className="px-3 py-2 text-right tabular">{s.avg_weight ? `${formatNumber(s.avg_weight, 2)} kg` : "-"}</td>
                    <td className="px-3 py-2 text-right tabular font-semibold">{formatRupiah(s.value)}</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-border bg-muted/30">
                  <td className="px-3 py-2 font-bold" colSpan={5}>TOTAL NILAI STOK</td>
                  <td className="px-3 py-2 text-right tabular font-bold">{formatRupiah(d.stock_value)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {!!(d.expenses_by_category || []).length && (
        <Section title="Beban per Kategori">
          {d.expenses_by_category.map((e) => (
            <Row key={e.category} label={e.category} value={formatRupiah(e.amount)} />
          ))}
        </Section>
      )}

      {d.notes ? (
        <Section title="Catatan Owner"><p className="text-sm">{d.notes}</p></Section>
      ) : null}
    </div>
  );
}

export default function Closing() {
  const { user } = useAuth();
  const isOwner = user.role === "owner";
  const [date, setDate] = useState(todayISO());
  const [preview, setPreview] = useState(null);
  const [history, setHistory] = useState([]);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [detail, setDetail] = useState(null);

  const load = useCallback(async () => {
    try {
      const [p, h] = await Promise.all([
        api.get(`/daily-closing/preview?date=${date}`),
        api.get("/daily-closing"),
      ]);
      setPreview(p.data);
      setHistory(h.data || []);
    } catch (e) {
      toast.error(apiError(e));
    }
  }, [date]);

  useEffect(() => { load(); }, [load]);
  useRealtimeReload(["closing", "dashboard"], load);

  const tutupBuku = async () => {
    if (preview?.already_closed &&
      !window.confirm(`Tanggal ${date} sudah pernah ditutup. Tutup ulang dengan angka terbaru?`)) return;
    setBusy(true);
    try {
      await api.post("/daily-closing", { date, notes });
      toast.success(`Tutup buku ${date} tersimpan`);
      setNotes("");
      load();
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setBusy(false);
    }
  };

  const openDetail = async (id) => {
    try {
      const r = await api.get(`/daily-closing/${id}`);
      setDetail(r.data);
    } catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="bam-fade">
      <PageHeader title="Tutup Buku Harian" subtitle="Rekap omzet, laba, stok sisa & piutang — simpan sebagai arsip harian"
        testid="closing-page"
        actions={
          <div className="flex items-center gap-2">
            <Input type="date" value={date} data-testid="closing-date"
              onChange={(e) => setDate(e.target.value)} className="w-[150px]" />
            {isOwner && (
              <Button data-testid="closing-submit" disabled={busy} onClick={tutupBuku}>
                {busy ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <BookCheck className="w-4 h-4 mr-1" />}
                {preview?.already_closed ? "Tutup Ulang" : "Tutup Buku"}
              </Button>
            )}
          </div>
        } />

      {preview?.already_closed && (
        <Card className="p-4 mb-4 border-success/40 bg-success/5" data-testid="closing-status">
          <div className="flex items-center gap-2 text-sm">
            <Lock className="w-4 h-4 text-success shrink-0" />
            <span>
              Tanggal <b>{preview.date}</b> sudah ditutup oleh <b>{preview.closed_by}</b> pada {formatTime(preview.closed_at)}
              {preview.version > 1 ? ` (versi ${preview.version})` : ""}. Angka di bawah adalah kondisi terkini.
            </span>
          </div>
        </Card>
      )}

      {!preview ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <div key={`sk-${i}`} className="h-28 rounded-xl bg-muted animate-pulse" />)}
        </div>
      ) : (
        <>
          {preview.txn_count === 0 && (
            <Card className="p-4 mb-4 border-warning/40 bg-warning/5">
              <div className="flex items-center gap-2 text-sm">
                <AlertTriangle className="w-4 h-4 text-warning shrink-0" />
                Belum ada transaksi pada tanggal ini.
              </div>
            </Card>
          )}
          <ClosingDetail d={preview} />

          {isOwner && (
            <Card className="p-5 mt-4">
              <Label className="text-xs">Catatan owner (opsional, tersimpan di arsip & PDF)</Label>
              <Textarea data-testid="closing-notes" value={notes} onChange={(e) => setNotes(e.target.value)}
                placeholder="Contoh: kas fisik cocok, sisa ayam 8 ekor dipindah ke freezer."
                className="mt-1.5" rows={2} />
            </Card>
          )}
        </>
      )}

      <Section title="Riwayat Tutup Buku" hint={`${history.length} arsip tersimpan`}>
        {history.length === 0 ? (
          <p className="text-sm text-muted-foreground">Belum ada tutup buku tersimpan.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-xs text-muted-foreground">
                <tr className="text-left">
                  <th className="px-3 py-2 font-semibold">Tanggal</th>
                  <th className="px-3 py-2 font-semibold text-right">Omzet</th>
                  <th className="px-3 py-2 font-semibold text-right">Laba Bersih</th>
                  <th className="px-3 py-2 font-semibold text-right">Uang Masuk</th>
                  <th className="px-3 py-2 font-semibold text-right">Nilai Stok</th>
                  <th className="px-3 py-2 font-semibold">Ditutup oleh</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {history.map((c) => (
                  <tr key={c.id} data-testid={`closing-row-${c.date}`} className="border-t border-border hover:bg-accent/40">
                    <td className="px-3 py-2 font-semibold">
                      {c.date}
                      {c.version > 1 && <Badge variant="secondary" className="ml-2 text-[10px]">v{c.version}</Badge>}
                    </td>
                    <td className="px-3 py-2 text-right tabular">{formatRupiah(c.omzet)}</td>
                    <td className="px-3 py-2 text-right tabular text-success font-semibold">{formatRupiah(c.net_profit)}</td>
                    <td className="px-3 py-2 text-right tabular">{formatRupiah(c.kas_masuk_total)}</td>
                    <td className="px-3 py-2 text-right tabular">{formatRupiah(c.stock_value)}</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">{c.closed_by}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button variant="ghost" size="sm" data-testid={`closing-view-${c.date}`} onClick={() => openDetail(c.id)}>
                          <Eye className="w-4 h-4" />
                        </Button>
                        <PdfButton path={`/daily-closing/${c.id}/pdf`} testid={`closing-pdf-${c.date}`} label="PDF" />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {detail && (
        <Dialog open onOpenChange={() => setDetail(null)}>
          <DialogContent className="bg-popover max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <HandCoins className="w-5 h-5 text-primary" />
                Tutup Buku {detail.date}
              </DialogTitle>
            </DialogHeader>
            <ClosingDetail d={detail} />
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
