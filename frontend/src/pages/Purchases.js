import { useState, useCallback } from "react";
import api, { apiError } from "@/lib/api";
import { useFetch, useRealtimeReload } from "@/lib/hooks";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { formatRupiah, formatWeight, formatDate, formatNumber } from "@/lib/format";
import { Plus, Trash2, Pencil } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const todayISO = () => new Date().toISOString().slice(0, 10);

// Deteksi produk FILLET — tidak lagi mencocokkan nama persis "Ayam Fillet".
// Sebuah produk dianggap fillet bila: nama MENGANDUNG kata "fillet" (huruf besar/kecil
// diabaikan) ATAU kategorinya "fillet" di database. Backend mengirim flag `is_fillet`
// dengan aturan yang sama; helper ini jadi cadangan bila flag belum ada.
export const isFilletProduct = (p) => {
  if (!p) return false;
  if (typeof p.is_fillet === "boolean") return p.is_fillet;
  const name = String(p.name || "").toLowerCase();
  const category = String(p.category || "").toLowerCase();
  return name.includes("fillet") || category === "fillet";
};
// Ayam utuh (Broiler/Kampung/Pejantan) = punya satuan ekor.
const isWholeChicken = (p) => (p?.units || []).includes("ekor");
// Produk yang boleh dibeli dari supplier: semua ayam utuh + semua varian fillet.
export const isPurchasable = (p) => {
  if (!p) return false;
  if (typeof p.is_purchasable === "boolean") return p.is_purchasable;
  return isWholeChicken(p) || isFilletProduct(p);
};
// Satuan "jumlah" sebuah baris pembelian: ayam utuh -> ekor, produk fillet -> pcs.
// Kolom berat & harga tidak berubah. Belum pilih produk -> tampil "ekor".
const qtyUnitOf = (product) => {
  if (!product) return "ekor";
  if (product.purchase_unit) return product.purchase_unit;
  return isFilletProduct(product) && !isWholeChicken(product) ? "pcs" : "ekor";
};

