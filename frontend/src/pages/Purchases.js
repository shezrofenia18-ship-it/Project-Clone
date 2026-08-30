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
import { formatRupiah, formatWeight, formatDate } from "@/lib/format";
import { Plus, Trash2, Pencil } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const todayISO = () => new Date().toISOString().slice(0, 10);

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

  const buyable = (products || []).filter((p) => !["sampingan", "fillet", "potongan"].includes(p.category));

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
          _k: Math.random(), product_id: it.product_id, ekor: it.ekor || 0,
          total_weight: it.total_weight || 0, total_price: it.subtotal || 0,
        }))
      : [{ _k: Math.random(), product_id: "", ekor: 0, total_weight: 0, total_price: 0 }]);
  const [paid, setPaid] = useState(initial?.paid ?? 0);
  const [busy, setBusy] = useState(false);

  const setItem = (i, k, v) => setItems((arr) => arr.map((it, idx) => idx === i ? { ...it, [k]: v } : it));
  const birdValue = items.reduce((s, it) => s + Number(it.total_price), 0);
  const totalEkor = items.reduce((s, it) => s + Number(it.ekor), 0);
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
      items: valid.map((it) => ({ product_id: it.product_id, ekor: Number(it.ekor), total_weight: Number(it.total_weight), total_price: Number(it.total_price) })),
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
                      <SelectContent className="bg-popover">{products.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <UnitField label="Jumlah (ekor)" unit="ekor" className="col-span-1 sm:col-span-2"
                    testid={`pur-ekor-${i}`} value={it.ekor} onChange={(v) => setItem(i, "ekor", v)} />
                  <UnitField label="Berat Total (kg)" unit="kg" className="col-span-1 sm:col-span-3"
                    testid={`pur-berat-${i}`} value={it.total_weight} onChange={(v) => setItem(i, "total_weight", v)} />
                  <UnitField label="Total Harga (Rp)" unit="Rp" className="col-span-2 sm:col-span-3"
                    testid={`pur-total-${i}`} value={it.total_price} onChange={(v) => setItem(i, "total_price", v)} />
                </div>
                {/* Kalkulasi otomatis berat 1 ekor: 15 ekor + 30 kg -> 2,00 kg/ekor.
                    Angka inilah yang dipakai memotong stok kg saat kasir jual per ekor. */}
                {Number(it.ekor) > 0 && Number(it.total_weight) > 0 && (
                  <p data-testid={`pur-avg-${i}`} className="text-[11px] text-muted-foreground pl-0.5">
                    Berat 1 ekor kiriman ini:{" "}
                    <span className="font-semibold text-foreground tabular">
                      {formatWeight(Number(it.total_weight) / Number(it.ekor), 2)}/ekor
                    </span>
                    {" — dipakai memotong stok kg tiap 1 ekor terjual"}
                  </p>
                )}
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={() => setItems((a) => [...a, { _k: Math.random(), product_id: "", ekor: 0, total_weight: 0, total_price: 0 }])}><Plus className="w-4 h-4 mr-1" /> Item</Button>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <UnitField label="Dibayar Sekarang (Rp)" unit="Rp" testid="pur-paid"
              value={paid} onChange={setPaid} hint="Sisanya otomatis dicatat sebagai hutang supplier." />
          </div>
          <div className="rounded-lg bg-accent p-3 text-sm space-y-1">
            <div className="flex justify-between"><span>Nilai Ayam (total dibayar)</span><span className="tabular">{formatRupiah(birdValue)}</span></div>
            <div className="flex justify-between font-bold"><span>Total Modal</span><span className="tabular">{formatRupiah(totalModal)}</span></div>
            <div className="flex justify-between text-muted-foreground"><span>Perkiraan Harga/kg (otomatis)</span><span className="tabular">{formatRupiah(totalWeight ? totalModal / totalWeight : 0)}</span></div>
            <div className="flex justify-between text-muted-foreground"><span>Modal Efektif/ekor</span><span className="tabular">{formatRupiah(totalEkor ? totalModal / totalEkor : 0)}</span></div>
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
function UnitField({ label, unit, value, onChange, testid, className = "", hint }) {
  return (
    <div className={className}>
      <Label className="text-[11px] text-muted-foreground">{label}</Label>
      <div className="relative mt-1">
        <Input data-testid={testid} type="number" inputMode="decimal" value={value}
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
