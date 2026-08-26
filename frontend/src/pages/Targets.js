import { useState, useEffect } from "react";
import api, { apiError } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { formatRupiah, formatWeight, formatNumber } from "@/lib/format";
import { Target as TargetIcon } from "lucide-react";

export default function Targets() {
  const [f, setF] = useState({ target_omzet: 0, target_weight: 0, target_ekor: 0, target_laba: 0 });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/targets").then((r) => setF({
      target_omzet: r.data.target_omzet || 0, target_weight: r.data.target_weight || 0,
      target_ekor: r.data.target_ekor || 0, target_laba: r.data.target_laba || 0,
    }));
  }, []);

  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const save = async () => {
    setBusy(true);
    try {
      await api.post("/targets", {
        target_omzet: Number(f.target_omzet), target_weight: Number(f.target_weight),
        target_ekor: Number(f.target_ekor), target_laba: Number(f.target_laba),
      });
      toast.success("Target hari ini disimpan");
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  return (
    <div className="bam-fade max-w-xl">
      <PageHeader title="Target Penjualan" subtitle="Tetapkan target harian bisnis" />
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-5"><TargetIcon className="w-5 h-5 text-primary" /><h3 className="font-head font-bold">Target Hari Ini</h3></div>
        <div className="space-y-4">
          <div><Label className="text-xs">Target Omzet (Rp)</Label><Input data-testid="target-omzet" type="number" value={f.target_omzet} onChange={(e) => set("target_omzet", e.target.value)} className="mt-1 tabular" /><p className="text-xs text-muted-foreground mt-1">{formatRupiah(f.target_omzet)}</p></div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-xs">Target Berat (kg)</Label><Input data-testid="target-weight" type="number" value={f.target_weight} onChange={(e) => set("target_weight", e.target.value)} className="mt-1 tabular" /></div>
            <div><Label className="text-xs">Target Ekor</Label><Input data-testid="target-ekor" type="number" value={f.target_ekor} onChange={(e) => set("target_ekor", e.target.value)} className="mt-1 tabular" /></div>
          </div>
          <div><Label className="text-xs">Target Laba (Rp)</Label><Input data-testid="target-laba" type="number" value={f.target_laba} onChange={(e) => set("target_laba", e.target.value)} className="mt-1 tabular" /><p className="text-xs text-muted-foreground mt-1">{formatRupiah(f.target_laba)}</p></div>
          <Button data-testid="save-target" disabled={busy} onClick={save} className="w-full">{busy ? "Menyimpan..." : "Simpan Target"}</Button>
        </div>
      </Card>
    </div>
  );
}
