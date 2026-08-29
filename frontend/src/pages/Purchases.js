import { useState } from "react";
import api, { apiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { formatRupiah, formatWeight, formatDate } from "@/lib/format";
import { Plus, Trash2 } from "lucide-react";

export default function Purchases() {
  const { data, reload } = useFetch("/purchases");
  const { data: suppliers } = useFetch("/suppliers");
  const { data: products } = useFetch("/products");
  const [open, setOpen] = useState(false);

  return (
    <div className="bam-fade">
      <PageHeader title="Pembelian Ayam" subtitle="Catat ayam masuk dari supplier"
        actions={<Button data-testid="add-purchase" onClick={() => setOpen(true)}><Plus className="w-4 h-4 mr-1" /> Pembelian Baru</Button>} />
      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground">
            <th className="px-4 py-3">Tanggal</th><th className="px-4 py-3">Supplier</th><th className="px-4 py-3 text-right">Berat</th>
            <th className="px-4 py-3 text-right">Modal Efektif/kg</th><th className="px-4 py-3 text-right">Total Modal</th><th className="px-4 py-3">Status</th>
          </tr></thead>
          <tbody>
            {(data || []).map((p) => (
              <tr key={p.id} data-testid={`purchase-${p.id}`} className="border-t border-border hover:bg-accent/40">
                <td className="px-4 py-3">{formatDate(p.date)}</td>
                <td className="px-4 py-3 font-medium">{p.supplier_name}</td>
                <td className="px-4 py-3 text-right tabular">{formatWeight(p.total_weight)}</td>
                <td className="px-4 py-3 text-right tabular">{formatRupiah(p.effective_cost_kg)}</td>
                <td className="px-4 py-3 text-right tabular font-semibold">{formatRupiah(p.total_modal)}</td>
                <td className="px-4 py-3"><Badge className={p.payment_status === "lunas" ? "bg-success text-white" : "bg-warning text-warning-foreground"}>{p.payment_status}</Badge></td>
              </tr>
            ))}
            {(data || []).length === 0 && <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">Belum ada pembelian.</td></tr>}
          </tbody>
        </table>
      </Card>
      {open && <PurchaseDialog suppliers={suppliers || []} products={(products || []).filter((p) => !["sampingan", "fillet", "potongan"].includes(p.category))} onClose={() => setOpen(false)} onSaved={() => { setOpen(false); reload(); }} />}
    </div>
  );
}

function PurchaseDialog({ suppliers, products, onClose, onSaved }) {
  const [supplier, setSupplier] = useState("");
  const [items, setItems] = useState([{ _k: Math.random(), product_id: "", ekor: 0, total_weight: 0, total_price: 0 }]);
  const [transport, setTransport] = useState(0);
  const [other, setOther] = useState(0);
  const [paid, setPaid] = useState(0);
  const [busy, setBusy] = useState(false);

  const setItem = (i, k, v) => setItems((arr) => arr.map((it, idx) => idx === i ? { ...it, [k]: v } : it));
  const birdValue = items.reduce((s, it) => s + Number(it.total_price), 0);
  const totalEkor = items.reduce((s, it) => s + Number(it.ekor), 0);
  const totalModal = birdValue + Number(transport) + Number(other);
  const totalWeight = items.reduce((s, it) => s + Number(it.total_weight), 0);

  const save = async () => {
    if (!supplier) return toast.error("Pilih supplier");
    const valid = items.filter((it) => it.product_id && Number(it.total_weight) > 0);
    if (!valid.length) return toast.error("Tambahkan minimal 1 item");
    setBusy(true);
    try {
      await api.post("/purchases", {
        supplier_id: supplier,
        items: valid.map((it) => ({ product_id: it.product_id, ekor: Number(it.ekor), total_weight: Number(it.total_weight), total_price: Number(it.total_price) })),
        transport_cost: Number(transport), other_cost: Number(other), paid: Number(paid),
      });
      toast.success("Pembelian tersimpan, stok bertambah"); onSaved();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>Pembelian Baru</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div><Label className="text-xs">Supplier</Label>
            <Select value={supplier} onValueChange={setSupplier}>
              <SelectTrigger data-testid="pur-supplier" className="mt-1"><SelectValue placeholder="Pilih supplier" /></SelectTrigger>
              <SelectContent className="bg-popover">{suppliers.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label className="text-xs">Item Ayam</Label>
            {items.map((it, i) => (
              <div key={it._k} className="grid grid-cols-12 gap-2 items-end">
                <div className="col-span-4"><Select value={it.product_id} onValueChange={(v) => setItem(i, "product_id", v)}>
                  <SelectTrigger data-testid={`pur-item-${i}`}><SelectValue placeholder="Produk" /></SelectTrigger>
                  <SelectContent className="bg-popover">{products.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent>
                </Select></div>
                <div className="col-span-2"><Input placeholder="Ekor" type="number" value={it.ekor} onChange={(e) => setItem(i, "ekor", e.target.value)} className="tabular" /></div>
                <div className="col-span-3"><Input placeholder="Berat kg" type="number" value={it.total_weight} onChange={(e) => setItem(i, "total_weight", e.target.value)} className="tabular" /></div>
                <div className="col-span-2"><Input placeholder="Total Rp" type="number" value={it.total_price} onChange={(e) => setItem(i, "total_price", e.target.value)} className="tabular" /></div>
                <div className="col-span-1"><Button variant="ghost" size="icon" onClick={() => setItems((a) => a.filter((_, idx) => idx !== i))}><Trash2 className="w-4 h-4 text-destructive" /></Button></div>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={() => setItems((a) => [...a, { _k: Math.random(), product_id: "", ekor: 0, total_weight: 0, total_price: 0 }])}><Plus className="w-4 h-4 mr-1" /> Item</Button>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div><Label className="text-xs">Transport</Label><Input type="number" value={transport} onChange={(e) => setTransport(e.target.value)} className="mt-1 tabular" /></div>
            <div><Label className="text-xs">Biaya Lain</Label><Input type="number" value={other} onChange={(e) => setOther(e.target.value)} className="mt-1 tabular" /></div>
            <div><Label className="text-xs">Dibayar</Label><Input data-testid="pur-paid" type="number" value={paid} onChange={(e) => setPaid(e.target.value)} className="mt-1 tabular" /></div>
          </div>
          <div className="rounded-lg bg-accent p-3 text-sm space-y-1">
            <div className="flex justify-between"><span>Nilai Ayam (total dibayar)</span><span className="tabular">{formatRupiah(birdValue)}</span></div>
            <div className="flex justify-between font-bold"><span>Total Modal</span><span className="tabular">{formatRupiah(totalModal)}</span></div>
            <div className="flex justify-between text-muted-foreground"><span>Perkiraan Harga/kg (otomatis)</span><span className="tabular">{formatRupiah(totalWeight ? totalModal / totalWeight : 0)}</span></div>
            <div className="flex justify-between text-muted-foreground"><span>Modal Efektif/ekor</span><span className="tabular">{formatRupiah(totalEkor ? totalModal / totalEkor : 0)}</span></div>
          </div>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Batal</Button><Button data-testid="save-purchase" disabled={busy} onClick={save}>{busy ? "Menyimpan..." : "Simpan"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
