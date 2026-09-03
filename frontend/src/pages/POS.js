import { useEffect, useState, useMemo, useCallback, createContext, useContext } from "react";
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
import { devWarn } from "@/lib/log";
import Receipt from "@/components/Receipt";
import { formatRupiah, formatWeight, formatNumber, CATEGORY_LABELS, PAYMENT_METHODS, PAYMENT_LABELS } from "@/lib/format";
import { Trash2, Plus, Minus, ShoppingCart, Scale, Hash, Delete, ScanLine, Wallet, CloudOff, ChevronUp, Grid3x3, LayoutGrid, Square, Hand } from "lucide-react";

// Pemetaan satuan (kg / ekor / pcs) dipisah sebagai lookup supaya tidak ada
// ternary bersarang di dalam JSX — lebih mudah dibaca & diubah.
const UNIT_INPUT_LABEL = { kg: "Berat (kg)", ekor: "Jumlah (ekor)", pcs: "Jumlah (pcs)" };
const UNIT_BUTTON_LABEL = { kg: "Per Kg", ekor: "Per Ekor", pcs: "Per Pcs" };
// Keypad angka POS. Satuan kg boleh berdesimal (pakai koma); ekor & pcs SELALU
// bilangan bulat, jadi slot koma diganti "C" (hapus semua) yang lebih berguna.
const KEYPAD_DECIMAL = ["1", "2", "3", "4", "5", "6", "7", "8", "9", ",", "0", "del"];
const KEYPAD_INTEGER = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "clear", "0", "del"];
const priceOf = (p, u) => Number(({ kg: p.price_kg, ekor: p.price_ekor, pcs: p.price_pcs })[u] || 0);
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

// Ukuran kartu produk bisa dipilih kasir sesuai perangkatnya (HP kecil, tablet 10",
// monitor kasir). Pilihan disimpan PER PERANGKAT di localStorage.
const CARD_SIZE_KEY = "bam_pos_card_size";
const CARD_SIZES = {
  kecil: {
    grid: "grid-cols-3 md:grid-cols-4 xl:grid-cols-6 2xl:grid-cols-7 gap-2",
    pad: "px-1.5 py-1", name: "text-[11px]", price: "text-[11px]", stock: "text-[9px]",
  },
  sedang: {
    grid: "grid-cols-2 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-2 sm:gap-3",
    pad: "px-2 py-1.5", name: "text-[13px]", price: "text-[13px]", stock: "text-[10px]",
  },
  besar: {
    grid: "grid-cols-2 md:grid-cols-3 xl:grid-cols-3 2xl:grid-cols-4 gap-3",
    pad: "px-3 py-2", name: "text-sm", price: "text-sm", stock: "text-[11px]",
  },
};
const SIZE_OPTIONS = [
  { key: "kecil", label: "Kecil", Icon: Grid3x3 },
  { key: "sedang", label: "Sedang", Icon: LayoutGrid },
  { key: "besar", label: "Besar", Icon: Square },
];

function readCardSize() {
  try {
    const v = localStorage.getItem(CARD_SIZE_KEY);
    return CARD_SIZES[v] ? v : "sedang";
  } catch (err) {
    // Mode privat/penyimpanan diblokir: bukan kondisi error bagi kasir, cukup
    // pakai ukuran bawaan. Tetap dicatat di konsol saat pengembangan.
    devWarn("pos:readCardSize", err);
    return "sedang";
  }
}

