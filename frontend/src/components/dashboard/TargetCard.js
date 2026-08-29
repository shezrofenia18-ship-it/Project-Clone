// Target penjualan hari ini beserta capaiannya.
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { formatRupiah, formatRupiahShort, formatWeight, formatNumber, formatPct } from "@/lib/format";
import { Target as TargetIcon } from "lucide-react";

function Mini({ label, value, of }) {
  return (
    <div>
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className="font-bold text-sm tabular">{value}</p>
      <p className="text-[10px] text-muted-foreground">/{of}</p>
    </div>
  );
}

export default function TargetCard({ d }) {
  const ach = d.target.achievement || 0;
  return (
    <Card className="p-5 lg:col-span-1" data-testid="target-card">
      <div className="flex items-center gap-2 mb-4">
        <TargetIcon className="w-4 h-4 text-primary" />
        <h3 className="font-head font-bold">Target Hari Ini</h3>
      </div>
      {d.target.omzet ? (
        <>
          <div className="flex items-end justify-between mb-1">
            <span className="text-sm text-muted-foreground">Omzet</span>
            <span className="font-bold tabular">{formatPct(ach)}</span>
          </div>
          <Progress value={Math.min(ach, 100)} className="h-2.5" />
          <p className="text-xs text-muted-foreground mt-1.5">{formatRupiah(d.omzet)} / {formatRupiah(d.target.omzet)}</p>
          <div className="grid grid-cols-3 gap-2 mt-5 text-center">
            <Mini label="Berat" value={formatWeight(d.weight, 0)} of={`${formatNumber(d.target.weight)}kg`} />
            <Mini label="Ekor" value={formatNumber(d.ekor)} of={formatNumber(d.target.ekor)} />
            <Mini label="Laba" value={formatRupiahShort(d.laba)} of={formatRupiahShort(d.target.laba)} />
          </div>
        </>
      ) : (
        <p className="text-sm text-muted-foreground py-6 text-center">Target belum diatur untuk hari ini.</p>
      )}
    </Card>
  );
}
