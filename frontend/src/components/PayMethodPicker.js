import { Label } from "@/components/ui/label";
import { PAYMENT_LABELS } from "@/lib/format";
import { Banknote, Building2, QrCode, CreditCard, Smartphone } from "lucide-react";

// Metode pembayaran untuk PELUNASAN piutang & hutang. "piutang" sengaja tidak
// ada di sini: melunasi piutang dengan piutang tidak masuk akal.
export const DEBT_PAY_METHODS = ["cash", "transfer", "qris", "debit", "ewallet"];

const ICONS = {
  cash: Banknote,
  transfer: Building2,
  qris: QrCode,
  debit: CreditCard,
  ewallet: Smartphone,
};

/** Pemilih metode bayar dengan tombol besar (nyaman dipakai di tablet kasir). */
export default function PayMethodPicker({ value, onChange, testid = "pay-method", label = "Uang Diterima Lewat" }) {
  return (
    <div>
      <Label className="text-xs">{label}</Label>
      <div className="grid grid-cols-3 gap-2 mt-1.5" data-testid={testid}>
        {DEBT_PAY_METHODS.map((m) => {
          const Icon = ICONS[m];
          const on = value === m;
          return (
            <button
              key={m} type="button" data-testid={`${testid}-${m}`} onClick={() => onChange(m)}
              className={`flex flex-col items-center justify-center gap-1 py-2.5 rounded-lg border text-xs font-semibold transition-colors ${
                on ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-accent"
              }`}
            >
              <Icon className="w-4 h-4" />
              {PAYMENT_LABELS[m]}
            </button>
          );
        })}
      </div>
    </div>
  );
}
