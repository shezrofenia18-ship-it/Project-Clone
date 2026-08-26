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
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { formatWeight, formatRupiah, formatPct, formatDate, formatNumber } from "@/lib/format";
import { Plus } from "lucide-react";

export default function Slaughter() {
  const { data, reload } = useFetch("/slaughters");
  const { data: products } = useFetch("/products");
  const [open, setOpen] = useState(false);
  const live = (products || []).filter((p) => ["broiler", "kampung", "pejantan"].includes(p.category));

  return (
    <div className="bam-fade">
      <PageHeader title="Pemotongan" subtitle="Proses ayam hidup menjadi karkas · rendemen & susut"
        actions={<Button data-testid="add-slaughter" onClick={() => setOpen(true)}><Plus className="w-4 h-4 mr-1" /> Pemotongan Baru</Button>} />
      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground">
            <th className="px-4 py-3">Tanggal</th><th className="px-4 py-3">Ayam</th><th className="px-4 py-3 text-right">Ekor</th>
            <th className="px-4 py-3 text-right">Berat Hidup</th><th className="px-4 py-3 text-right">Karkas</th>
            <th className="px-4 py-3 text-right">Susut</th><th className="px-4 py-3 text-right">Rendemen</th><th className="px-4 py-3">Operator</th>
          </tr></thead>
          <tbody>
            {(data || []).map((s) => (
              <tr key={s.id} data-testid={`slaughter-${s.id}`} className="border-t border-border hover:bg-accent/40">
                <td className="px-4 py-3">{formatDate(s.date)}</td>
                <td className="px-4 py-3 font-medium">{s.product_name}</td>
                <td className="px-4 py-3 text-right tabular">{formatNumber(s.ekor_in)}</td>
                <td className="px-4 py-3 text-right tabular">{formatWeight(s.live_weight)}</td>
                <td className="px-4 py-3 text-right tabular">{formatWeight(s.carcass_weight)}</td>
                <td className="px-4 py-3 text-right tabular text-warning">{formatWeight(s.susut_weight)}</td>
                <td className="px-4 py-3 text-right"><Badge className="bg-success text-white">{formatPct(s.rendemen_pct)}</Badge></td>
                <td className="px-4 py-3 text-muted-foreground">{s.operator}</td>
              </tr>
            ))}
            {(data || []).length === 0 && <tr><td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">Belum ada data pemotongan.</td></tr>}
          </tbody>
        </table>
      </Card>
      {open && <SlaughterDialog products={live} onClose={() => setOpen(false)} onSaved={() => { setOpen(false); reload(); }} />}
    </div>
  );
}

function SlaughterDialog({ products, onClose, onSaved }) {
  const [f, setF] = useState({ product_id: "", ekor_in: 0, live_weight: 0, carcass_weight: 0, cost_pemotongan: 0, operator: "" });
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const live = Number(f.live_weight), carcass = Number(f.carcass_weight);
  const rendemen = live ? (carcass / live) * 100 : 0;
  const susut = live - carcass;

  const save = async () => {
    if (!f.product_id || !live || !carcass) return toast.error("Lengkapi data");
    if (carcass > live) return toast.error("Karkas tidak boleh > berat hidup");
    setBusy(true);
    try {
      await api.post("/slaughters", { ...f, ekor_in: Number(f.ekor_in), live_weight: live, carcass_weight: carcass, cost_pemotongan: Number(f.cost_pemotongan) });
      toast.success(`Pemotongan tersimpan · rendemen ${rendemen.toFixed(1)}%`); onSaved();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover">
        <DialogHeader><DialogTitle>Pemotongan Baru</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div><Label className="text-xs">Jenis Ayam</Label>
            <Select value={f.product_id} onValueChange={(v) => set("product_id", v)}>
              <SelectTrigger data-testid="sl-product" className="mt-1"><SelectValue placeholder="Pilih ayam" /></SelectTrigger>
              <SelectContent className="bg-popover">{products.map((p) => <SelectItem key={p.id} value={p.id}>{p.name} (stok {formatWeight(p.stock_kg)})</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-xs">Jumlah Ekor</Label><Input type="number" value={f.ekor_in} onChange={(e) => set("ekor_in", e.target.value)} className="mt-1 tabular" /></div>
            <div><Label className="text-xs">Biaya Pemotongan</Label><Input type="number" value={f.cost_pemotongan} onChange={(e) => set("cost_pemotongan", e.target.value)} className="mt-1 tabular" /></div>
            <div><Label className="text-xs">Berat Hidup (kg)</Label><Input data-testid="sl-live" type="number" value={f.live_weight} onChange={(e) => set("live_weight", e.target.value)} className="mt-1 tabular" /></div>
            <div><Label className="text-xs">Berat Karkas (kg)</Label><Input data-testid="sl-carcass" type="number" value={f.carcass_weight} onChange={(e) => set("carcass_weight", e.target.value)} className="mt-1 tabular" /></div>
          </div>
          <div><Label className="text-xs">Operator</Label><Input value={f.operator} onChange={(e) => set("operator", e.target.value)} placeholder="Nama operator" className="mt-1" /></div>
          <div className="rounded-lg bg-accent p-3">
            <div className="flex justify-between text-sm mb-1"><span>Rendemen Karkas</span><span className="font-bold tabular">{formatPct(rendemen)}</span></div>
            <Progress value={Math.min(rendemen, 100)} className="h-2" />
            <p className="text-xs text-muted-foreground mt-1.5 tabular">Susut: {formatWeight(susut > 0 ? susut : 0)} ({formatPct(100 - rendemen)})</p>
          </div>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Batal</Button><Button data-testid="save-slaughter" disabled={busy} onClick={save}>{busy ? "..." : "Simpan"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