export default function Purchases() {
  const { data, reload } = useFetch("/purchases");
  const { data: suppliers, reload: rSup } = useFetch("/suppliers");
  const { data: products } = useFetch("/products");
  const [open, setOpen] = useState(false);
  // Owner boleh MENGOREKSI pembelian yang sudah tersimpan (tanpa hapus & input ulang).
  const [edit, setEdit] = useState(null);
  const [del, setDel] = useState(null);
  const { user } = useAuth();
  const canEdit = user.role === "owner";
  // Pembelian & saldo hutang supplier ikut berubah seketika (mis. setelah bayar hutang).
  const reloadAll = useCallback(() => { reload(); rSup(); }, [reload, rSup]);
  useRealtimeReload(["purchases", "payables", "suppliers"], reloadAll);

  // Produk yang bisa dibeli dari supplier: semua ayam utuh (Broiler/Kampung/Pejantan)
  // + SEMUA varian fillet yang ada di sistem (Ayam Fillet, Dada Fillet, dst.).
  // Produk nonaktif (sudah dihapus owner) disembunyikan, sama seperti POS & Stok.
  // Sampingan/potongan lain tetap hasil produksi sendiri. Ayam utuh ditampilkan lebih dulu.
  const buyable = (products || [])
    .filter((p) => p.active !== false && isPurchasable(p))
    .sort((a, b) => {
      const fa = isFilletProduct(a) ? 1 : 0, fb = isFilletProduct(b) ? 1 : 0;
      return fa - fb || String(a.name).localeCompare(String(b.name));
    });

  return (
    <div className="bam-fade">
      <PageHeader title="Pembelian Ayam" subtitle="Catat ayam masuk dari supplier"
        actions={<Button data-testid="add-purchase" onClick={() => setOpen(true)}><Plus className="w-4 h-4 mr-1" /> Pembelian Baru</Button>} />
      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground">
            <th className="px-4 py-3">Tanggal</th><th className="px-4 py-3">Supplier</th><th className="px-4 py-3 text-right">Berat</th>
            <th className="px-4 py-3 text-right">Modal Efektif/kg</th><th className="px-4 py-3 text-right">Total Modal</th><th className="px-4 py-3">Status</th>
            {canEdit && <th className="px-4 py-3 text-right">Aksi</th>}
          </tr></thead>
          <tbody>
            {(data || []).map((p) => (
              <tr key={p.id} data-testid={`purchase-${p.id}`} className="border-t border-border hover:bg-accent/40">
                <td className="px-4 py-3 whitespace-nowrap">
                  {formatDate(p.date)}
                  {p.updated_at && (
                    <span className="block text-[10px] text-muted-foreground" data-testid={`purchase-edited-${p.id}`}>
                      dikoreksi oleh {p.updated_by}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 font-medium">{p.supplier_name}</td>
                <td className="px-4 py-3 text-right tabular">{formatWeight(p.total_weight)}</td>
                <td className="px-4 py-3 text-right tabular">{formatRupiah(p.effective_cost_kg)}</td>
                <td className="px-4 py-3 text-right tabular font-semibold">{formatRupiah(p.total_modal)}</td>
                <td className="px-4 py-3"><Badge className={p.payment_status === "lunas" ? "bg-success text-white" : "bg-warning text-warning-foreground"}>{p.payment_status}</Badge></td>
                {canEdit && (
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <Button variant="outline" size="sm" className="h-8" data-testid={`edit-purchase-${p.id}`}
                        onClick={() => setEdit(p)}>
                        <Pencil className="w-3.5 h-3.5 mr-1" /> Koreksi
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8" title="Hapus pembelian"
                        data-testid={`delete-purchase-${p.id}`} onClick={() => setDel(p)}>
                        <Trash2 className="w-4 h-4 text-destructive" />
                      </Button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
            {(data || []).length === 0 && <tr><td colSpan={canEdit ? 7 : 6} className="px-4 py-8 text-center text-muted-foreground">Belum ada pembelian.</td></tr>}
          </tbody>
        </table>
      </Card>
      {open && <PurchaseDialog suppliers={suppliers || []} products={buyable}
        onClose={() => setOpen(false)} onSaved={() => { setOpen(false); reloadAll(); }} />}
      {edit && <PurchaseDialog suppliers={suppliers || []} products={buyable} initial={edit}
        onClose={() => setEdit(null)} onSaved={() => { setEdit(null); reloadAll(); }} />}
      {del && <DeletePurchaseDialog purchase={del} onClose={() => setDel(null)}
        onDone={() => { setDel(null); reloadAll(); }} />}
    </div>
  );
}

function DeletePurchaseDialog({ purchase, onClose, onDone }) {
  const [busy, setBusy] = useState(false);
  const hapus = async () => {
    setBusy(true);
    try {
      await api.delete(`/purchases/${purchase.id}`);
      toast.success("Pembelian dihapus, stok & pembukuan dikembalikan");
      onDone();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover max-w-md">
        <DialogHeader><DialogTitle>Hapus pembelian ini?</DialogTitle></DialogHeader>
        <p className="text-sm text-muted-foreground">
          Pembelian <b>{purchase.supplier_name}</b> tanggal {formatDate(purchase.date)} sebesar{" "}
          <b>{formatRupiah(purchase.total_modal)}</b> ({formatWeight(purchase.total_weight)}) akan dihapus.
          Stok, pengeluaran, dan hutang supplier ikut dikembalikan. Kalau hanya ingin membetulkan
          angkanya, pakai tombol <b>Koreksi</b> saja.
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Batal</Button>
          <Button variant="destructive" data-testid="confirm-delete-purchase" disabled={busy} onClick={hapus}>
            {busy ? "Menghapus..." : "Ya, Hapus"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PurchaseDialog({ suppliers, products, onClose, onSaved, initial }) {
  const editing = !!initial;
  const [supplier, setSupplier] = useState(initial?.supplier_id || "");
  const [date, setDate] = useState(initial?.date || todayISO());
  const [items, setItems] = useState(() =>
    editing && (initial.items || []).length
      ? initial.items.map((it) => ({
          // Baris lama menyimpan jumlah di `ekor` (ayam utuh) atau `pcs` (produk fillet).
          // Untuk pcs: `pcs_supplier` = jumlah dari supplier, `pcs` = jumlah akhir
          // setelah dipotong (pembelian sebelum fitur ini hanya punya `pcs`).
          _k: Math.random(), product_id: it.product_id,
          ekor: it.qty_unit === "pcs" ? (it.pcs_supplier ?? it.pcs ?? 0) : (it.ekor || 0),
          pcs_after: it.qty_unit === "pcs" && it.pcs_supplier != null && it.pcs !== it.pcs_supplier ? it.pcs : "",
          total_weight: it.total_weight || 0, total_price: it.subtotal || 0,
        }))
      : [{ _k: Math.random(), product_id: "", ekor: 0, pcs_after: "", total_weight: 0, total_price: 0 }]);
  const [paid, setPaid] = useState(initial?.paid ?? 0);
  const [busy, setBusy] = useState(false);

  const productOf = (id) => products.find((p) => p.id === id);
  const unitOf = (it) => qtyUnitOf(productOf(it.product_id));
  const nameOf = (it) => productOf(it.product_id)?.name || "Fillet";
  const setItem = (i, k, v) => setItems((arr) => arr.map((it, idx) => idx === i ? { ...it, [k]: v } : it));
  // Pcs AKHIR yang masuk stok: "Total Pcs Setelah Dipotong" bila diisi, kalau
  // kosong otomatis = jumlah pcs dari supplier. Kg & harga selalu dari input awal.
  const finalPcs = (it) => (it.pcs_after !== "" && Number(it.pcs_after) > 0 ? Number(it.pcs_after) : Number(it.ekor));
  const birdValue = items.reduce((s, it) => s + Number(it.total_price), 0);
  // Jumlah ekor hanya dari ayam utuh; baris produk fillet dihitung terpisah sebagai pcs.
  const totalEkor = items.reduce((s, it) => s + (unitOf(it) === "ekor" ? Number(it.ekor) : 0), 0);
  const pcsItems = items.filter((it) => unitOf(it) === "pcs" && it.product_id);
  const totalPcsSupplier = pcsItems.reduce((s, it) => s + Number(it.ekor), 0);
  const totalPcs = pcsItems.reduce((s, it) => s + finalPcs(it), 0);
  const pcsValue = pcsItems.reduce((s, it) => s + Number(it.total_price), 0);
  // Rincian per produk fillet (Ayam Fillet, Dada Fillet, ...) supaya owner melihat
  // stok pcs/kg yang masuk ke MASING-MASING produk, bukan cuma totalnya.
  const pcsByProduct = Object.values(pcsItems.reduce((acc, it) => {
    const cur = acc[it.product_id] || { id: it.product_id, name: nameOf(it), supplier: 0, pcs: 0, kg: 0, value: 0 };
    cur.supplier += Number(it.ekor); cur.pcs += finalPcs(it);
    cur.kg += Number(it.total_weight); cur.value += Number(it.total_price);
    acc[it.product_id] = cur;
    return acc;
  }, {}));
  // Transport & biaya lain dihilangkan dari form (permintaan owner): total modal
  // sekarang MURNI total harga ayam dari supplier.
  const totalModal = birdValue;
  const totalWeight = items.reduce((s, it) => s + Number(it.total_weight), 0);

  const save = async () => {
    if (!supplier) return toast.error("Pilih supplier");
    const valid = items.filter((it) => it.product_id && Number(it.total_weight) > 0);
    if (!valid.length) return toast.error("Tambahkan minimal 1 item");
    setBusy(true);
    const payload = {
      supplier_id: supplier,
      date,
      items: valid.map((it) => ({
        product_id: it.product_id, ekor: Number(it.ekor), total_weight: Number(it.total_weight), total_price: Number(it.total_price),
        // hanya berarti untuk produk pcs; backend mengabaikannya untuk ayam utuh
        pcs_after: unitOf(it) === "pcs" ? finalPcs(it) : null,
      })),
      paid: Number(paid),
    };
    try {
      if (editing) {
        await api.put(`/purchases/${initial.id}`, payload);
        toast.success("Pembelian dikoreksi, stok & pembukuan ikut disesuaikan");
      } else {
        await api.post("/purchases", payload);
        toast.success("Pembelian tersimpan, stok bertambah");
      }
      onSaved();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editing ? "Koreksi Pembelian" : "Pembelian Baru"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {editing && (
            <p className="text-[11px] text-muted-foreground bg-accent rounded-lg p-2.5" data-testid="pur-edit-note">
              Betulkan angka yang salah lalu simpan — stok, modal (HPP), pengeluaran, dan hutang
              supplier otomatis disesuaikan. Koreksi ditolak bila hutang pembelian ini sudah
              dibayar, atau bila pengurangan beratnya membuat stok jadi minus (ayamnya sudah terjual).
            </p>
          )}
          <div className="grid sm:grid-cols-2 gap-3">
            <div><Label className="text-xs">Supplier</Label>
              <Select value={supplier} onValueChange={setSupplier}>
                <SelectTrigger data-testid="pur-supplier" className="mt-1"><SelectValue placeholder="Pilih supplier" /></SelectTrigger>
                <SelectContent className="bg-popover">{suppliers.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label className="text-xs">Tanggal Pembelian</Label>
              <Input type="date" data-testid="pur-date" value={date} max={todayISO()}
                onChange={(e) => setDate(e.target.value)} className="mt-1" />
            </div>
          </div>
          <div className="space-y-3">
            <Label className="text-xs">Item Ayam</Label>
            {/* Setiap kotak diberi judul + satuan (ekor / kg / Rp) supaya owner tidak
                keliru memasukkan angka. Di HP kotaknya ditata bertingkat. */}
            {items.map((it, i) => (
              <div key={it._k} className="rounded-lg border border-border p-2.5 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-muted-foreground">Item {i + 1}</span>
                  {items.length > 1 && (
                    <Button variant="ghost" size="icon" className="h-7 w-7" data-testid={`pur-remove-${i}`}
                      onClick={() => setItems((a) => a.filter((_, idx) => idx !== i))}>
                      <Trash2 className="w-4 h-4 text-destructive" />
                    </Button>
                  )}
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-12 gap-2">
                  <div className="col-span-2 sm:col-span-4">
                    <Label className="text-[11px] text-muted-foreground">Produk</Label>
                    <Select value={it.product_id} onValueChange={(v) => setItem(i, "product_id", v)}>
                      <SelectTrigger data-testid={`pur-item-${i}`} className="mt-1"><SelectValue placeholder="Pilih produk" /></SelectTrigger>
                      <SelectContent className="bg-popover">
                        {/* Dropdown hanya menampilkan NAMA produk (tanpa embel-embel satuan);
                            satuan ekor/pcs tetap terlihat di label & kotak "Jumlah". */}
                        {products.map((p) => (
                          <SelectItem key={p.id} value={p.id} data-testid={`pur-item-opt-${p.id}`}>{p.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  {/* Label & satuan mengikuti produk: ayam utuh = ekor, produk fillet = pcs. */}
                  <UnitField label={`Jumlah (${unitOf(it)})`} unit={unitOf(it)} className="col-span-1 sm:col-span-2"
                    testid={`pur-ekor-${i}`} value={it.ekor} onChange={(v) => setItem(i, "ekor", v)} />
                  <UnitField label="Berat Total (kg)" unit="kg" className="col-span-1 sm:col-span-3"
                    testid={`pur-berat-${i}`} value={it.total_weight} onChange={(v) => setItem(i, "total_weight", v)} />
                  <UnitField label="Total Harga (Rp)" unit="Rp" className="col-span-2 sm:col-span-3"
                    testid={`pur-total-${i}`} value={it.total_price} onChange={(v) => setItem(i, "total_price", v)} />
                </div>
                {/* Khusus produk fillet (satuan pcs): fillet dari supplier sering dipotong
                    lagi di toko. Kolom ini = jumlah pcs AKHIR yang masuk stok. Kosong =
                    sama dengan jumlah dari supplier. Kg & modal tetap dari input awal. */}
                {unitOf(it) === "pcs" && it.product_id && (
                  <div className="grid grid-cols-2 sm:grid-cols-12 gap-2">
                    <UnitField label="Total Pcs Setelah Dipotong" unit="pcs" className="col-span-1 sm:col-span-4"
                      testid={`pur-pcs-after-${i}`}
                      value={it.pcs_after === "" ? it.ekor : it.pcs_after}
                      placeholder={String(it.ekor || 0)}
                      onFocus={() => { if (it.pcs_after === "") setItem(i, "pcs_after", String(it.ekor)); }}
                      onChange={(v) => setItem(i, "pcs_after", v)}
                      hint={it.pcs_after !== "" && Number(it.pcs_after) > 0 && Number(it.pcs_after) !== Number(it.ekor)
                        ? `${formatNumber(Number(it.ekor))} pcs dari supplier → ${formatNumber(finalPcs(it))} pcs masuk stok`
                        : "Opsional. Kosong = sama dengan jumlah dari supplier."} />
                    {finalPcs(it) > 0 && Number(it.total_price) > 0 && (
                      <div className="col-span-1 sm:col-span-4">
                        <Label className="text-[11px] text-muted-foreground">Harga/pcs (otomatis)</Label>
                        <p data-testid={`pur-price-pcs-${i}`} className="mt-1 h-10 flex items-center justify-end rounded-md border border-border bg-muted/40 px-3 text-sm font-semibold tabular">
                          {formatRupiah(Number(it.total_price) / finalPcs(it))}
                        </p>
                      </div>
                    )}
                  </div>
                )}
                {/* Kalkulasi otomatis berat 1 ekor: 15 ekor + 30 kg -> 2,00 kg/ekor.
                    Angka inilah yang dipakai memotong stok kg saat kasir jual per ekor.
                    Untuk produk fillet dihitung per pcs AKHIR (setelah dipotong). */}
                {finalPcs(it) > 0 && Number(it.total_weight) > 0 && (
                  <p data-testid={`pur-avg-${i}`} className="text-[11px] text-muted-foreground pl-0.5">
                    Berat 1 {unitOf(it)} {unitOf(it) === "pcs" ? "setelah dipotong" : "kiriman ini"}:{" "}
                    <span className="font-semibold text-foreground tabular">
                      {formatWeight(Number(it.total_weight) / (unitOf(it) === "pcs" ? finalPcs(it) : Number(it.ekor)), 2)}/{unitOf(it)}
                    </span>
                    {unitOf(it) === "ekor"
                      ? " — dipakai memotong stok kg tiap 1 ekor terjual"
                      : ` — stok ${nameOf(it)} bertambah ${formatWeight(Number(it.total_weight))} & ${formatNumber(finalPcs(it))} pcs`}
                  </p>
                )}
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={() => setItems((a) => [...a, { _k: Math.random(), product_id: "", ekor: 0, pcs_after: "", total_weight: 0, total_price: 0 }])}><Plus className="w-4 h-4 mr-1" /> Item</Button>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <UnitField label="Dibayar Sekarang (Rp)" unit="Rp" testid="pur-paid"
              value={paid} onChange={setPaid} hint="Sisanya otomatis dicatat sebagai hutang supplier." />
          </div>
          <div className="rounded-lg bg-accent p-3 text-sm space-y-1">
            <div className="flex justify-between"><span>Nilai Ayam (total dibayar)</span><span className="tabular">{formatRupiah(birdValue)}</span></div>
            <div className="flex justify-between font-bold"><span>Total Modal</span><span className="tabular">{formatRupiah(totalModal)}</span></div>
            <div className="flex justify-between text-muted-foreground"><span>Perkiraan Harga/kg (otomatis)</span><span className="tabular">{formatRupiah(totalWeight ? totalModal / totalWeight : 0)}</span></div>
            {totalPcs > 0 && (
              // Total harga semua baris fillet dibagi jumlah pcs AKHIR (setelah dipotong).
              <div className="flex justify-between text-muted-foreground" data-testid="pur-price-pcs">
                <span>Perkiraan Harga/pcs (otomatis)</span><span className="tabular">{formatRupiah(pcsValue / totalPcs)}</span>
              </div>
            )}
            {totalEkor > 0 && (
              <div className="flex justify-between text-muted-foreground"><span>Modal Efektif/ekor</span><span className="tabular">{formatRupiah(totalModal / totalEkor)}</span></div>
            )}
            {totalPcs > 0 && (
              <div data-testid="pur-total-pcs">
                <div className="flex justify-between text-muted-foreground">
                  <span>Jumlah Fillet (masuk stok)</span>
                  <span className="tabular">
                    {totalPcs !== totalPcsSupplier && <span className="text-[11px] mr-1.5">{formatNumber(totalPcsSupplier)} pcs supplier →</span>}
                    {formatNumber(totalPcs)} pcs
                  </span>
                </div>
                {/* Rincian per produk fillet: stok kg & pcs masuk ke produk yang dipilih di dropdown. */}
                <ul className="mt-1 space-y-0.5 pl-3 border-l-2 border-border">
                  {pcsByProduct.map((g) => (
                    <li key={g.id} className="flex justify-between text-[11px] text-muted-foreground" data-testid={`pur-pcs-product-${g.id}`}>
                      <span className="truncate mr-2">{g.name}</span>
                      <span className="tabular whitespace-nowrap">
                        {g.pcs !== g.supplier && <span className="mr-1">{formatNumber(g.supplier)} →</span>}
                        {formatNumber(g.pcs)} pcs · {formatWeight(g.kg)}
                        {g.pcs > 0 && g.value > 0 && <span className="ml-1">· {formatRupiah(g.value / g.pcs)}/pcs</span>}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {totalEkor === 0 && totalPcs === 0 && (
              <div className="flex justify-between text-muted-foreground"><span>Modal Efektif/ekor</span><span className="tabular">{formatRupiah(0)}</span></div>
            )}
            {totalEkor > 0 && totalWeight > 0 && (
              <div className="flex justify-between text-muted-foreground">
                <span>Berat rata-rata/ekor kiriman ini</span>
                <span className="tabular font-semibold text-foreground" data-testid="pur-avg-total">
                  {formatWeight(totalWeight / totalEkor, 2)}/ekor
                </span>
              </div>
            )}
          </div>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Batal</Button><Button data-testid="save-purchase" disabled={busy} onClick={save}>{busy ? "Menyimpan..." : (editing ? "Simpan Koreksi" : "Simpan")}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Kotak angka dengan judul di atas + satuan di dalam kotak (ekor / kg / Rp).
function UnitField({ label, unit, value, onChange, testid, className = "", hint, placeholder, onFocus }) {
  return (
    <div className={className}>
      <Label className="text-[11px] text-muted-foreground">{label}</Label>
      <div className="relative mt-1">
        <Input data-testid={testid} type="number" inputMode="decimal" value={value}
          placeholder={placeholder} onFocus={onFocus}
          onChange={(e) => onChange(e.target.value)}
          className="tabular pr-10 text-right" />
        <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[11px] font-semibold text-muted-foreground pointer-events-none">
          {unit}
        </span>
      </div>
      {hint && <p className="text-[10px] text-muted-foreground mt-1">{hint}</p>}
    </div>
  );
}
