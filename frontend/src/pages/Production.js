import { useState } from "react";
import api, { apiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { formatRupiah, formatNumber, formatDate } from "@/lib/format";
import { Plus, Trash2 } from "lucide-react";

export default function Production() {
  const { data, reload } = useFetch("/productions");
  const { data: products } = useFetch("/products");
  const source = (products || []).filter((p) => ["broiler", "kampung", "pejantan"].includes(p.category));
  const outs = (products || []).filter((p) => p.category === "fillet" || p.category === "sampingan");
  const [open, setOpen] = useState(false);

  return (
    <div className="bam-fade">
      <PageHeader title="Produksi Potong" subtitle="Potong ayam (ekor) menjadi produk per pcs"
        actions={<Button data-testid="add-production" onClick={() => setOpen(true)}><Plus className="w-4 h-4 mr-1" /> Produksi Baru</Button>} />
      <div className="grid gap-3">
        {(data || []).map((p) => (
          <Card key={p.id} data-testid={`production-${p.id}`} className="p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-semibold">{p.source_name} · Input {formatNumber(p.input_ekor)} ekor</p>
                <p className="text-xs text-muted-foreground">{formatDate(p.date)} · Operator {p.operator}</p>
              </div>
              <div className="text-right"><p className="text-xs text-muted-foreground">Total Biaya</p><p className="font-bold tabular">{formatRupiah(p.total_cost)}</p></div>
            </div>
            <div className="flex flex-wrap gap-2 mt-3">
              {(p.outputs || []).map((o, i) => <span key={`${o.product_id}-${i}`} className="text-xs px-2.5 py-1 rounded-full bg-accent tabular">{o.name}: {formatNumber(o.pcs)} pcs</span>)}
            </div>
          </Card>
        ))}
        {(data || []).length === 0 && <Card className="p-8 text-center text-muted-foreground">Belum ada produksi.</Card>}
      </div>
      {open && <ProductionDialog source={source} outs={outs} onClose={() => setOpen(false)} onSaved={() => { setOpen(false); reload(); }} />}
    </div>
  );
}

function ProductionDialog({ source, outs, onClose, onSaved }) {
  const [f, setF] = useState({ source_product_id: "", input_ekor: 0, labor_cost: 0, packaging_cost: 0, other_cost: 0, operator: "" });
  const [outputs, setOutputs] = useState([{ _k: Math.random(), product_id: "", pcs: 0 }]);
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const setOut = (i, k, v) => setOutputs((a) => a.map((o, idx) => idx === i ? { ...o, [k]: v } : o));
  const totalPcs = outputs.reduce((s, o) => s + Number(o.pcs), 0);

  const save = async () => {
    if (!f.source_product_id || !Number(f.input_ekor)) return toast.error("Lengkapi sumber & jumlah ayam");
    const valid = outputs.filter((o) => o.product_id && Number(o.pcs) > 0);
    if (!valid.length) return toast.error("Tambahkan output");
    setBusy(true);
    try {
      await api.post("/productions", {
        source_product_id: f.source_product_id, input_ekor: Number(f.input_ekor),
        labor_cost: Number(f.labor_cost), packaging_cost: Number(f.packaging_cost), other_cost: Number(f.other_cost),
        operator: f.operator, outputs: valid.map((o) => ({ product_id: o.product_id, pcs: Number(o.pcs) })),
      });
      toast.success("Produksi tersimpan"); onSaved();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>Produksi Potong</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-xs">Sumber (ayam)</Label>
              <Select value={f.source_product_id} onValueChange={(v) => set("source_product_id", v)}>
                <SelectTrigger data-testid="prod-source" className="mt-1"><SelectValue placeholder="Pilih" /></SelectTrigger>
                <SelectContent className="bg-popover">{source.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label className="text-xs">Jumlah Ayam (ekor)</Label><Input data-testid="prod-input" type="number" value={f.input_ekor} onChange={(e) => set("input_ekor", e.target.value)} className="mt-1 tabular" /></div>
          </div>
          <div className="space-y-2">
            <Label className="text-xs">Output (per pcs)</Label>
            {outputs.map((o, i) => (
              <div key={o._k} className="grid grid-cols-12 gap-2 items-center">
                <div className="col-span-7"><Select value={o.product_id} onValueChange={(v) => setOut(i, "product_id", v)}>
                  <SelectTrigger data-testid={`prod-out-${i}`}><SelectValue placeholder="Produk hasil" /></SelectTrigger>
                  <SelectContent className="bg-popover">{outs.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent>
                </Select></div>
                <div className="col-span-4"><Input placeholder="pcs" type="number" value={o.pcs} onChange={(e) => setOut(i, "pcs", e.target.value)} className="tabular" /></div>
                <div className="col-span-1"><Button variant="ghost" size="icon" onClick={() => setOutputs((a) => a.filter((_, idx) => idx !== i))}><Trash2 className="w-4 h-4 text-destructive" /></Button></div>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={() => setOutputs((a) => [...a, { _k: Math.random(), product_id: "", pcs: 0 }])}><Plus className="w-4 h-4 mr-1" /> Output</Button>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div><Label className="text-xs">Tenaga Kerja</Label><Input type="number" value={f.labor_cost} onChange={(e) => set("labor_cost", e.target.value)} className="mt-1 tabular" /></div>
            <div><Label className="text-xs">Kemasan</Label><Input type="number" value={f.packaging_cost} onChange={(e) => set("packaging_cost", e.target.value)} className="mt-1 tabular" /></div>
            <div><Label className="text-xs">Lainnya</Label><Input type="number" value={f.other_cost} onChange={(e) => set("other_cost", e.target.value)} className="mt-1 tabular" /></div>
          </div>
          <div className="rounded-lg bg-accent p-3 text-sm flex justify-between tabular">
            <span>Total Output: {formatNumber(totalPcs)} pcs</span>
          </div>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Batal</Button><Button data-testid="save-production" disabled={busy} onClick={save}>{busy ? "..." : "Simpan"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
