import { useFetch } from "@/lib/hooks";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDate, formatTime } from "@/lib/format";

const ACTION_TONE = { create: "bg-success/15 text-success", update: "bg-chart-4/10 text-chart-4", delete: "bg-destructive/10 text-destructive", cancel: "bg-destructive/10 text-destructive", adjust: "bg-warning/20 text-warning" };

export default function AuditLog() {
  const { data } = useFetch("/audit-logs");
  return (
    <div className="bam-fade">
      <PageHeader title="Audit Log" subtitle="Riwayat aktivitas & perubahan data" />
      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground">
            <th className="px-4 py-3">Waktu</th><th className="px-4 py-3">User</th><th className="px-4 py-3">Aksi</th><th className="px-4 py-3">Entitas</th><th className="px-4 py-3">Detail</th>
          </tr></thead>
          <tbody>
            {(data || []).map((a) => (
              <tr key={a.id} data-testid={`audit-${a.id}`} className="border-t border-border">
                <td className="px-4 py-2.5 text-muted-foreground whitespace-nowrap">{formatDate(a.created_at)} {formatTime(a.created_at)}</td>
                <td className="px-4 py-2.5">{a.user} <span className="text-xs text-muted-foreground">({a.role})</span></td>
                <td className="px-4 py-2.5"><Badge className={ACTION_TONE[a.action] || "bg-muted text-foreground"}>{a.action}</Badge></td>
                <td className="px-4 py-2.5">{a.entity}</td>
                <td className="px-4 py-2.5 text-xs text-muted-foreground max-w-xs truncate">{a.after ? JSON.stringify(a.after) : ""}</td>
              </tr>
            ))}
            {(data || []).length === 0 && <tr><td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">Belum ada log.</td></tr>}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
