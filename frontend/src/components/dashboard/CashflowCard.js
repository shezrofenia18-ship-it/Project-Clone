// Arus kas hari ini. Di sinilah uang beli ayam & bayar hutang ikut dihitung,
// supaya biaya ayam TIDAK dikurangi dua kali dari laba (sudah ada di HPP).
import { Card } from "@/components/ui/card";
import { formatRupiah, formatRupiahShort } from "@/lib/format";
import { Banknote } from "lucide-react";

function Cell({ label, value, note, tone = "", testid }) {
  return (
    <div>
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className={`font-head font-bold text-lg tabular ${tone}`} data-testid={testid}>{value}</p>
      <p className="text-[10px] text-muted-foreground">{note}</p>
    </div>
  );
}

export default function CashflowCard({ d }) {
  return (
    <Card className="p-4 mt-4" data-testid="cashflow-card">
      <div className="flex items-center gap-2 mb-3">
        <Banknote className="w-4 h-4 text-primary" />
        <h3 className="font-head font-bold text-sm">Uang Masuk &amp; Keluar Hari Ini</h3>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Cell testid="cash-in" label="Uang Masuk" tone="text-success"
          value={formatRupiah(d.cash_in)}
          note={`Tunai jual ${formatRupiahShort(d.kas_dari_penjualan)}`} />
        <Cell testid="cash-out" label="Uang Keluar" tone="text-destructive"
          value={formatRupiah(d.cash_out)}
          note={`Beli ayam & hutang ${formatRupiahShort(d.modal_cash)}`} />
        <Cell testid="net-cash" label="Uang Bersih (Kas)"
          tone={d.net_cash < 0 ? "text-destructive" : "text-success"}
          value={formatRupiah(d.net_cash)} note="Masuk − keluar" />
        <Cell testid="opex" label="Biaya Operasional"
          value={formatRupiah(d.opex)}
          note={`Piutang baru ${formatRupiahShort(d.piutang_baru)}`} />
      </div>
    </Card>
  );
}
