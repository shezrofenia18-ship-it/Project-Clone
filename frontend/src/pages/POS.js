import { useEffect, useState, useMemo, useCallback } from "react";
import api, { apiError } from "@/lib/api";
import { useFetch, useRealtimeReload } from "@/lib/hooks";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { useOffline } from "@/context/OfflineContext";
import Receipt from "@/components/Receipt";
import { formatRupiah, formatWeight, formatNumber, CATEGORY_LABELS, PAYMENT_METHODS, PAYMENT_LABELS } from "@/lib/format";
import { Trash2, Plus, Minus, ShoppingCart, Scale, Hash, Delete, ScanLine, Wallet, CloudOff, ChevronUp } from "lucide-react";

// Pemetaan satuan (kg / ekor / pcs) dipisah sebagai lookup supaya tidak ada
// ternary bersarang di dalam JSX — lebih mudah dibaca & diubah.
const UNIT_INPUT_LABEL = { kg: "Berat (kg)", ekor: "Jumlah (ekor)", pcs: "Jumlah (pcs)" };
const UNIT_BUTTON_LABEL = { kg: "Per Kg", ekor: "Per Ekor", pcs: "Per Pcs" };
const priceOf = (p, u) => Number(({ kg: p.price_kg, ekor: p.price_ekor, pcs: p.price_pcs })[u] || 0);
const modalOf = (p, u) => Number(({ kg: p.hpp_kg, ekor: p.hpp_ekor, pcs: p.hpp_pcs })[u] || 0);
// Ayam utuh (produk yang punya satuan "ekor") HANYA boleh dijual per ekor.
// Owner membeli ayam dengan ditimbang (mis. 15 ekor = 30 kg -> 2 kg/ekor), lalu
// saat 1 ekor terjual stok kg otomatis berkurang 2 kg. Produk sampingan,
// potongan, dan fillet TIDAK berubah: tetap boleh per kg dan/atau per pcs.
const posUnits = (p) => {
  const units = (p.units || []).length ? p.units : ["kg"];
  return units.includes("ekor") ? ["ekor"] : units;
};
// Satuan utama yang dipakai untuk menampilkan harga di kartu produk.
const primaryUnit = (p) => posUnits(p)[0] || "kg";
const qtyLabel = (unit, qty) => (unit === "kg" ? formatWeight(qty, 3) : `${qty} ${unit}`);
// Stok ditampilkan dalam satuan yang memang dipakai produk itu.
const stockLabel = (p) => {
  const all = p.units || [];
  const parts = [];
  if (all.includes("ekor")) parts.push(`${formatNumber(p.stock_ekor || 0)} ekor`);
  if (all.includes("kg")) parts.push(formatWeight(p.stock_kg || 0));
  if (all.includes("pcs")) parts.push(`${formatNumber(p.stock_pcs || 0)} pcs`);
  return `Stok ${parts.join(" · ") || "-"}`;
};
import PendingSales from "@/components/PendingSales";
import PayMethodPicker from "@/components/PayMethodPicker";
import useIsDesktop from "@/hooks/useIsDesktop";

const CATS = ["all", "broiler", "kampung", "pejantan", "fillet", "potongan", "sampingan"];

// Local calendar date (YYYY-MM-DD) so a sale queued offline is still booked on the
// day it actually happened, not on the day it finally syncs.
const localDate = () => {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};

