import { useState } from "react";
import api, { apiError } from "@/lib/api";
import { useFetch, useRealtimeReload } from "@/lib/hooks";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "sonner";
import { formatRupiah, CATEGORY_LABELS } from "@/lib/format";
import { Plus, Pencil, Phone } from "lucide-react";

export default function Suppliers() {
  const { data, reload } = useFetch("/suppliers");
  useRealtimeReload(["suppliers", "purchases", "payables"], reload);
  const [edit, setEdit] = useState(null);

  const cats = ["broiler", "kampung", "pejantan"];

  return (
    <div className="bam-fade">
      <PageHeader title="Supplier" subtitle="Data supplier, harga terakhir & hutang"
        actions={<Button data-testid="add-supplier" onClick={() => setEdit({})}><Plus className="w-4 h-4 mr-1" /> Tambah</Button>} />
      <Tabs defaultValue="list">
        <TabsList><TabsTrigger value="list" data-testid="tab-list">Daftar Supplier</TabsTrigger><TabsTrigger value="compare" data-testid="tab-compare">Perbandingan Harga</TabsTrigger></TabsList>
        <TabsContent value="list">
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {(data || []).map((s) => (
              <Card key={s.id} data-testid={`supplier-${s.id}`} className="p-4 bam-card-hover">
                <div className="flex items-start justify-between">
                  <p className="font-semibold">{s.name}</p>
                  <Button variant="ghost" size="icon" onClick={() => setEdit(s)}><Pencil className="w-4 h-4" /></Button>
                </div>
                {s.phone && <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1"><Phone className="w-3 h-3" /> {s.phone}</p>}
                <div className="flex justify-between mt-3 text-sm">
                  <div><p className="text-[11px] text-muted-foreground">Total Beli</p><p className="font-semibold tabular">{formatRupiah(s.total_purchase)}</p></div>
                  <div className="text-right"><p className="text-[11px] text-muted-foreground">Hutang</p><p className={`font-semibold tabular ${s.payable > 0 ? "text-destructive" : ""}`}>{formatRupiah(s.payable)}</p></div>
                </div>
              </Card>
            ))}
          </div>
        </TabsContent>
        <TabsContent value="compare">
          <Card className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground">
                <th className="px-4 py-3">Supplier</th>{cats.map((c) => <th key={c} className="px-4 py-3 text-right">{CATEGORY_LABELS[c]}</th>)}
              </tr></thead>
              <tbody>
                {(data || []).map((s) => (
                  <tr key={s.id} className="border-t border-border">
                    <td className="px-4 py-3 font-medium">{s.name}</td>
                    {cats.map((c) => {
                      const price = (s.last_prices || {})[c];
                      const best = (data || []).filter((x) => (x.last_prices || {})[c]).sort((a, b) => a.last_prices[c] - b.last_prices[c])[0];
                      const isBest = best && best.id === s.id && price;
                      return <td key={c} className={`px-4 py-3 text-right tabular ${isBest ? "text-success font-bold" : ""}`}>{price ? formatRupiah(price) : "-"}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="px-4 py-2 text-xs text-muted-foreground">Harga terbaik ditandai hijau.</p>
          </Card>
        </TabsContent>
      </Tabs>
      {edit && <SupplierDialog init={edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); reload(); }} />}
    </div>
  );
}

function SupplierDialog({ init, onClose, onSaved }) {
  const [f, setF] = useState({ name: "", phone: "", address: "", ...init });
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const save = async () => {
    if (!f.name) return toast.error("Nama wajib diisi");
    setBusy(true);
    const body = { name: f.name, phone: f.phone || "", address: f.address || "", chicken_types: f.chicken_types || [] };
    try {
      if (init.id) await api.put(`/suppliers/${init.id}`, body); else await api.post("/suppliers", body);
      toast.success("Supplier disimpan"); onSaved();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover">
        <DialogHeader><DialogTitle>{init.id ? "Edit" : "Tambah"} Supplier</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div><Label className="text-xs">Nama</Label><Input data-testid="sup-name" value={f.name} onChange={(e) => set("name", e.target.value)} className="mt-1" /></div>
          <div><Label className="text-xs">No. HP</Label><Input value={f.phone} onChange={(e) => set("phone", e.target.value)} className="mt-1" /></div>
          <div><Label className="text-xs">Alamat</Label><Input value={f.address} onChange={(e) => set("address", e.target.value)} className="mt-1" /></div>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Batal</Button><Button data-testid="save-supplier" disabled={busy} onClick={save}>Simpan</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
