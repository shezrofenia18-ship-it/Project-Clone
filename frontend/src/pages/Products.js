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
import { formatRupiah, formatWeight, formatNumber, formatPct, CATEGORY_LABELS } from "@/lib/format";
import { Plus, Pencil } from "lucide-react";

const EMPTY = { name: "", category: "sampingan", units: ["kg"], buy_price_kg: 0, hpp_kg: 0, hpp_ekor: 0, price_kg: 0, price_ekor: 0, stock_kg: 0, stock_ekor: 0, min_stock_kg: 0, min_stock_ekor: 0, image_url: "", is_byproduct: false, active: true };

export default function Products() {
  const { data, reload } = useFetch("/products");
  const [edit, setEdit] = useState(null);

  return (
    <div className="bam-fade">
      <PageHeader title="Produk & Harga" subtitle="Master produk, harga beli, HPP & harga jual"
        actions={<Button data-testid="add-product" onClick={() => setEdit(EMPTY)}><Plus className="w-4 h-4 mr-1" /> Tambah Produk</Button>} />
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr className="text-left text-xs text-muted-foreground">
                <th className="px-4 py-3 font-semibold">Produk</th>
                <th className="px-4 py-3 font-semibold">Kategori</th>
                <th className="px-4 py-3 font-semibold text-right">Harga Beli/kg</th>
                <th className="px-4 py-3 font-semibold text-right">HPP/kg</th>
                <th className="px-4 py-3 font-semibold text-right">Jual/kg</th>
                <th className="px-4 py-3 font-semibold text-right">Margin</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {(data || []).map((p) => {
                const margin = p.price_kg ? ((p.price_kg - p.hpp_kg) / p.price_kg) * 100 : 0;
                return (
                  <tr key={p.id} data-testid={`product-row-${p.id}`} className="border-t border-border hover:bg-accent/40">
                    <td className="px-4 py-3 font-semibold">{p.name}{p.active === false && <Badge variant="secondary" className="ml-2 text-[10px]">nonaktif</Badge>}</td>
                    <td className="px-4 py-3"><Badge variant="secondary">{CATEGORY_LABELS[p.category]}</Badge></td>
                    <td className="px-4 py-3 text-right tabular">{formatRupiah(p.buy_price_kg)}</td>
                    <td className="px-4 py-3 text-right tabular">{formatRupiah(p.hpp_kg)}</td>
                    <td className="px-4 py-3 text-right tabular font-semibold">{formatRupiah(p.price_kg)}</td>
                    <td className="px-4 py-3 text-right tabular text-success">{formatPct(margin)}</td>
                    <td className="px-4 py-3 text-right">
                      <Button data-testid={`edit-product-${p.id}`} variant="ghost" size="sm" onClick={() => setEdit(p)}><Pencil className="w-4 h-4" /></Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
      {edit && <ProductDialog init={edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); reload(); }} />}
    </div>
  );
}

function ProductDialog({ init, onClose, onSaved }) {
  const [f, setF] = useState({ ...EMPTY, ...init });
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const num = (k) => (e) => set(k, Number(e.target.value));

  const save = async () => {
    if (!f.name) return toast.error("Nama produk wajib diisi");
    setBusy(true);
    const units = [];
    if (f._kg) units.push("kg"); if (f._ekor) units.push("ekor");
    const body = { ...f, units: (f.units && f.units.length ? f.units : ["kg"]) };
    delete body.id; delete body.created_at; delete body._id;
    try {
      if (init.id) await api.put(`/products/${init.id}`, body);
      else await api.post("/products", body);
      toast.success("Produk disimpan");
      onSaved();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  const toggleUnit = (u) => {
    const has = f.units.includes(u);
    set("units", has ? f.units.filter((x) => x !== u) : [...f.units, u]);
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>{init.id ? "Edit Produk" : "Tambah Produk"}</DialogTitle></DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2"><Label className="text-xs">Nama</Label><Input data-testid="prod-name" value={f.name} onChange={(e) => set("name", e.target.value)} className="mt-1" /></div>
          <div><Label className="text-xs">Kategori</Label>
            <Select value={f.category} onValueChange={(v) => set("category", v)}>
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-popover">
                {Object.entries(CATEGORY_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div><Label className="text-xs">Satuan</Label>
            <div className="flex gap-2 mt-1.5">
              {["kg", "ekor"].map((u) => (
                <button key={u} type="button" onClick={() => toggleUnit(u)}
                  className={`px-3 py-1.5 rounded-lg text-sm border ${f.units.includes(u) ? "bg-primary text-primary-foreground border-primary" : "border-border"}`}>{u}</button>
              ))}
            </div>
          </div>
          <div><Label className="text-xs">Harga Beli/kg</Label><Input type="number" value={f.buy_price_kg} onChange={num("buy_price_kg")} className="mt-1 tabular" /></div>
          <div><Label className="text-xs">HPP/kg</Label><Input type="number" value={f.hpp_kg} onChange={num("hpp_kg")} className="mt-1 tabular" /></div>
          <div><Label className="text-xs">Harga Jual/kg</Label><Input data-testid="prod-price-kg" type="number" value={f.price_kg} onChange={num("price_kg")} className="mt-1 tabular" /></div>
          <div><Label className="text-xs">Harga Jual/ekor</Label><Input type="number" value={f.price_ekor} onChange={num("price_ekor")} className="mt-1 tabular" /></div>
          <div><Label className="text-xs">Stok Awal (kg)</Label><Input type="number" value={f.stock_kg} onChange={num("stock_kg")} className="mt-1 tabular" disabled={!!init.id} /></div>
          <div><Label className="text-xs">Stok Awal (ekor)</Label><Input type="number" value={f.stock_ekor} onChange={num("stock_ekor")} className="mt-1 tabular" disabled={!!init.id} /></div>
          <div><Label className="text-xs">Min Stok (kg)</Label><Input type="number" value={f.min_stock_kg} onChange={num("min_stock_kg")} className="mt-1 tabular" /></div>
          <div className="col-span-2"><Label className="text-xs">URL Gambar</Label><Input value={f.image_url} onChange={(e) => set("image_url", e.target.value)} className="mt-1" /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Batal</Button>
          <Button data-testid="save-product" disabled={busy} onClick={save}>{busy ? "Menyimpan..." : "Simpan"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
