import { useEffect, useState, useMemo } from "react";
import api, { apiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
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
import { toast } from "sonner";
import { formatRupiah, formatWeight, formatNumber, CATEGORY_LABELS, PAYMENT_METHODS, PAYMENT_LABELS } from "@/lib/format";
import { Trash2, Plus, Minus, ShoppingCart, Scale, Hash, Delete, ScanLine } from "lucide-react";

const CATS = ["all", "broiler", "kampung", "pejantan", "fillet", "sampingan"];

export default function POS() {
  const { data: products, reload } = useFetch("/products");
  const { data: customers } = useFetch("/customers");
  const [cat, setCat] = useState("all");
  const [cart, setCart] = useState([]);
  const [customerId, setCustomerId] = useState("umum");
  const [entry, setEntry] = useState(null); // product being added
  const [checkout, setCheckout] = useState(false);
  const [method, setMethod] = useState("cash");
  const [paid, setPaid] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const id = setInterval(reload, 15000);
    return () => clearInterval(id);
  }, [reload]);

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
    setBusy(true);
    const paidNum = method === "piutang" ? Number(paid || 0) : (paid ? Number(paid) : total);
    try {
      const body = {
        txn_id: `pos-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        customer_id: customerId === "umum" ? null : customerId,
        items: cart.map((i) => ({ product_id: i.product_id, unit: i.unit, qty: i.qty, price: i.price })),
        payment_method: method,
        paid: paidNum,
      };
      const { data } = await api.post("/sales", body);
      toast.success(`Transaksi selesai · ${formatRupiah(data.total)}`, {
        description: data.change > 0 ? `Kembalian ${formatRupiah(data.change)}` : undefined,
      });
      setCart([]); setCheckout(false); setPaid(""); setMethod("cash"); setCustomerId("umum");
      reload();
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bam-fade -m-4 lg:-m-6 h-[calc(100vh-4rem)] flex flex-col lg:flex-row">
      {/* products */}
      <div className="flex-1 flex flex-col min-h-0 p-4 lg:p-6">
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
          <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-3">
            {shown.map((p) => (
              <button key={p.id} data-testid={`pos-product-${p.id}`} onClick={() => setEntry(p)}
                className="text-left bg-card border border-border rounded-xl overflow-hidden hover:border-primary hover:-translate-y-0.5 transition-all duration-150">
                <div className="aspect-[4/3] bg-muted overflow-hidden">
                  {p.image_url ? <img src={p.image_url} alt={p.name} className="w-full h-full object-cover" /> : null}
                </div>
                <div className="p-3">
                  <p className="font-semibold text-sm leading-tight truncate">{p.name}</p>
                  <p className="text-primary font-bold text-sm mt-1 tabular">
                    {p.units.includes("kg") ? `${formatRupiah(p.price_kg)}/kg` : `${formatRupiah(p.price_ekor)}/ekor`}
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5 tabular">
                    Stok {formatWeight(p.stock_kg)}{p.stock_ekor ? ` · ${formatNumber(p.stock_ekor)} ekor` : ""}
                  </p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* cart */}
      <div className="w-full lg:w-[380px] bg-card border-t lg:border-t-0 lg:border-l border-border flex flex-col min-h-0">
        <div className="p-4 border-b border-border flex items-center gap-2">
          <ShoppingCart className="w-5 h-5 text-primary" />
          <h2 className="font-head font-bold">Keranjang</h2>
          <Badge variant="secondary" className="ml-auto">{cart.length} item</Badge>
        </div>
        <div className="flex-1 overflow-y-auto no-scrollbar p-4 space-y-2" data-testid="pos-cart">
          {cart.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground py-12">
              <ShoppingCart className="w-10 h-10 mb-2 opacity-40" />
              <p className="text-sm">Pilih produk untuk memulai transaksi</p>
            </div>
          )}
          {cart.map((i) => (
            <div key={i.key} className="flex items-center gap-2 p-2.5 rounded-lg bg-accent/60">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold truncate">{i.name}</p>
                <p className="text-xs text-muted-foreground tabular">
                  {i.unit === "kg" ? formatWeight(i.qty, 3) : `${i.qty} ekor`} × {formatRupiah(i.price)}
                </p>
              </div>
              <p className="text-sm font-bold tabular">{formatRupiah(i.qty * i.price)}</p>
              <button data-testid={`cart-remove-${i.key}`} onClick={() => removeItem(i.key)} className="p-1.5 rounded-md hover:bg-destructive/10 text-destructive">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
        <div className="p-4 border-t border-border space-y-3">
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
          <Button data-testid="pos-checkout" disabled={cart.length === 0} onClick={() => { setPaid(""); setCheckout(true); }}
            className="w-full h-12 rounded-lg font-bold text-base">
            Bayar
          </Button>
        </div>
      </div>

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
    </div>
  );
}

function EntryDialog({ product, onClose, onAdd }) {
  const hasKg = product.units.includes("kg");
  const hasEkor = product.units.includes("ekor");
  const [unit, setUnit] = useState(hasKg ? "kg" : "ekor");
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState(hasKg ? product.price_kg : product.price_ekor);

  useEffect(() => { setPrice(unit === "kg" ? product.price_kg : product.price_ekor); }, [unit, product]);

  const qtyNum = Number(String(qty).replace(",", ".")) || 0;
  const subtotal = qtyNum * (Number(price) || 0);

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
          {hasKg && hasEkor && (
            <div className="grid grid-cols-2 gap-2">
              <button data-testid="unit-kg" onClick={() => setUnit("kg")} className={`flex items-center justify-center gap-2 py-2.5 rounded-lg border font-semibold ${unit === "kg" ? "bg-primary text-primary-foreground border-primary" : "border-border"}`}><Scale className="w-4 h-4" /> Per Kg</button>
              <button data-testid="unit-ekor" onClick={() => setUnit("ekor")} className={`flex items-center justify-center gap-2 py-2.5 rounded-lg border font-semibold ${unit === "ekor" ? "bg-primary text-primary-foreground border-primary" : "border-border"}`}><Hash className="w-4 h-4" /> Per Ekor</button>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs flex items-center gap-1"><ScanLine className="w-3 h-3" /> {unit === "kg" ? "Berat (kg)" : "Jumlah (ekor)"}</Label>
              <Input data-testid="entry-qty" value={qty} onChange={(e) => setQty(e.target.value.replace(/[^0-9.,]/g, ""))}
                placeholder="0" className="mt-1.5 h-12 text-xl font-bold tabular text-center" inputMode="decimal" />
            </div>
            <div>
              <Label className="text-xs">Harga / {unit}</Label>
              <Input data-testid="entry-price" type="number" value={price} onChange={(e) => setPrice(e.target.value)}
                className="mt-1.5 h-12 text-lg tabular text-center" />
            </div>
          </div>

          {unit === "kg" && (
            <div className="grid grid-cols-4 gap-1.5">
              {["1", "2", "3", "4", "5", "6", "7", "8", "9", ",", "0", "del"].map((k) => (
                <button key={k} data-testid={`keypad-${k}`} onClick={() => press(k === "," ? "." : k)}
                  className="h-11 rounded-lg bg-accent hover:bg-primary hover:text-primary-foreground font-bold text-lg transition-colors flex items-center justify-center">
                  {k === "del" ? <Delete className="w-5 h-5" /> : k}
                </button>
              ))}
            </div>
          )}
          {unit === "ekor" && (
            <div className="flex items-center justify-center gap-4">
              <Button variant="outline" size="icon" onClick={() => setQty((q) => String(Math.max(0, (Number(q) || 0) - 1)))}><Minus className="w-4 h-4" /></Button>
              <span className="font-head font-extrabold text-3xl tabular w-16 text-center">{qtyNum || 0}</span>
              <Button variant="outline" size="icon" onClick={() => setQty((q) => String((Number(q) || 0) + 1))}><Plus className="w-4 h-4" /></Button>
            </div>
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