export default function POS() {
  const { data: products, reload } = useFetch("/products", [], "products");
  const { data: customers } = useFetch("/customers", [], "customers");
  const [cat, setCat] = useState("all");
  const [cart, setCart] = useState([]);
  const [customerId, setCustomerId] = useState("umum");
  const [entry, setEntry] = useState(null); // product being added
  const [checkout, setCheckout] = useState(false);
  const [cartOpen, setCartOpen] = useState(false);
  const isDesktop = useIsDesktop();
  const [method, setMethod] = useState("cash");
  const [paid, setPaid] = useState("");
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState(null);
  const [debtOpen, setDebtOpen] = useState(false);
  const [pendingOpen, setPendingOpen] = useState(false);
  const { user } = useAuth();
  const { enqueue, online, pending } = useOffline();

  useEffect(() => {
    const id = setInterval(reload, 15000);
    return () => clearInterval(id);
  }, [reload]);

  // Stok & harga ikut berubah seketika saat ada transaksi/pembelian di device lain.
  useRealtimeReload(["stock", "products"], reload);

  const active = (products || []).filter((p) => p.active !== false);
  const shown = active.filter((p) => cat === "all" || p.category === cat);

  const total = useMemo(() => cart.reduce((s, i) => s + i.qty * i.price, 0), [cart]);

  const addToCart = (item) => {
    setCart((c) => [...c, { ...item, key: Date.now() + Math.random() }]);
    setEntry(null);
    toast.success(`${item.name} ditambahkan`);
  };

  const removeItem = (key) => setCart((c) => c.filter((i) => i.key !== key));

  const submitSale = async () => {
    if (method === "piutang" && customerId === "umum") return toast.error("Transaksi piutang harus memilih pelanggan");
    setBusy(true);
    const paidNum = Math.round(method === "piutang" ? Number(paid || 0) : (paid ? Number(paid) : total));
    const txnId = `pos-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const cust = (customers || []).find((c) => c.id === customerId);
    const body = {
      txn_id: txnId,
      customer_id: customerId === "umum" ? null : customerId,
      items: cart.map((i) => ({ product_id: i.product_id, unit: i.unit, qty: i.qty, price: i.price })),
      payment_method: method,
      paid: paidNum,
    };
    const localSale = {
      id: txnId, txn_id: txnId, created_at: new Date().toISOString(),
      cashier_name: user.name, customer_name: cust ? cust.name : "Umum",
      items: cart.map((i) => ({ name: i.name, unit: i.unit, qty: i.qty, price: i.price, subtotal: i.qty * i.price })),
      total, paid: paidNum, change: paidNum > total ? paidNum - total : 0,
      receivable: method === "piutang" ? Math.max(0, total - paidNum) : 0, payment_method: method,
    };
    const finish = (sale, offline) => {
      setReceipt({ sale, phone: cust?.phone, offline });
      setCart([]); setCheckout(false); setCartOpen(false); setPaid(""); setMethod("cash"); setCustomerId("umum");
      setBusy(false);
    };
    // Snapshot for the pending-queue list (body only carries product ids).
    const summary = {
      customer_name: cust ? cust.name : "Umum",
      total,
      item_count: cart.length,
      payment_method: method,
    };
    const queueOffline = () => {
      enqueue({ ...body, date: localDate(), offline_at: new Date().toISOString() }, summary);
    };
    try {
      if (!navigator.onLine) {
        queueOffline();
        toast.warning("Mode offline — transaksi masuk antrean & disinkron otomatis");
        return finish(localSale, true);
      }
      const { data } = await api.post("/sales", body);
      toast.success(`Transaksi selesai · ${formatRupiah(data.total)}`, {
        description: data.change > 0 ? `Kembalian ${formatRupiah(data.change)}` : undefined,
      });
      finish(data, false);
      reload();
    } catch (e) {
      if (!e.response) {
        queueOffline();
        toast.warning("Koneksi terputus — transaksi masuk antrean offline");
        finish(localSale, true);
      } else {
        toast.error(apiError(e));
        setBusy(false);
      }
    }
  };

  return (
    <div className="bam-fade -m-4 lg:-m-6 h-[calc(100vh-4rem)] flex flex-col lg:flex-row">
      {/* products */}
      <div className="flex-1 flex flex-col min-h-0 p-4 lg:p-6">
        {(!online || pending > 0) && (
          <div
            data-testid="pos-offline-banner"
            className={`mb-3 flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold border ${
              !online
                ? "border-destructive/40 bg-destructive/10 text-destructive"
                : "border-warning/40 bg-warning/10 text-warning"
            }`}
          >
            <CloudOff className="w-4 h-4 shrink-0" />
            <span className="min-w-0">
              {!online
                ? "Internet mati — Anda tetap bisa melayani pembeli. Transaksi tersimpan di perangkat & dikirim otomatis saat online."
                : `${pending} transaksi offline menunggu dikirim ke server.`}
            </span>
            <Button
              size="sm" variant="outline" className="h-7 text-xs ml-auto shrink-0"
              data-testid="pos-open-pending" onClick={() => setPendingOpen(true)}
            >
              Lihat Antrean
            </Button>
          </div>
        )}
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-3">
          {CATS.map((c) => (
            <button key={c} data-testid={`pos-cat-${c}`} onClick={() => setCat(c)}
              className={`px-4 py-2 rounded-full text-sm font-semibold whitespace-nowrap transition-colors ${
                cat === c ? "bg-primary text-primary-foreground" : "bg-card border border-border hover:bg-accent"
              }`}>
              {c === "all" ? "Semua" : CATEGORY_LABELS[c]}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto no-scrollbar">
          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-3 pb-24 lg:pb-0">
            {shown.map((p) => (
              <button key={p.id} data-testid={`pos-product-${p.id}`} onClick={() => setEntry(p)}
                className="text-left bg-card border border-border rounded-xl overflow-hidden hover:border-primary hover:-translate-y-0.5 transition-all duration-150">
                <div className="aspect-[4/3] bg-muted overflow-hidden">
                  {p.image_url ? <img src={p.image_url} alt={p.name} className="w-full h-full object-cover" /> : null}
                </div>
                <div className="p-3">
                  <p className="font-semibold text-sm leading-tight truncate">{p.name}</p>
                  <p className="text-primary font-bold text-sm mt-1 tabular">
                    {`${formatRupiah(priceOf(p, primaryUnit(p)))}/${primaryUnit(p)}`}
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5 tabular">{stockLabel(p)}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* keranjang dirender HANYA SATU KALI: sidebar (desktop) ATAU panel geser
          (HP/Tablet). Ini mencegah data-testid & kontrol form ganda di DOM. */}
      {isDesktop && (
        <div className="w-[380px] bg-card border-l border-border flex flex-col min-h-0">
          <CartPanel
            cart={cart} removeItem={removeItem} customers={customers} customerId={customerId}
            setCustomerId={setCustomerId} total={total}
            onCheckout={() => { setPaid(""); setCheckout(true); }}
            onPayDebt={() => setDebtOpen(true)}
          />
        </div>
      )}

      {/* HP & Tablet: bar tetap di bawah supaya pilihan yang akan di-checkout
          SELALU terlihat, lalu panel geser untuk melihat & mengubah keranjang. */}
      {!isDesktop && (
        <>
          <div
            data-testid="pos-mobile-bar"
            className="fixed bottom-0 inset-x-0 z-30 bg-card border-t border-border px-3 pt-2.5 pb-[calc(0.625rem+env(safe-area-inset-bottom))] flex items-center gap-3 shadow-[0_-4px_16px_rgba(0,0,0,0.08)]"
          >
            <button
              data-testid="pos-mobile-cart-open" onClick={() => setCartOpen(true)}
              className="flex items-center gap-2.5 min-w-0 flex-1 text-left"
            >
              <span className="relative shrink-0">
                <ShoppingCart className="w-6 h-6 text-primary" />
                <span className="absolute -top-1.5 -right-2 min-w-[18px] h-[18px] px-1 rounded-full bg-primary text-primary-foreground text-[11px] font-bold flex items-center justify-center">
                  {cart.length}
                </span>
              </span>
              <span className="min-w-0">
                <span className="block text-[11px] text-muted-foreground leading-none">
                  {cart.length === 0 ? "Keranjang kosong" : `${cart.length} item dipilih`}
                </span>
                <span className="block font-head font-extrabold text-xl tabular leading-tight" data-testid="pos-mobile-total">
                  {formatRupiah(total)}
                </span>
              </span>
              <ChevronUp className="w-4 h-4 text-muted-foreground shrink-0" />
            </button>
            <Button
              data-testid="pos-mobile-review" onClick={() => setCartOpen(true)}
              className="h-12 px-5 rounded-lg font-bold shrink-0"
            >
              Lihat Keranjang
            </Button>
          </div>

          <Sheet open={cartOpen} onOpenChange={setCartOpen}>
            <SheetContent
              side="bottom" data-testid="pos-cart-sheet"
              className="p-0 h-[85vh] max-h-[85vh] rounded-t-2xl flex flex-col bg-card"
            >
              <SheetHeader className="px-4 pt-4 pb-0 text-left shrink-0">
                <SheetTitle className="font-head">Keranjang</SheetTitle>
                <SheetDescription className="text-xs">
                  Periksa pesanan sebelum dibayar. Ketuk ikon tong sampah untuk menghapus item.
                </SheetDescription>
              </SheetHeader>
              <CartPanel
                cart={cart} removeItem={removeItem} customers={customers} customerId={customerId}
                setCustomerId={setCustomerId} total={total} compact
                onCheckout={() => { setPaid(""); setCartOpen(false); setCheckout(true); }}
                onPayDebt={() => { setCartOpen(false); setDebtOpen(true); }}
              />
            </SheetContent>
          </Sheet>
        </>
      )}

      {entry && <EntryDialog product={entry} onClose={() => setEntry(null)} onAdd={addToCart} />}

      <Dialog open={checkout} onOpenChange={setCheckout}>
        <DialogContent className="bg-popover">
          <DialogHeader><DialogTitle>Pembayaran</DialogTitle>
            <DialogDescription>Pilih metode pembayaran dan masukkan nominal.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="text-center py-3 rounded-xl bg-accent">
              <p className="text-sm text-muted-foreground">Total Tagihan</p>
              <p className="font-head font-extrabold text-3xl tabular">{formatRupiah(total)}</p>
            </div>
            <div>
              <Label className="text-xs">Metode Pembayaran</Label>
              <div className="grid grid-cols-3 gap-2 mt-1.5">
                {PAYMENT_METHODS.map((m) => (
                  <button key={m} data-testid={`pay-${m}`} onClick={() => setMethod(m)}
                    className={`py-2.5 rounded-lg text-sm font-semibold border transition-colors ${
                      method === m ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-accent"
                    }`}>{PAYMENT_LABELS[m]}</button>
                ))}
              </div>
            </div>
            <div>
              <Label htmlFor="paid" className="text-xs">{method === "piutang" ? "Uang Muka (DP)" : "Uang Diterima"}</Label>
              <Input id="paid" data-testid="pos-paid" type="number" value={paid} onChange={(e) => setPaid(e.target.value)}
                placeholder={formatRupiah(total)} className="mt-1.5 h-11 text-lg tabular" />
              {paid && Number(paid) >= total && method !== "piutang" && (
                <p className="text-sm text-success mt-1.5">Kembalian: {formatRupiah(Number(paid) - total)}</p>
              )}
              {method === "piutang" && (
                <p className="text-sm text-warning mt-1.5">Piutang: {formatRupiah(total - Number(paid || 0))}</p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCheckout(false)}>Batal</Button>
            <Button data-testid="pos-confirm" disabled={busy} onClick={submitSale} className="font-bold">
              {busy ? "Memproses..." : "Selesaikan Transaksi"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {receipt && <Receipt sale={receipt.sale} phone={receipt.phone} offline={receipt.offline} onClose={() => setReceipt(null)} />}
      {debtOpen && <ReceivableDialog onClose={() => setDebtOpen(false)} />}
      {pendingOpen && <PendingSales onClose={() => setPendingOpen(false)} />}
    </div>
  );
}

function CartPanel({ cart, removeItem, customers, customerId, setCustomerId, total, onCheckout, onPayDebt, compact = false }) {
  return (
    <>
      {!compact && (
        <div className="p-4 border-b border-border flex items-center gap-2">
          <ShoppingCart className="w-5 h-5 text-primary" />
          <h2 className="font-head font-bold">Keranjang</h2>
          <Badge variant="secondary" className="ml-auto">{cart.length} item</Badge>
        </div>
      )}
      <div className="flex-1 min-h-0 overflow-y-auto no-scrollbar p-4 space-y-2" data-testid="pos-cart">
        {cart.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground py-12">
            <ShoppingCart className="w-10 h-10 mb-2 opacity-40" />
            <p className="text-sm">Pilih produk untuk memulai transaksi</p>
          </div>
        )}
        {cart.map((i) => (
          <div key={i.key} data-testid={`cart-item-${i.product_id}`} className="flex items-center gap-2 p-2.5 rounded-lg bg-accent/60">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold truncate">{i.name}</p>
              <p className="text-xs text-muted-foreground tabular">
                {qtyLabel(i.unit, i.qty)} × {formatRupiah(i.price)}
              </p>
            </div>
            <p className="text-sm font-bold tabular">{formatRupiah(i.qty * i.price)}</p>
            <button data-testid={`cart-remove-${i.key}`} onClick={() => removeItem(i.key)} className="p-2 rounded-md hover:bg-destructive/10 text-destructive">
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
      <div className="p-4 border-t border-border space-y-3 shrink-0">
        <div>
          <Label className="text-xs">Pelanggan</Label>
          <Select value={customerId} onValueChange={setCustomerId}>
            <SelectTrigger data-testid="pos-customer" className="mt-1"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-popover">
              <SelectItem value="umum">Umum</SelectItem>
              {(customers || []).map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Total</span>
          <span className="font-head font-extrabold text-2xl tabular" data-testid="pos-total">{formatRupiah(total)}</span>
        </div>
        <Button data-testid="pos-checkout" disabled={cart.length === 0} onClick={onCheckout}
          className="w-full h-12 rounded-lg font-bold text-base">
          Bayar
        </Button>
        <Button variant="outline" data-testid="pos-pay-debt" onClick={onPayDebt}
          className="w-full h-10 rounded-lg font-semibold">
          <Wallet className="w-4 h-4 mr-1.5" /> Bayar Piutang Pelanggan
        </Button>
      </div>
    </>
  );
}

function ReceivableDialog({ onClose }) {
  const { data, reload } = useFetch("/receivables");
  const outstanding = (data || []).filter((r) => r.status !== "lunas" && r.remaining > 0);
  const [pay, setPay] = useState(null);
  const [amt, setAmt] = useState("");
  const [payMethod, setPayMethod] = useState("cash");
  const submit = async () => {
    if (!Number(amt)) return toast.error("Masukkan nominal pembayaran");
    try {
      await api.post(`/receivables/${pay.id}/pay`, { amount: Number(amt), method: payMethod });
      toast.success(`Pembayaran piutang tercatat · ${PAYMENT_LABELS[payMethod]}`);
      setPay(null); setAmt(""); setPayMethod("cash"); reload();
    } catch (e) { toast.error(apiError(e)); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover max-w-md max-h-[85vh] overflow-y-auto">
        <DialogHeader><DialogTitle>Bayar Piutang Pelanggan</DialogTitle>
          <DialogDescription>Pilih pelanggan yang melunasi piutangnya.</DialogDescription>
        </DialogHeader>
        <div className="space-y-2" data-testid="debt-list">
          {outstanding.length === 0 && <p className="text-sm text-muted-foreground py-6 text-center">Tidak ada piutang berjalan.</p>}
          {outstanding.map((r) => (
            <div key={r.id} data-testid={`debt-${r.id}`} className="flex items-center gap-2 p-3 rounded-lg bg-accent/60">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold truncate">{r.customer_name}</p>
                <p className="text-xs text-warning tabular">Sisa {formatRupiah(r.remaining)}</p>
              </div>
              <Button size="sm" data-testid={`debt-pay-${r.id}`} onClick={() => { setPay(r); setAmt(String(r.remaining)); setPayMethod("cash"); }}>Bayar</Button>
            </div>
          ))}
        </div>
        {pay && (
          <div className="border-t border-border pt-3 mt-1 space-y-3">
            <div>
              <Label className="text-xs">Nominal untuk {pay.customer_name} (sisa {formatRupiah(pay.remaining)})</Label>
              <Input data-testid="debt-amount" type="number" value={amt} onChange={(e) => setAmt(e.target.value)} className="mt-1 tabular" />
            </div>
            <PayMethodPicker value={payMethod} onChange={setPayMethod} testid="debt-method" />
            <div className="flex gap-2 justify-end">
              <Button variant="outline" size="sm" onClick={() => setPay(null)}>Batal</Button>
              <Button size="sm" data-testid="debt-confirm" onClick={submit}>Simpan Pembayaran</Button>
            </div>
          </div>
        )}
        <DialogFooter><Button variant="outline" onClick={onClose}>Tutup</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EntryDialog({ product, onClose, onAdd }) {
  const { user } = useAuth();
  // Kasir tidak boleh melihat modal/HPP & laba (hanya owner & admin).
  const canSeeCost = user.role === "owner" || user.role === "admin";
  // Ayam utuh: pilihan "Per Kg" memang dihilangkan untuk SEMUA role.
  const units = posUnits(product);
  const priceFor = useCallback((u) => priceOf(product, u), [product]);
  const [unit, setUnit] = useState(units[0]);
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState(priceFor(units[0]));

  useEffect(() => { setPrice(priceFor(unit)); }, [unit, priceFor]);

  const isWeight = unit === "kg";
  const unitLabel = UNIT_INPUT_LABEL[unit] || UNIT_INPUT_LABEL.kg;
  const qtyNum = Number(String(qty).replace(",", ".")) || 0;
  const subtotal = qtyNum * (Number(price) || 0);
  // Ayam utuh: tunjukkan berapa kg stok yang akan berkurang, supaya kasir & owner
  // tahu perhitungannya terukur (mis. 2 ekor x 1,85 kg = 3,7 kg).
  const avgWeight = Number(product.avg_weight_used || product.avg_weight_ekor || 0);
  const stockOut = unit === "ekor" && avgWeight > 0 ? qtyNum * avgWeight : 0;

  const press = (k) => {
    if (k === "del") return setQty((q) => q.slice(0, -1));
    if (k === "." || k === ",") { if (!String(qty).includes(".")) setQty((q) => (q === "" ? "0." : q + ".")); return; }
    setQty((q) => q + k);
  };

  const confirm = () => {
    if (qtyNum <= 0) return toast.error("Masukkan jumlah/berat");
    onAdd({ product_id: product.id, name: product.name, unit, qty: qtyNum, price: Number(price) });
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover max-w-md">
        <DialogHeader><DialogTitle>{product.name}</DialogTitle>
          <DialogDescription>Masukkan berat atau jumlah dan harga.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {units.length > 1 && (
            <div className={`grid gap-2 ${units.length === 3 ? "grid-cols-3" : "grid-cols-2"}`}>
              {units.map((u) => (
                <button key={u} data-testid={`unit-${u}`} onClick={() => setUnit(u)}
                  className={`flex items-center justify-center gap-2 py-2.5 rounded-lg border font-semibold ${unit === u ? "bg-primary text-primary-foreground border-primary" : "border-border"}`}>
                  {u === "kg" ? <Scale className="w-4 h-4" /> : <Hash className="w-4 h-4" />} {UNIT_BUTTON_LABEL[u] || u}
                </button>
              ))}
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs flex items-center gap-1"><ScanLine className="w-3 h-3" /> {unitLabel}</Label>
              <Input data-testid="entry-qty" value={qty} onChange={(e) => setQty(e.target.value.replace(/[^0-9.,]/g, ""))}
                placeholder="0" className="mt-1.5 h-12 text-xl font-bold tabular text-center" inputMode="decimal" />
            </div>
            <div>
              <Label className="text-xs">Harga / {unit}</Label>
              <Input data-testid="entry-price" type="number" value={price} onChange={(e) => setPrice(e.target.value)}
                className="mt-1.5 h-12 text-lg tabular text-center" />
            </div>
          </div>

          {(() => {
            if (!canSeeCost) return null;
            const modal = modalOf(product, unit);
            const estimate = unit === "ekor" && product.avg_weight_source === "perkiraan";
            return modal > 0 ? (
              <p data-testid="entry-modal" className="text-xs text-muted-foreground -mt-1">
                Modal efektif/{unit}: <span className="font-semibold tabular">{formatRupiah(modal)}</span>
                {Number(price) > 0 && <span className="text-success"> · Laba/{unit} {formatRupiah(Number(price) - modal)}</span>}
                {estimate && <span className="text-warning"> · berat perkiraan</span>}
              </p>
            ) : null;
          })()}

          {isWeight ? (
            <div className="grid grid-cols-4 gap-1.5">
              {["1", "2", "3", "4", "5", "6", "7", "8", "9", ",", "0", "del"].map((k) => (
                <button key={k} data-testid={`keypad-${k}`} onClick={() => press(k === "," ? "." : k)}
                  className="h-11 rounded-lg bg-accent hover:bg-primary hover:text-primary-foreground font-bold text-lg transition-colors flex items-center justify-center">
                  {k === "del" ? <Delete className="w-5 h-5" /> : k}
                </button>
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center gap-4">
              <Button variant="outline" size="icon" onClick={() => setQty((q) => String(Math.max(0, (Number(q) || 0) - 1)))}><Minus className="w-4 h-4" /></Button>
              <span className="font-head font-extrabold text-3xl tabular w-16 text-center">{qtyNum || 0}</span>
              <Button variant="outline" size="icon" onClick={() => setQty((q) => String((Number(q) || 0) + 1))}><Plus className="w-4 h-4" /></Button>
            </div>
          )}

          {stockOut > 0 && (
            <p data-testid="entry-stock-out" className="text-xs text-muted-foreground px-1 -mb-1">
              Stok berkurang <span className="font-semibold tabular text-foreground">{formatWeight(stockOut, 2)}</span>
              {` (${formatNumber(qtyNum)} ekor × ${formatWeight(avgWeight, 2)}/ekor)`}
            </p>
          )}

          <div className="flex items-center justify-between px-1">
            <span className="text-muted-foreground">Subtotal</span>
            <span className="font-head font-extrabold text-2xl tabular">{formatRupiah(subtotal)}</span>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Batal</Button>
          <Button data-testid="entry-add" onClick={confirm} className="font-bold">Tambah ke Keranjang</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