function CardSizePicker({ value, onChange }) {
  return (
    <div data-testid="pos-card-size"
      className="flex items-center gap-0.5 shrink-0 bg-card border border-border rounded-full p-0.5">
      {SIZE_OPTIONS.map(({ key, label, Icon }) => (
        <button
          key={key} type="button" title={`Ukuran kartu: ${label}`} aria-label={`Ukuran kartu ${label}`}
          data-testid={`pos-size-${key}`} onClick={() => onChange(key)}
          className={`flex items-center gap-1 h-7 px-2 rounded-full text-[11px] font-semibold transition-colors ${
            value === key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent"
          }`}
        >
          <Icon className="w-3.5 h-3.5" />
          <span className="hidden xl:inline">{label}</span>
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// MODE SENTUH (tablet kasir)
// Kasir yang memakai tablet butuh area sentuh jauh lebih besar daripada
// pengguna mouse: keypad, tombol bayar, filter kategori, dan tombol hapus item.
// Mode ini DIMATIKAN secara bawaan supaya tampilan di HP & komputer TIDAK
// berubah, dan disimpan PER PERANGKAT di localStorage — jadi tablet di meja
// kasir cukup diatur sekali saja.
// Pemakaian: `const touch = useTouch();` lalu `tcls(touch, "kelas-besar", "kelas-normal")`.
// ---------------------------------------------------------------------------
const TOUCH_KEY = "bam_pos_touch";
const TouchCtx = createContext(false);
const useTouch = () => useContext(TouchCtx);
// Pemilih kelas Tailwind: dipisah jadi fungsi agar JSX tidak penuh ternary.
const tcls = (touch, big, normal) => (touch ? big : normal);

function readTouch() {
  try {
    return localStorage.getItem(TOUCH_KEY) === "1";
  } catch (err) {
    // Mode privat / penyimpanan diblokir: bukan gangguan transaksi, cukup
    // pakai bawaan (mati). Dicatat hanya saat pengembangan.
    devWarn("pos:readTouch", err);
    return false;
  }
}

function TouchToggle({ value, onChange }) {
  return (
    <button
      type="button" data-testid="pos-touch-toggle" aria-pressed={value}
      title={value ? "Mode sentuh AKTIF — tombol diperbesar untuk tablet" : "Aktifkan mode sentuh (tablet)"}
      aria-label="Mode sentuh untuk tablet"
      onClick={() => onChange(!value)}
      className={`flex items-center gap-1.5 shrink-0 rounded-full border font-semibold transition-colors ${
        value
          ? "bg-primary text-primary-foreground border-primary"
          : "bg-card text-muted-foreground border-border hover:bg-accent"
      } ${value ? "h-11 px-4 text-sm" : "h-8 px-3 text-[11px]"}`}
    >
      <Hand className={value ? "w-5 h-5" : "w-3.5 h-3.5"} />
      <span className="hidden sm:inline">Sentuh</span>
    </button>
  );
}

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
  const [cardSize, setCardSize] = useState(readCardSize);
  const [touch, setTouch] = useState(readTouch);
  const baseSize = CARD_SIZES[cardSize] || CARD_SIZES.sedang;
  // Mode sentuh: jumlah kolom TETAP mengikuti pilihan kasir (biar dia bisa
  // memilih sendiri berapa produk yang terlihat), tapi padding & ukuran teks
  // kartu dinaikkan ke tingkat "besar" supaya nyaman ditekan dengan jari.
  const size = touch ? { ...baseSize, ...CARD_SIZES.besar, grid: baseSize.grid } : baseSize;
  const { user } = useAuth();
  const { enqueue, online, pending } = useOffline();

  useEffect(() => {
    try {
      localStorage.setItem(CARD_SIZE_KEY, cardSize);
    } catch (err) {
      // Kuota penuh / mode privat: preferensi tampilan gagal disimpan. TIDAK
      // ditampilkan ke kasir (bukan gangguan transaksi), hanya dicatat saat dev.
      devWarn("pos:saveCardSize", err);
    }
  }, [cardSize]);

  useEffect(() => {
    try {
      localStorage.setItem(TOUCH_KEY, touch ? "1" : "0");
    } catch (err) {
      // Sama seperti ukuran kartu: kegagalan menyimpan preferensi tampilan
      // TIDAK ditampilkan ke kasir agar tidak mengganggu pelayanan.
      devWarn("pos:saveTouch", err);
    }
  }, [touch]);

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
    <TouchCtx.Provider value={touch}>
    <div className="bam-fade -m-4 lg:-m-6 h-[calc(100vh-4rem)] flex flex-col lg:flex-row">
      {/* products */}
      <div className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden p-3 lg:p-4">
        {(!online || pending > 0) && (
          <div
            data-testid="pos-offline-banner"
            className={`mb-2 flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[11px] font-semibold border ${
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
        <div className="flex items-center gap-2 pb-2 min-w-0">
          <div
            data-testid="pos-category-scroller"
            className="flex flex-nowrap items-center gap-1.5 overflow-x-auto overflow-y-hidden no-scrollbar min-w-0 flex-1 touch-pan-x snap-x -mx-1 px-1"
            style={{ WebkitOverflowScrolling: "touch" }}
          >
            {CATS.map((c) => (
              <button key={c} data-testid={`pos-cat-${c}`} onClick={() => setCat(c)}
                className={`shrink-0 snap-start rounded-full font-semibold whitespace-nowrap transition-colors ${
                  tcls(touch, "px-5 h-12 text-base", "px-3 h-8 text-xs")
                } ${
                  cat === c ? "bg-primary text-primary-foreground" : "bg-card border border-border hover:bg-accent"
                }`}>
                {c === "all" ? "Semua" : CATEGORY_LABELS[c]}
              </button>
            ))}
          </div>
          <TouchToggle value={touch} onChange={setTouch} />
          <CardSizePicker value={cardSize} onChange={setCardSize} />
        </div>
        <div className="flex-1 min-h-0 min-w-0 overflow-y-auto overflow-x-hidden no-scrollbar" data-testid="pos-product-scroll">
          {/* Kartu dipadatkan & ukurannya bisa dipilih kasir (kecil/sedang/besar). */}
          <div className={`grid w-full ${size.grid} pb-24 lg:pb-1`} data-testid="pos-product-grid">
            {shown.map((p) => (
              <button key={p.id} data-testid={`pos-product-${p.id}`} onClick={() => setEntry(p)}
                className="w-full min-w-0 flex flex-col text-left bg-card border border-border rounded-lg overflow-hidden hover:border-primary hover:-translate-y-0.5 transition-all duration-150">
                <div className="w-full aspect-square bg-muted overflow-hidden">
                  {p.image_url ? <img src={p.image_url} alt={p.name} className="block w-full h-full object-cover" loading="lazy" /> : null}
                </div>
                <div className={`w-full min-w-0 ${size.pad}`}>
                  <p className={`font-semibold ${size.name} leading-tight truncate`}>{p.name}</p>
                  <p className={`text-primary font-bold ${size.price} leading-tight mt-0.5 tabular truncate`}>
                    {`${formatRupiah(priceOf(p, primaryUnit(p)))}/${primaryUnit(p)}`}
                  </p>
                  <p className={`${size.stock} text-muted-foreground leading-tight tabular truncate`}>{stockLabel(p)}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* keranjang dirender HANYA SATU KALI: sidebar (desktop) ATAU panel geser
          (HP/Tablet). Ini mencegah data-testid & kontrol form ganda di DOM. */}
      {isDesktop && (
        <div className="w-[320px] bg-card border-l border-border flex flex-col min-h-0">
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
            className="fixed bottom-0 inset-x-0 z-30 bg-card border-t border-border px-3 pt-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))] flex items-center gap-2 shadow-[0_-4px_16px_rgba(0,0,0,0.08)]"
          >
            <button
              data-testid="pos-mobile-cart-open" onClick={() => setCartOpen(true)}
              className="flex items-center gap-2 min-w-0 flex-1 text-left"
            >
              <span className="relative shrink-0">
                <ShoppingCart className="w-5 h-5 text-primary" />
                <span className="absolute -top-1.5 -right-2 min-w-[16px] h-4 px-1 rounded-full bg-primary text-primary-foreground text-[10px] font-bold flex items-center justify-center">
                  {cart.length}
                </span>
              </span>
              <span className="min-w-0">
                <span className="block text-[10px] text-muted-foreground leading-none">
                  {cart.length === 0 ? "Keranjang kosong" : `${cart.length} item dipilih`}
                </span>
                <span className="block font-head font-extrabold text-lg tabular leading-tight" data-testid="pos-mobile-total">
                  {formatRupiah(total)}
                </span>
              </span>
              <ChevronUp className="w-4 h-4 text-muted-foreground shrink-0" />
            </button>
            <Button
              data-testid="pos-mobile-review" onClick={() => setCartOpen(true)}
              className={`rounded-lg font-bold shrink-0 ${tcls(touch, "h-14 px-6 text-base", "h-10 px-4 text-sm")}`}
            >
              Keranjang
            </Button>
          </div>

          <Sheet open={cartOpen} onOpenChange={setCartOpen}>
            <SheetContent
              side="bottom" data-testid="pos-cart-sheet"
              className="p-0 h-[80vh] max-h-[80vh] rounded-t-2xl flex flex-col bg-card"
            >
              <SheetHeader className="px-3 pt-3 pb-0 text-left shrink-0">
                <SheetTitle className="font-head text-base">Keranjang</SheetTitle>
                <SheetDescription className="text-[11px]">
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
        <DialogContent className={`bg-popover p-4 gap-3 ${tcls(touch, "max-w-md", "max-w-sm")}`}>
          <DialogHeader className="space-y-0.5"><DialogTitle className="text-base">Pembayaran</DialogTitle>
            <DialogDescription className="text-[11px]">Pilih metode pembayaran dan masukkan nominal.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="text-center py-2 rounded-xl bg-accent">
              <p className="text-[11px] text-muted-foreground">Total Tagihan</p>
              <p className="font-head font-extrabold text-2xl tabular">{formatRupiah(total)}</p>
            </div>
            <div>
              <Label className="text-[11px]">Metode Pembayaran</Label>
              <div className={`grid grid-cols-3 mt-1 ${tcls(touch, "gap-2", "gap-1.5")}`}>
                {PAYMENT_METHODS.map((m) => (
                  <button key={m} data-testid={`pay-${m}`} onClick={() => setMethod(m)}
                    className={`rounded-lg font-semibold border transition-colors ${
                      tcls(touch, "h-14 text-sm", "h-9 text-xs")
                    } ${
                      method === m ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-accent"
                    }`}>{PAYMENT_LABELS[m]}</button>
                ))}
              </div>
            </div>
            <div>
              <Label htmlFor="paid" className="text-[11px]">{method === "piutang" ? "Uang Muka (DP)" : "Uang Diterima"}</Label>
              <Input id="paid" data-testid="pos-paid" type="number" value={paid} onChange={(e) => setPaid(e.target.value)}
                placeholder={formatRupiah(total)}
                className={`mt-1 tabular ${tcls(touch, "h-14 text-xl font-bold text-center", "h-10 text-base")}`} />
              {paid && Number(paid) >= total && method !== "piutang" && (
                <p className="text-xs text-success mt-1">Kembalian: {formatRupiah(Number(paid) - total)}</p>
              )}
              {method === "piutang" && (
                <p className="text-xs text-warning mt-1">Piutang: {formatRupiah(total - Number(paid || 0))}</p>
              )}
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-2">
            <Button variant="outline" size={tcls(touch, "default", "sm")}
              className={tcls(touch, "h-14 px-6 text-base", "")}
              onClick={() => setCheckout(false)}>Batal</Button>
            <Button data-testid="pos-confirm" size={tcls(touch, "default", "sm")} disabled={busy} onClick={submitSale}
              className={`font-bold ${tcls(touch, "h-14 px-6 text-base", "")}`}>
              {busy ? "Memproses..." : "Selesaikan Transaksi"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {receipt && <Receipt sale={receipt.sale} phone={receipt.phone} offline={receipt.offline} onClose={() => setReceipt(null)} />}
      {debtOpen && <ReceivableDialog onClose={() => setDebtOpen(false)} />}
      {pendingOpen && <PendingSales onClose={() => setPendingOpen(false)} />}
    </div>
    </TouchCtx.Provider>
  );
}

function CartPanel({ cart, removeItem, customers, customerId, setCustomerId, total, onCheckout, onPayDebt, compact = false }) {
  const touch = useTouch();
  return (
    <>
      {!compact && (
        <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
          <ShoppingCart className="w-4 h-4 text-primary" />
          <h2 className="font-head font-bold text-sm">Keranjang</h2>
          <Badge variant="secondary" className="ml-auto text-[10px]">{cart.length} item</Badge>
        </div>
      )}
      <div className="flex-1 min-h-0 overflow-y-auto no-scrollbar p-3 space-y-1.5" data-testid="pos-cart">
        {cart.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground py-8">
            <ShoppingCart className="w-8 h-8 mb-2 opacity-40" />
            <p className="text-xs">Pilih produk untuk memulai transaksi</p>
          </div>
        )}
        {cart.map((i) => (
          <div key={i.key} data-testid={`cart-item-${i.product_id}`} className={`flex items-center gap-1.5 rounded-lg bg-accent/60 ${tcls(touch, "p-3", "p-2")}`}>
            <div className="min-w-0 flex-1">
              <p className={`font-semibold truncate leading-tight ${tcls(touch, "text-[15px]", "text-[13px]")}`}>{i.name}</p>
              <p className={`text-muted-foreground tabular leading-tight ${tcls(touch, "text-[13px]", "text-[11px]")}`}>
                {qtyLabel(i.unit, i.qty)} × {formatRupiah(i.price)}
              </p>
            </div>
            <p className={`font-bold tabular ${tcls(touch, "text-[15px]", "text-[13px]")}`}>{formatRupiah(i.qty * i.price)}</p>
            <button data-testid={`cart-remove-${i.key}`} onClick={() => removeItem(i.key)}
              aria-label={`Hapus ${i.name} dari keranjang`}
              className={`rounded-md hover:bg-destructive/10 text-destructive shrink-0 ${tcls(touch, "p-3", "p-1.5")}`}>
              <Trash2 className={tcls(touch, "w-6 h-6", "w-4 h-4")} />
            </button>
          </div>
        ))}
      </div>
      <div className="p-3 border-t border-border space-y-2 shrink-0">
        <div>
          <Label className="text-[11px]">Pelanggan</Label>
          <Select value={customerId} onValueChange={setCustomerId}>
            <SelectTrigger data-testid="pos-customer" className={`mt-1 ${tcls(touch, "h-12 text-base", "h-9 text-sm")}`}><SelectValue /></SelectTrigger>
            <SelectContent className="bg-popover">
              <SelectItem value="umum">Umum</SelectItem>
              {(customers || []).map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">Total</span>
          <span className="font-head font-extrabold text-xl tabular" data-testid="pos-total">{formatRupiah(total)}</span>
        </div>
        <Button data-testid="pos-checkout" disabled={cart.length === 0} onClick={onCheckout}
          className={`w-full rounded-lg font-bold ${tcls(touch, "h-16 text-lg", "h-11 text-sm")}`}>
          Bayar
        </Button>
        <Button variant="outline" data-testid="pos-pay-debt" onClick={onPayDebt}
          className={`w-full rounded-lg font-semibold ${tcls(touch, "h-12 text-sm", "h-9 text-xs")}`}>
          <Wallet className={`mr-1.5 ${tcls(touch, "w-4 h-4", "w-3.5 h-3.5")}`} /> Bayar Piutang Pelanggan
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
  // POS TIDAK lagi menampilkan modal efektif & laba per satuan. Kasir tidak perlu
  // tahu modal/laba; owner tetap bisa melihatnya di Produk & Harga, Laporan, dan
  // Dashboard. Dialog ini juga dipadatkan supaya keypad + tombol "Tambah ke
  // Keranjang" muat di layar HP tanpa menggulir.
  // Ayam utuh: pilihan "Per Kg" memang dihilangkan untuk SEMUA role.
  const units = posUnits(product);
  const touch = useTouch();
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
  const estimateWeight = unit === "ekor" && product.avg_weight_source === "perkiraan";

  // Keypad kini juga tampil untuk satuan EKOR & PCS supaya kasir bisa MENGETIK
  // jumlahnya langsung — sebelumnya hanya ada tombol +/- yang harus ditekan
  // berulang (10 ekor = 10 kali tekan). Tombol +/- tetap disediakan untuk
  // penyesuaian cepat 1-2 satuan.
  const press = (k) => {
    if (k === "del") return setQty((q) => String(q).slice(0, -1));
    if (k === "clear") return setQty("");
    if (k === "." || k === ",") {
      if (!isWeight) return; // ekor & pcs tidak berdesimal
      if (!String(qty).includes(".")) setQty((q) => (q === "" ? "0." : q + "."));
      return;
    }
    setQty((q) => String(q) + k);
  };

  const confirm = () => {
    if (qtyNum <= 0) return toast.error("Masukkan jumlah/berat");
    onAdd({ product_id: product.id, name: product.name, unit, qty: qtyNum, price: Number(price) });
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className={`bg-popover p-4 gap-3 ${tcls(touch, "max-w-md", "max-w-sm")}`}>
        <DialogHeader className="space-y-0.5">
          <DialogTitle className="text-base">{product.name}</DialogTitle>
          <DialogDescription className="text-[11px]">Masukkan berat atau jumlah dan harga.</DialogDescription>
        </DialogHeader>
        <div className="space-y-2.5">
          {units.length > 1 && (
            <div className={`grid gap-1.5 ${units.length === 3 ? "grid-cols-3" : "grid-cols-2"}`}>
              {units.map((u) => (
                <button key={u} data-testid={`unit-${u}`} onClick={() => setUnit(u)}
                  className={`flex items-center justify-center gap-1.5 rounded-lg border font-semibold ${
                    tcls(touch, "h-14 text-sm", "h-9 text-xs")
                  } ${unit === u ? "bg-primary text-primary-foreground border-primary" : "border-border"}`}>
                  {u === "kg" ? <Scale className={tcls(touch, "w-5 h-5", "w-3.5 h-3.5")} /> : <Hash className={tcls(touch, "w-5 h-5", "w-3.5 h-3.5")} />} {UNIT_BUTTON_LABEL[u] || u}
                </button>
              ))}
            </div>
          )}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label className="text-[11px] flex items-center gap-1"><ScanLine className="w-3 h-3" /> {unitLabel}</Label>
              <Input data-testid="entry-qty" value={qty}
                onChange={(e) => setQty(e.target.value.replace(isWeight ? /[^0-9.,]/g : /[^0-9]/g, ""))}
                placeholder="0" className={`mt-1 font-bold tabular text-center ${tcls(touch, "h-14 text-2xl", "h-10 text-lg")}`}
                inputMode={isWeight ? "decimal" : "numeric"} />
            </div>
            <div>
              <Label className="text-[11px]">Harga / {unit}</Label>
              <Input data-testid="entry-price" type="number" value={price} onChange={(e) => setPrice(e.target.value)}
                className={`mt-1 tabular text-center ${tcls(touch, "h-14 text-xl", "h-10 text-base")}`} />
            </div>
          </div>

          {!isWeight && (
            <div className={`flex items-center justify-center py-0.5 ${tcls(touch, "gap-6", "gap-4")}`}>
              <Button variant="outline" size="icon" className={tcls(touch, "h-14 w-14", "h-9 w-9")} data-testid="qty-minus" onClick={() => setQty((q) => String(Math.max(0, (Number(q) || 0) - 1)))}><Minus className={tcls(touch, "w-6 h-6", "w-4 h-4")} /></Button>
              <span className={`font-head font-extrabold tabular text-center ${tcls(touch, "text-3xl w-20", "text-2xl w-14")}`}>{qtyNum || 0}</span>
              <Button variant="outline" size="icon" className={tcls(touch, "h-14 w-14", "h-9 w-9")} data-testid="qty-plus" onClick={() => setQty((q) => String((Number(q) || 0) + 1))}><Plus className={tcls(touch, "w-6 h-6", "w-4 h-4")} /></Button>
            </div>
          )}

          <div className={`grid grid-cols-4 ${tcls(touch, "gap-2", "gap-1.5")}`}>
            {(isWeight ? KEYPAD_DECIMAL : KEYPAD_INTEGER).map((k) => (
              <button key={k} data-testid={`keypad-${k}`} onClick={() => press(k === "," ? "." : k)}
                title={k === "clear" ? "Hapus semua" : undefined}
                className={`rounded-lg bg-accent hover:bg-primary hover:text-primary-foreground font-bold transition-colors flex items-center justify-center ${
                  tcls(touch, "h-16 text-2xl", "h-10 text-base")
                }`}>
                {k === "del" ? <Delete className={tcls(touch, "w-6 h-6", "w-4 h-4")} /> : k === "clear" ? "C" : k}
              </button>
            ))}
          </div>

          {stockOut > 0 && (
            <p data-testid="entry-stock-out" className="text-[11px] text-muted-foreground px-0.5 leading-tight">
              Stok berkurang <span className="font-semibold tabular text-foreground">{formatWeight(stockOut, 2)}</span>
              {` (${formatNumber(qtyNum)} ekor × ${formatWeight(avgWeight, 2)}/ekor)`}
              {estimateWeight && <span className="text-warning"> · berat perkiraan</span>}
            </p>
          )}

          <div className="flex items-center justify-between px-0.5">
            <span className="text-xs text-muted-foreground">Subtotal</span>
            <span className="font-head font-extrabold text-xl tabular">{formatRupiah(subtotal)}</span>
          </div>
        </div>
        <DialogFooter className="gap-2 sm:gap-2">
          <Button variant="outline" size={tcls(touch, "default", "sm")}
            className={tcls(touch, "h-14 px-6 text-base", "")} onClick={onClose}>Batal</Button>
          <Button data-testid="entry-add" size={tcls(touch, "default", "sm")} onClick={confirm}
            className={`font-bold ${tcls(touch, "h-14 px-6 text-base", "")}`}>Tambah ke Keranjang</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
