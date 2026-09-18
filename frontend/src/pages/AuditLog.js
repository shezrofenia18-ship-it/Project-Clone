import { useState } from "react";
import api, { apiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { formatDate, formatTime, formatNumber, formatWeight, formatRupiah, CATEGORY_LABELS } from "@/lib/format";
import { toast } from "sonner";
import { Trash2, RotateCcw } from "lucide-react";

const ACTION_TONE = {
  create: "bg-success/15 text-success", update: "bg-chart-4/10 text-chart-4",
  delete: "bg-destructive/10 text-destructive", delete_permanent: "bg-destructive text-destructive-foreground",
  restore: "bg-success/15 text-success", restore_deleted: "bg-success text-success-foreground", cancel: "bg-destructive/10 text-destructive",
  adjust: "bg-warning/20 text-warning", sync_kg: "bg-warning/20 text-warning",
};
const ACTION_LABELS = {
  delete: "nonaktifkan", delete_permanent: "hapus permanen", restore: "aktifkan kembali",
  restore_deleted: "pulihkan produk", sync_kg: "sinkron kg", cancel: "batalkan",
};

export default function AuditLog() {
  const { data, reload } = useFetch("/audit-logs");
  const { data: deleted, reload: reloadDeleted } = useFetch("/audit-logs/deleted-products");
  const { user } = useAuth();
  const isOwner = user?.role === "owner";
  const deletedCount = (deleted || []).length;
  const [restoring, setRestoring] = useState(null);
  const afterRestore = () => { setRestoring(null); reloadDeleted(); reload(); };

  return (
    <div className="bam-fade">
      <PageHeader title="Audit Log" subtitle="Riwayat aktivitas & perubahan data" />
      <Tabs defaultValue="semua">
        <TabsList>
          <TabsTrigger value="semua" data-testid="tab-audit-all">Semua Aktivitas</TabsTrigger>
          <TabsTrigger value="hapus" data-testid="tab-audit-deleted">
            <Trash2 className="w-3.5 h-3.5 mr-1" /> Produk Dihapus{deletedCount ? ` (${deletedCount})` : ""}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="semua">
          <Card className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground">
                <th className="px-4 py-3">Waktu</th><th className="px-4 py-3">User</th><th className="px-4 py-3">Aksi</th><th className="px-4 py-3">Entitas</th><th className="px-4 py-3">Detail</th>
              </tr></thead>
              <tbody>
                {(data || []).map((a) => (
                  <tr key={a.id} data-testid={`audit-${a.id}`} className="border-t border-border">
                    <td className="px-4 py-2.5 text-muted-foreground whitespace-nowrap">{formatDate(a.created_at)} {formatTime(a.created_at)}</td>
                    <td className="px-4 py-2.5">{a.user} <span className="text-xs text-muted-foreground">({a.role})</span></td>
                    <td className="px-4 py-2.5"><Badge className={ACTION_TONE[a.action] || "bg-muted text-foreground"}>{ACTION_LABELS[a.action] || a.action}</Badge></td>
                    <td className="px-4 py-2.5">{a.entity}</td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground max-w-xs truncate">
                      {a.action === "delete_permanent" && a.before?.name
                        ? <span className="text-foreground font-medium">{a.before.name}</span>
                        : (a.after ? JSON.stringify(a.after) : "")}
                    </td>
                  </tr>
                ))}
                {(data || []).length === 0 && <tr><td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">Belum ada log.</td></tr>}
              </tbody>
            </table>
          </Card>
        </TabsContent>

        <TabsContent value="hapus">
          <p className="text-xs text-muted-foreground mb-3 leading-relaxed">
            Daftar produk yang pernah <b>dihapus permanen</b> dari database — kapan, oleh siapa, beserta stok & riwayat
            yang tercatat saat dihapus. Data ini diambil dari audit log sehingga tetap ada walau produknya sudah tidak ada.
          </p>
          <Card className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground">
                <th className="px-4 py-3">Dihapus pada</th>
                <th className="px-4 py-3">Produk</th>
                <th className="px-4 py-3">Kategori</th>
                <th className="px-4 py-3 text-right">Stok saat dihapus</th>
                <th className="px-4 py-3 text-right">Harga jual/kg</th>
                <th className="px-4 py-3 text-right">Riwayat</th>
                <th className="px-4 py-3">Dihapus oleh</th>
                <th className="px-4 py-3"></th>
              </tr></thead>
              <tbody>
                {(deleted || []).map((r) => {
                  const u = r.usage || {};
                  const hist = (u.sales || 0) + (u.purchases || 0) + (u.productions || 0) + (u.movements || 0);
                  const stockParts = [
                    r.stock_kg ? formatWeight(r.stock_kg) : null,
                    r.stock_ekor ? `${formatNumber(r.stock_ekor)} ekor` : null,
                    r.stock_pcs ? `${formatNumber(r.stock_pcs)} pcs` : null,
                  ].filter(Boolean);
                  return (
                    <tr key={r.id} data-testid={`deleted-product-${r.id}`} className={`border-t border-border ${r.restored_at ? "opacity-70" : ""}`}>
                      <td className="px-4 py-2.5 text-muted-foreground whitespace-nowrap">{formatDate(r.deleted_at)} {formatTime(r.deleted_at)}</td>
                      <td className="px-4 py-2.5 font-semibold">
                        {r.name}
                        {r.was_active === false && <Badge variant="secondary" className="ml-2 text-[10px]">sudah nonaktif</Badge>}
                        {r.restored_at && (
                          <Badge data-testid={`restored-badge-${r.id}`} className="ml-2 text-[10px] bg-success/15 text-success hover:bg-success/15"
                            title={`Dipulihkan ${formatDate(r.restored_at)} ${formatTime(r.restored_at)} oleh ${r.restored_by || "-"}`}>
                            dipulihkan
                          </Badge>
                        )}
                      </td>
                      <td className="px-4 py-2.5"><Badge variant="secondary">{CATEGORY_LABELS[r.category] || r.category || "-"}</Badge></td>
                      <td className="px-4 py-2.5 text-right tabular whitespace-nowrap">{stockParts.length ? stockParts.join(" · ") : <span className="text-muted-foreground">kosong</span>}</td>
                      <td className="px-4 py-2.5 text-right tabular">{formatRupiah(r.price_kg)}</td>
                      <td className="px-4 py-2.5 text-right tabular" title={`Penjualan ${u.sales || 0} · Pembelian ${u.purchases || 0} · Produksi ${u.productions || 0} · Pergerakan ${u.movements || 0}`}>
                        {hist ? `${formatNumber(hist)} catatan` : <span className="text-muted-foreground">tidak ada</span>}
                      </td>
                      <td className="px-4 py-2.5">{r.deleted_by} <span className="text-xs text-muted-foreground">({r.deleted_by_role})</span></td>
                      <td className="px-4 py-2.5 text-right whitespace-nowrap">
                        {isOwner && r.can_restore && (
                          <Button data-testid={`restore-deleted-${r.id}`} size="sm" variant="outline" className="h-7 text-xs" onClick={() => setRestoring(r)}>
                            <RotateCcw className="w-3.5 h-3.5 mr-1" /> Pulihkan
                          </Button>
                        )}
                        {!r.can_restore && !r.restored_at && (
                          <span className="text-[11px] text-muted-foreground" title={r.blocked_reason || "Tidak bisa dipulihkan"}>
                            {r.blocked_reason ? `tidak bisa: ${r.blocked_reason}` : "tidak bisa dipulihkan"}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
                {(deleted || []).length === 0 && (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">Belum ada produk yang dihapus permanen.</td></tr>
                )}
              </tbody>
            </table>
          </Card>
        </TabsContent>
      </Tabs>
      {restoring && <RestoreDeletedDialog row={restoring} onClose={() => setRestoring(null)} onDone={afterRestore} />}
    </div>
  );
}

// Konfirmasi "Pulihkan": produk dibuat ulang dari salinan audit dengan ID yang
// sama, sehingga riwayat lama tersambung kembali. Stok saat dihapus ikut kembali.
function RestoreDeletedDialog({ row, onClose, onDone }) {
  const [busy, setBusy] = useState(false);
  const stockParts = [
    row.stock_kg ? formatWeight(row.stock_kg) : null,
    row.stock_ekor ? `${formatNumber(row.stock_ekor)} ekor` : null,
    row.stock_pcs ? `${formatNumber(row.stock_pcs)} pcs` : null,
  ].filter(Boolean);
  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/audit-logs/deleted-products/${row.id}/restore`);
      toast.success(`"${data.name}" dipulihkan dan aktif kembali`);
      onDone();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent data-testid="restore-deleted-dialog" className="bg-popover max-w-md">
        <DialogHeader><DialogTitle className="flex items-center gap-2"><RotateCcw className="w-4 h-4 text-success" /> Pulihkan "{row.name}"?</DialogTitle></DialogHeader>
        <div className="space-y-3 text-sm">
          <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs space-y-1">
            <div className="flex justify-between gap-3"><span className="text-muted-foreground">Kategori</span><span>{CATEGORY_LABELS[row.category] || row.category || "-"}</span></div>
            <div className="flex justify-between gap-3"><span className="text-muted-foreground">Satuan</span><span>{(row.units || []).join(", ") || "-"}</span></div>
            <div className="flex justify-between gap-3"><span className="text-muted-foreground">Harga jual/kg</span><span className="tabular">{formatRupiah(row.price_kg)}</span></div>
            <div className="flex justify-between gap-3"><span className="text-muted-foreground">Stok yang ikut dipulihkan</span><span className="tabular">{stockParts.length ? stockParts.join(" · ") : "kosong"}</span></div>
            <div className="flex justify-between gap-3"><span className="text-muted-foreground">Dihapus</span><span>{formatDate(row.deleted_at)} {formatTime(row.deleted_at)} · {row.deleted_by}</span></div>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Produk dibuat ulang persis seperti saat dihapus (harga, HPP, berat rata-rata, foto) dengan ID yang sama, sehingga
            riwayat penjualan/pembelian/produksi lama otomatis tersambung kembali. Produk langsung <b>aktif</b> dan muncul lagi di POS, Stok & Produksi.
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>Batal</Button>
          <Button data-testid="restore-deleted-confirm" onClick={run} disabled={busy}>{busy ? "Memulihkan..." : "Pulihkan Produk"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
