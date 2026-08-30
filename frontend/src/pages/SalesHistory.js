import { useState, useMemo } from "react";
import api, { apiError } from "@/lib/api";
import { useFetch, useRealtimeReload } from "@/lib/hooks";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { formatRupiah, formatQtyUnit, formatTime, formatDate, PAYMENT_LABELS, todayWib, isRecent } from "@/lib/format";
import { useAuth } from "@/context/AuthContext";
import { printReceipt, waShareReceipt } from "@/lib/receipt";
import { useStore } from "@/lib/hooks";
import { Ban, Receipt, Printer, Share2 } from "lucide-react";

export default function SalesHistory() {
  const { user } = useAuth();
  const isKasir = user.role === "kasir";
  // Kasir hanya boleh melihat 7 hari terakhir (dibatasi juga di server). Kalender
  // dibatasi supaya kasir tidak bingung memilih tanggal yang hasilnya selalu kosong.
  const minDate = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() - 6);
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  }, []);
  // Default HARI INI (acuan WIB, sama dengan backend) supaya transaksi yang baru
  // dibuat langsung terlihat dan tidak tertimbun riwayat hari-hari sebelumnya.
  const [date, setDate] = useState(todayWib());
  const { data, reload } = useFetch(date ? `/sales?date=${date}` : "/sales", [date]);
  const store = useStore();
  const [detail, setDetail] = useState(null);
  const canCancel = ["owner", "admin"].includes(user.role);
  // Ikut berubah seketika saat ada penjualan baru atau piutang dibayar (status jadi lunas).
  useRealtimeReload(["sales", "receivables"], reload);

  const ringkasan = useMemo(() => {
    const rows = data || [];
    const aktif = rows.filter((s) => s.status !== "batal");
    return {
      jumlah: rows.length,
      batal: rows.length - aktif.length,
      total: aktif.reduce((a, s) => a + (s.total || 0), 0),
    };
  }, [data]);

  const cancel = async (id) => {
    try { await api.post(`/sales/${id}/cancel`); toast.success("Transaksi dibatalkan, stok dikembalikan"); setDetail(null); reload(); }
    catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="bam-fade">
      <PageHeader title="Riwayat Transaksi"
        subtitle={isKasir ? "Penjualan Anda dalam 7 hari terakhir" : "Daftar penjualan"} />

      <Card className="p-3 mb-3 flex flex-wrap items-end gap-3">
        <div>
          <p className="text-xs text-muted-foreground mb-1">Tanggal</p>
          <Input type="date" data-testid="hist-date" className="w-44" value={date}
            min={isKasir ? minDate : undefined} max={isKasir ? todayWib() : undefined}
            onChange={(e) => setDate(e.target.value)} />
        </div>
        <Button variant={date ? "outline" : "default"} size="sm" data-testid="hist-today"
          onClick={() => setDate(todayWib())}>Hari Ini</Button>
        <Button variant={date ? "ghost" : "outline"} size="sm" data-testid="hist-all"
          onClick={() => setDate("")}>{isKasir ? "7 Hari Terakhir" : "Semua Tanggal"}</Button>
        <div className="ml-auto text-right" data-testid="hist-summary">
          <p className="text-xs text-muted-foreground">
            {ringkasan.jumlah} transaksi{ringkasan.batal > 0 ? ` · ${ringkasan.batal} batal` : ""}
          </p>
          <p className="text-lg font-bold tabular">{formatRupiah(ringkasan.total)}</p>
        </div>
      </Card>

      {isKasir && (
        <p className="text-[11px] text-muted-foreground mb-3 -mt-1" data-testid="hist-kasir-note">
          Riwayat kasir dibatasi 7 hari terakhir (sejak {formatDate(minDate)}). Untuk riwayat lebih
          lama, silakan minta ke owner.
        </p>
      )}

      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground">
            <th className="px-4 py-3">Waktu</th><th className="px-4 py-3">Kasir</th><th className="px-4 py-3">Pelanggan</th>
            <th className="px-4 py-3">Metode</th><th className="px-4 py-3 text-right">Total</th><th className="px-4 py-3">Status</th><th className="px-4 py-3"></th>
          </tr></thead>
          <tbody>
            {(data || []).map((s) => (
              <tr key={s.id} data-testid={`sale-${s.id}`}
                className={`border-t border-border hover:bg-accent/40 cursor-pointer ${isRecent(s.created_at) ? "bg-success/10" : ""}`}
                onClick={() => setDetail(s)}>
                <td className="px-4 py-2.5 whitespace-nowrap">
                  {formatDate(s.date)} {formatTime(s.created_at)}
                  {isRecent(s.created_at) && (
                    <Badge className="ml-2 bg-success text-white text-[10px]" data-testid="badge-baru">BARU</Badge>
                  )}
                </td>
                <td className="px-4 py-2.5">{s.cashier_name}</td>
                <td className="px-4 py-2.5 text-muted-foreground">{s.customer_name}</td>
                <td className="px-4 py-2.5"><Badge variant="secondary" className="text-[10px]">{PAYMENT_LABELS[s.payment_method] || s.payment_method}</Badge></td>
                <td className="px-4 py-2.5 text-right tabular font-semibold">{formatRupiah(s.total)}</td>
                <td className="px-4 py-2.5">{s.status === "batal" ? <Badge variant="destructive">Batal</Badge> : <Badge className="bg-success text-white">Selesai</Badge>}</td>
                <td className="px-4 py-2.5"><Receipt className="w-4 h-4 text-muted-foreground" /></td>
              </tr>
            ))}
            {(data || []).length === 0 && <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
              {date ? "Belum ada transaksi pada tanggal ini." : "Belum ada transaksi."}
            </td></tr>}
          </tbody>
        </table>
      </Card>

      {detail && (
        <Dialog open onOpenChange={() => setDetail(null)}>
          <DialogContent className="bg-popover">
            <DialogHeader><DialogTitle>Detail Transaksi</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div className="text-xs text-muted-foreground">{formatDate(detail.date)} {formatTime(detail.created_at)} · {detail.cashier_name} · {detail.customer_name}</div>
              <div className="space-y-1.5">
                {detail.items.map((it, i) => (
                  <div key={`${it.product_id || it.name}-${i}`} className="flex justify-between text-sm">
                    <span>{it.name} <span className="text-muted-foreground">({formatQtyUnit(it.qty, it.unit)} × {formatRupiah(it.price)})</span></span>
                    <span className="tabular font-medium">{formatRupiah(it.subtotal)}</span>
                  </div>
                ))}
              </div>
              <div className="border-t border-border pt-2 space-y-1 text-sm">
                <div className="flex justify-between font-bold"><span>Total</span><span className="tabular">{formatRupiah(detail.total)}</span></div>
                <div className="flex justify-between text-muted-foreground"><span>Bayar ({PAYMENT_LABELS[detail.payment_method]})</span><span className="tabular">{formatRupiah(detail.paid)}</span></div>
                {detail.receivable > 0 && <div className="flex justify-between text-warning"><span>Piutang</span><span className="tabular">{formatRupiah(detail.receivable)}</span></div>}
                {["owner", "admin"].includes(user.role) && <div className="flex justify-between text-success"><span>Laba Kotor (margin {detail.margin_pct}%)</span><span className="tabular">{formatRupiah(detail.gross_profit)}</span></div>}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Button variant="outline" data-testid="hist-print" onClick={() => printReceipt(detail, store)}><Printer className="w-4 h-4 mr-1" /> Cetak Struk</Button>
                <Button variant="outline" data-testid="hist-wa" onClick={() => waShareReceipt(detail, store)} className="text-success border-success/40 hover:bg-success/10"><Share2 className="w-4 h-4 mr-1" /> WhatsApp</Button>
              </div>
              {canCancel && detail.status !== "batal" && (
                <Button data-testid="cancel-sale" variant="destructive" className="w-full" onClick={() => cancel(detail.id)}>
                  <Ban className="w-4 h-4 mr-1" /> Batalkan Transaksi
                </Button>
              )}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
