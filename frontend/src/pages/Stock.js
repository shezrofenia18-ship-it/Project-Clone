import { useState, useCallback } from "react";
import api, { apiError } from "@/lib/api";
import { useFetch, useRealtimeReload } from "@/lib/hooks";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "sonner";
import { formatWeight, formatNumber, CATEGORY_LABELS, formatTime, formatDate } from "@/lib/format";
import { SlidersHorizontal } from "lucide-react";

// "mati" hanya dipertahankan agar riwayat lama tetap terbaca; pilihan barunya
// adalah "salah_potong" (permintaan owner).
const MOVE_LABELS = { pembelian: "Pembelian", penjualan: "Penjualan", pemotongan: "Pemotongan", produksi: "Produksi", retur: "Retur", penyesuaian: "Penyesuaian", rusak: "Rusak", salah_potong: "Salah Potong", mati: "Mati", susut: "Susut" };
const MOVE_TONE = { pembelian: "bg-success/15 text-success", produksi: "bg-success/15 text-success", penjualan: "bg-primary/10 text-primary", retur: "bg-chart-4/10 text-chart-4", pemotongan: "bg-warning/20 text-warning", salah_potong: "bg-destructive/10 text-destructive" };

export default function Stock() {
  const { data: products, reload } = useFetch("/products");
  const { data: moves, reload: reloadMoves } = useFetch("/stock-movements");
  const [adj, setAdj] = useState(false);

  // Stok bergerak seketika saat kasir menjual / ayam masuk dari device lain.
  const reloadAll = useCallback(() => { reload(); reloadMoves(); }, [reload, reloadMoves]);
  useRealtimeReload(["stock", "products"], reloadAll);

  const active = (products || []).filter((p) => p.active !== false);
  // Nilai uang (rupiah) TIDAK ditampilkan di halaman Stok — permintaan owner supaya
  // modal/HPP tidak terlihat di layar operasional. Nilai stok tetap ada di
  // Laporan > Stok (khusus owner/admin) dan di PDF Laporan Nilai Stok.
  const totalKg = active.reduce((s, p) => s + (p.stock_kg || 0), 0);
  const totalEkor = active.reduce((s, p) => s + (p.stock_ekor || 0), 0);

  return (
    <div className="bam-fade">
      <PageHeader title="Stok Ayam"
        subtitle={`Total stok: ${formatWeight(totalKg)} · ${formatNumber(totalEkor)} ekor`}
        actions={<Button data-testid="add-adjustment" onClick={() => setAdj(true)}><SlidersHorizontal className="w-4 h-4 mr-1" /> Penyesuaian Stok</Button>} />

      <Tabs defaultValue="stok">
        <TabsList><TabsTrigger value="stok" data-testid="tab-stok">Stok Saat Ini</TabsTrigger><TabsTrigger value="movement" data-testid="tab-movement">Pergerakan Stok</TabsTrigger></TabsList>
        <TabsContent value="stok">
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {active.map((p) => {
              const low = p.min_stock_kg > 0 && p.stock_kg <= p.min_stock_kg;
              return (
                <Card key={p.id} className="p-4 bam-card-hover" data-testid={`stock-${p.id}`}>
                  <div className="flex items-center justify-between">
                    <p className="font-semibold">{p.name}</p>
                    <Badge variant="secondary" className="text-[10px]">{CATEGORY_LABELS[p.category]}</Badge>
                  </div>
                  <div className="flex items-end gap-4 mt-3">
                    <div><p className="text-[11px] text-muted-foreground">Berat</p><p className={`font-head font-extrabold text-xl tabular ${low ? "text-warning" : ""}`}>{formatWeight(p.stock_kg)}</p></div>
                    {p.units.includes("ekor") && <div><p className="text-[11px] text-muted-foreground">Ekor</p><p className="font-head font-extrabold text-xl tabular">{formatNumber(p.stock_ekor)}</p></div>}
                    {p.units.includes("pcs") && <div><p className="text-[11px] text-muted-foreground">Pcs</p><p className="font-head font-extrabold text-xl tabular">{formatNumber(p.stock_pcs)}</p></div>}
                  </div>
                  {low && <Badge className="mt-2 bg-warning text-warning-foreground">Stok menipis</Badge>}
                </Card>
              );
            })}
          </div>
        </TabsContent>
        <TabsContent value="movement">
          <Card className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground">
                <th className="px-4 py-3">Waktu</th><th className="px-4 py-3">Produk</th><th className="px-4 py-3">Jenis</th>
                <th className="px-4 py-3 text-right">Qty</th><th className="px-4 py-3 text-right">Stok Sesudah</th><th className="px-4 py-3">User</th>
              </tr></thead>
              <tbody>
                {(moves || []).slice(0, 200).map((m) => (
                  <tr key={m.id} className="border-t border-border">
                    <td className="px-4 py-2.5 text-muted-foreground">{formatDate(m.created_at)} {formatTime(m.created_at)}</td>
                    <td className="px-4 py-2.5 font-medium">{m.product_name}</td>
                    <td className="px-4 py-2.5"><Badge className={MOVE_TONE[m.type] || "bg-muted text-foreground"}>{MOVE_LABELS[m.type] || m.type}</Badge></td>
                    <td className="px-4 py-2.5 text-right tabular">{m.qty_kg ? `${m.qty_kg > 0 ? "+" : ""}${formatWeight(m.qty_kg, 3)}` : ""}{m.qty_ekor ? ` ${m.qty_ekor > 0 ? "+" : ""}${m.qty_ekor} ekor` : ""}</td>
                    <td className="px-4 py-2.5 text-right tabular">{formatWeight(m.after_kg)}</td>
                    <td className="px-4 py-2.5 text-muted-foreground">{m.user}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </TabsContent>
      </Tabs>
      {adj && <AdjustDialog products={active} onClose={() => setAdj(false)} onSaved={() => { setAdj(false); reload(); reloadMoves(); }} />}
    </div>
  );
}

function AdjustDialog({ products, onClose, onSaved }) {
  const [f, setF] = useState({ product_id: "", delta_kg: 0, delta_ekor: 0, type: "penyesuaian", reason: "" });
  const [busy, setBusy] = useState(false);
  const save = async () => {
    if (!f.product_id || !f.reason) return toast.error("Lengkapi produk & alasan");
    setBusy(true);
    try {
      await api.post("/stock-adjustments", { ...f, delta_kg: Number(f.delta_kg), delta_ekor: Number(f.delta_ekor) });
      toast.success("Penyesuaian tersimpan"); onSaved();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover">
        <DialogHeader><DialogTitle>Penyesuaian Stok</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div><Label className="text-xs">Produk</Label>
            <Select value={f.product_id} onValueChange={(v) => setF({ ...f, product_id: v })}>
              <SelectTrigger data-testid="adj-product" className="mt-1"><SelectValue placeholder="Pilih produk" /></SelectTrigger>
              <SelectContent className="bg-popover">{products.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div><Label className="text-xs">Jenis</Label>
            <Select value={f.type} onValueChange={(v) => setF({ ...f, type: v })}>
              <SelectTrigger data-testid="adj-type" className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-popover">
                <SelectItem value="penyesuaian">Penyesuaian</SelectItem><SelectItem value="rusak">Ayam Rusak</SelectItem>
                <SelectItem value="salah_potong">Salah Potong</SelectItem><SelectItem value="susut">Susut</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-xs">Perubahan Kg (+/-)</Label><Input data-testid="adj-kg" type="number" value={f.delta_kg} onChange={(e) => setF({ ...f, delta_kg: e.target.value })} className="mt-1 tabular" /></div>
            <div><Label className="text-xs">Perubahan Ekor (+/-)</Label><Input type="number" value={f.delta_ekor} onChange={(e) => setF({ ...f, delta_ekor: e.target.value })} className="mt-1 tabular" /></div>
          </div>
          <div><Label className="text-xs">Alasan</Label><Input data-testid="adj-reason" value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} className="mt-1" /></div>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Batal</Button><Button data-testid="save-adjustment" disabled={busy} onClick={save}>Simpan</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
