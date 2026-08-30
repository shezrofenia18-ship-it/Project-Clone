import { useState } from "react";
import api, { apiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { formatRupiah, formatNumber, formatDate } from "@/lib/format";
import { Plus } from "lucide-react";

export default function Production() {
  const { data, reload } = useFetch("/productions");
  const { data: products } = useFetch("/products");
  const source = (products || []).filter((p) => ["broiler", "kampung", "pejantan"].includes(p.category));
  const outs = (products || []).filter((p) => ["fillet", "potongan", "sampingan"].includes(p.category));
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
              <div className="text-right"><p className="text-xs text-muted-foreground">Nilai Ayam</p><p className="font-bold tabular">{formatRupiah(p.material_value ?? p.total_cost)}</p></div>
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

const OUT_GROUPS = [
  { key: "potongan", label: "Potongan" },
  { key: "fillet", label: "Fillet" },
  { key: "sampingan", label: "Sampingan" },
];

function ProductionDialog({ source, outs, onClose, onSaved }) {
  const [f, setF] = useState({ source_product_id: "", input_ekor: 0 });
  // Semua bagian langsung tampil; kasir hanya mengisi jumlah pcs.
  // Bentuknya { [product_id]: "12" } supaya tidak perlu tambah/hapus baris.
  const [qty, setQty] = useState({});
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const setQ = (id, v) => setQty((p) => ({ ...p, [id]: v.replace(/[^0-9]/g, "") }));

  const filled = outs.filter((p) => Number(qty[p.id]) > 0);
  const totalPcs = filled.reduce((s, p) => s + Number(qty[p.id]), 0);

  const save = async () => {
    if (!f.source_product_id || !Number(f.input_ekor)) return toast.error("Lengkapi sumber & jumlah ayam");
    if (!filled.length) return toast.error("Isi jumlah pcs minimal satu bagian");
    setBusy(true);
    try {
      await api.post("/productions", {
        source_product_id: f.source_product_id,
        input_ekor: Number(f.input_ekor),
        outputs: filled.map((p) => ({ product_id: p.id, pcs: Number(qty[p.id]) })),
      });
      toast.success("Produksi tersimpan"); onSaved();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Produksi Potong</DialogTitle>
          <DialogDescription className="text-xs">
            Isi jumlah pcs pada bagian yang dihasilkan. Bagian yang dibiarkan kosong tidak dicatat.
          </DialogDescription>
        </DialogHeader>
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

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label className="text-xs">Hasil Potong (pcs)</Label>
              {totalPcs > 0 && (
                <button type="button" data-testid="prod-reset" onClick={() => setQty({})}
                  className="text-[11px] text-muted-foreground hover:text-destructive underline">
                  Kosongkan
                </button>
              )}
            </div>
            {OUT_GROUPS.map((g) => {
              const items = outs.filter((p) => p.category === g.key);
              if (!items.length) return null;
              return (
                <div key={g.key}>
                  <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">{g.label}</p>
                  <div className="space-y-1.5">
                    {items.map((p) => {
                      const active = Number(qty[p.id]) > 0;
                      return (
                        <div key={p.id}
                          className={`flex items-center gap-2 rounded-lg border px-2.5 py-1.5 transition-colors ${active ? "border-primary bg-accent" : "border-border"}`}>
                          <span className="flex-1 text-sm truncate">{p.name}</span>
                          <Input data-testid={`prod-qty-${p.id}`} value={qty[p.id] || ""}
                            onChange={(e) => setQ(p.id, e.target.value)} placeholder="0"
                            inputMode="numeric"
                            className="w-20 h-8 text-center tabular font-semibold" />
                          <span className="text-[11px] text-muted-foreground w-6">pcs</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="rounded-lg bg-accent p-3 text-sm flex justify-between tabular">
            <span>Total Output: {formatNumber(totalPcs)} pcs</span>
            <span className="text-muted-foreground">{filled.length} bagian</span>
          </div>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Batal</Button><Button data-testid="save-production" disabled={busy} onClick={save}>{busy ? "..." : "Simpan"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
