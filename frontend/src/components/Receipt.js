import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { formatRupiah, formatWeight, formatTime, formatDate, PAYMENT_LABELS } from "@/lib/format";
import { printReceipt, waShareReceipt } from "@/lib/receipt";
import { Printer, Share2, Check, WifiOff } from "lucide-react";

export default function Receipt({ sale, phone, offline, onClose }) {
  if (!sale) return null;
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover max-w-sm">
        <DialogHeader>
          <DialogTitle>Struk Penjualan</DialogTitle>
          <DialogDescription>Cetak atau bagikan struk ke pelanggan via WhatsApp.</DialogDescription>
        </DialogHeader>

        <div data-testid="receipt-preview" className="rounded-lg border border-dashed border-border p-4 font-mono text-xs bg-background max-h-[45vh] overflow-y-auto">
          <div className="text-center">
            <p className="font-bold text-sm">Berkah Ayam Mili</p>
            <p className="text-[10px] text-muted-foreground">Ayam Potong & Fillet</p>
          </div>
          {offline && (
            <div className="flex items-center justify-center gap-1 text-[10px] text-warning mt-1">
              <WifiOff className="w-3 h-3" /> Tersimpan offline · akan disinkron otomatis
            </div>
          )}
          <div className="border-t border-dashed my-2" />
          <div className="flex justify-between"><span>{formatDate(sale.created_at)}</span><span>{formatTime(sale.created_at)}</span></div>
          <div className="flex justify-between"><span>Kasir</span><span>{sale.cashier_name}</span></div>
          <div className="flex justify-between"><span>Pembeli</span><span>{sale.customer_name}</span></div>
          <div className="border-t border-dashed my-2" />
          {sale.items.map((it, i) => (
            <div key={i} className="mb-1.5">
              <p>{it.name}</p>
              <div className="flex justify-between text-muted-foreground">
                <span>{it.unit === "kg" ? formatWeight(it.qty, 3) : `${it.qty} ekor`} x {formatRupiah(it.price)}</span>
                <span>{formatRupiah(it.subtotal)}</span>
              </div>
            </div>
          ))}
          <div className="border-t border-dashed my-2" />
          <div className="flex justify-between font-bold text-sm"><span>TOTAL</span><span>{formatRupiah(sale.total)}</span></div>
          <div className="flex justify-between"><span>Bayar ({PAYMENT_LABELS[sale.payment_method] || sale.payment_method})</span><span>{formatRupiah(sale.paid)}</span></div>
          {sale.change > 0 && <div className="flex justify-between"><span>Kembali</span><span>{formatRupiah(sale.change)}</span></div>}
          {sale.receivable > 0 && <div className="flex justify-between text-warning"><span>Piutang</span><span>{formatRupiah(sale.receivable)}</span></div>}
          <div className="border-t border-dashed my-2" />
          <p className="text-center text-muted-foreground">Terima kasih atas kunjungan Anda</p>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Button variant="outline" data-testid="receipt-print" onClick={() => printReceipt(sale)}>
            <Printer className="w-4 h-4 mr-1" /> Cetak
          </Button>
          <Button variant="outline" data-testid="receipt-wa" onClick={() => waShareReceipt(sale, "Berkah Ayam Mili", phone)} className="text-success border-success/40 hover:bg-success/10">
            <Share2 className="w-4 h-4 mr-1" /> WhatsApp
          </Button>
        </div>
        <Button data-testid="receipt-done" onClick={onClose} className="w-full">
          <Check className="w-4 h-4 mr-1" /> Selesai
        </Button>
      </DialogContent>
    </Dialog>
  );
}
