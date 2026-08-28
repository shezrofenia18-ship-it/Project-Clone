import React from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useOffline } from "@/context/OfflineContext";
import { formatRupiah, formatTime, formatDate, PAYMENT_LABELS } from "@/lib/format";
import { RefreshCw, Trash2, CloudOff, CheckCircle2, AlertTriangle, RotateCw } from "lucide-react";

export default function PendingSales({ onClose }) {
  const { queue, pending, failed, syncing, online, lastSync, syncNow, remove, retry } = useOffline();

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover max-w-lg max-h-[85vh] flex flex-col" data-testid="pending-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CloudOff className="w-5 h-5 text-primary" /> Transaksi Menunggu Sinkron
          </DialogTitle>
          <DialogDescription>
            Transaksi yang dibuat saat internet mati tersimpan di perangkat ini dan dikirim otomatis
            begitu koneksi kembali. Data tidak akan hilang meski aplikasi ditutup.
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2 flex-wrap text-xs">
          <Badge variant="secondary" data-testid="pending-count">{pending} menunggu</Badge>
          {failed > 0 && <Badge variant="destructive" data-testid="failed-count">{failed} ditolak</Badge>}
          <span className={`font-semibold ${online ? "text-success" : "text-destructive"}`}>
            {online ? "Koneksi tersedia" : "Sedang offline"}
          </span>
          {lastSync && (
            <span className="text-muted-foreground">· Sinkron terakhir {formatTime(lastSync)}</span>
          )}
        </div>

        <div className="flex-1 overflow-y-auto no-scrollbar space-y-2 -mx-1 px-1" data-testid="pending-list">
          {queue.length === 0 && (
            <div className="py-10 flex flex-col items-center text-center text-muted-foreground">
              <CheckCircle2 className="w-9 h-9 mb-2 text-success opacity-70" />
              <p className="text-sm font-semibold text-foreground">Semua transaksi sudah tersinkron</p>
              <p className="text-xs mt-0.5">Tidak ada antrean offline.</p>
            </div>
          )}

          {queue.map((item) => {
            const s = item.summary || {};
            const isFailed = item.status === "failed";
            return (
              <div
                key={item.id}
                data-testid={`pending-item-${item.id}`}
                className={`p-3 rounded-lg border ${isFailed ? "border-destructive/40 bg-destructive/5" : "border-border bg-accent/50"}`}
              >
                <div className="flex items-start gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold truncate">{s.customer_name || "Umum"}</p>
                      {isFailed ? (
                        <Badge variant="destructive" className="text-[10px] px-1.5 py-0">Ditolak</Badge>
                      ) : (
                        <Badge variant="secondary" className="text-[10px] px-1.5 py-0">Menunggu</Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground tabular mt-0.5">
                      {formatDate(item.queued_at)} {formatTime(item.queued_at)} · {s.item_count || 0} item
                      {s.payment_method ? ` · ${PAYMENT_LABELS[s.payment_method] || s.payment_method}` : ""}
                    </p>
                    {isFailed && (
                      <p className="text-xs text-destructive mt-1 flex items-start gap-1">
                        <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px" />
                        <span>{item.error || "Ditolak server"}</span>
                      </p>
                    )}
                  </div>
                  <p className="text-sm font-bold tabular shrink-0">{formatRupiah(s.total || 0)}</p>
                </div>

                <div className="flex items-center gap-2 mt-2">
                  {isFailed && (
                    <Button
                      size="sm" variant="outline" className="h-7 text-xs"
                      data-testid={`pending-retry-${item.id}`}
                      onClick={() => retry(item.id)}
                    >
                      <RotateCw className="w-3.5 h-3.5 mr-1" /> Coba Lagi
                    </Button>
                  )}
                  <Button
                    size="sm" variant="ghost"
                    className="h-7 text-xs text-destructive hover:bg-destructive/10 ml-auto"
                    data-testid={`pending-remove-${item.id}`}
                    onClick={() => remove(item.id)}
                  >
                    <Trash2 className="w-3.5 h-3.5 mr-1" /> Hapus
                  </Button>
                </div>
              </div>
            );
          })}
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>Tutup</Button>
          <Button
            data-testid="pending-sync-now"
            disabled={syncing || pending === 0}
            onClick={syncNow}
            className="font-semibold"
          >
            <RefreshCw className={`w-4 h-4 mr-1.5 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? "Menyinkronkan..." : "Sinkron Sekarang"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
