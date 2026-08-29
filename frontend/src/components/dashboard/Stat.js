// Kartu angka ringkas di baris atas dashboard.
import { Card } from "@/components/ui/card";

const TONES = {
  primary: "bg-primary/10 text-primary",
  success: "bg-success/10 text-success",
  warning: "bg-warning/20 text-warning",
  chart4: "bg-chart-4/10 text-chart-4",
};

export default function Stat({ icon: Icon, label, value, sub, tone = "primary", testid }) {
  return (
    <Card className="p-5 bam-card-hover" data-testid={testid}>
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
          <p className="font-head font-extrabold text-2xl mt-1.5 tabular truncate">{value}</p>
          {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
        </div>
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${TONES[tone]}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </Card>
  );
}
