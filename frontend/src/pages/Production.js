import { useState } from "react";
import api, { apiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { formatRupiah, formatNumber, formatDate, formatTime } from "@/lib/format";
import { Plus, Pencil, XCircle } from "lucide-react";

export default function Production() {
  const { data, reload } = useFetch("/productions");
  const { data: products, reload: reloadProducts } = useFetch("/products");
  const [open, setOpen] = useState(false);
  // Baris produksi yang sedang dikoreksi (null = tidak ada).
  const [edit, setEdit] = useState(null);
  // Produk NONAKTIF disembunyikan supaya pilihan tidak dipenuhi produk yang sudah
  // tidak terpakai. Pengecualian: produk yang dipakai pada data lama yang sedang
  // dikoreksi tetap ditampilkan agar formulir edit tidak kehilangan pilihannya.
  const usedInEdit = new Set([edit?.source_product_id, ...((edit?.outputs || []).map((o) => o.product_id))].filter(Boolean));
  const visible = (p) => p.active !== false || usedInEdit.has(p.id);
  const source = (products || []).filter((p) => ["broiler", "kampung", "pejantan"].includes(p.category) && visible(p));
  const outs = (products || []).filter((p) => ["fillet", "potongan", "sampingan"].includes(p.category) && visible(p));

  const afterSave = () => { setOpen(false); setEdit(null); reload(); reloadProducts(); };
  // Produksi yang sedang dikonfirmasi untuk dibatalkan.
  const [cancelling, setCancelling] = useState(null);
  // Filter: sembunyikan yang dibatalkan secara default supaya daftar tetap rapi,
  // tapi log pembatalan tetap bisa dilihat kapan saja.
  const [showCancelled, setShowCancelled] = useState(false);
  const all = data || [];
  const cancelledCount = all.filter((p) => p.status === "batal").length;
  const rows = showCancelled ? all : all.filter((p) => p.status !== "batal");

  return (
    <div className="bam-fade">
      <PageHeader title="Produksi Potong" subtitle="Potong ayam (ekor) menjadi produk per pcs"
        actions={<Button data-testid="add-production" onClick={() => setOpen(true)}><Plus className="w-4 h-4 mr-1" /> Produksi Baru</Button>} />
      {cancelledCount > 0 && (
        <div className="flex items-center justify-end mb-3">
          <button type="button" data-testid="toggle-cancelled" onClick={() => setShowCancelled((v) => !v)}
            className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2">
            {showCancelled ? "Sembunyikan yang dibatalkan" : `Tampilkan ${cancelledCount} produksi dibatalkan`}
          </button>
        </div>
      )}
      <div className="grid gap-3">
        {rows.map((p) => {
          const isCancelled = p.status === "batal";
          return (
          <Card key={p.id} data-testid={`production-${p.id}`} className={`p-4 ${isCancelled ? "border-destructive/40 bg-destructive/[0.03]" : ""}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className={`font-semibold ${isCancelled ? "line-through text-muted-foreground" : ""}`}>
                  {p.source_name} · Input {formatNumber(p.input_ekor)} ekor
                  {Number(p.input_weight_kg) > 0 && (
                    <span className="text-muted-foreground font-normal tabular" data-testid={`production-kg-${p.id}`}>
                      {" "}· ≈ {formatNumber(p.input_weight_kg, 2)} kg
                    </span>
                  )}
                  {isCancelled && <Badge data-testid={`cancelled-badge-${p.id}`} className="ml-2 no-underline bg-destructive text-destructive-foreground text-[10px] align-middle">DIBATALKAN</Badge>}
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatDate(p.date)} · Operator {p.operator}
                  {p.updated_at && !isCancelled && <span className="text-warning"> · sudah dikoreksi</span>}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-right"><p className="text-xs text-muted-foreground">Nilai Ayam</p><p className={`font-bold tabular ${isCancelled ? "line-through text-muted-foreground" : ""}`}>{formatRupiah(p.material_value ?? p.total_cost)}</p></div>
                {!isCancelled && (
                  <>
                    <Button variant="outline" size="sm" data-testid={`edit-production-${p.id}`}
                      onClick={() => setEdit(p)}>
                      <Pencil className="w-3.5 h-3.5 mr-1" /> Edit
                    </Button>
                    <Button variant="outline" size="sm" data-testid={`cancel-production-${p.id}`}
                      className="border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"
                      onClick={() => setCancelling(p)}>
                      <XCircle className="w-3.5 h-3.5 mr-1" /> Batalkan
                    </Button>
                  </>
                )}
              </div>
            </div>
            <div className="flex flex-wrap gap-2 mt-3">
              {(p.outputs || []).map((o, i) => <span key={`${o.product_id}-${i}`} className={`text-xs px-2.5 py-1 rounded-full tabular ${isCancelled ? "bg-muted text-muted-foreground line-through" : "bg-accent"}`}>{o.name}: {formatNumber(o.pcs)} pcs</span>)}
            </div>
            {isCancelled && (
              <div data-testid={`cancel-log-${p.id}`} className="mt-3 rounded-lg border border-destructive/30 bg-destructive/5 p-2.5 text-[11px] leading-relaxed">
                <p className="font-semibold text-destructive flex items-center gap-1"><XCircle className="w-3.5 h-3.5" /> Log pembatalan</p>
                <p className="mt-0.5">
                  <b>{formatDate(p.cancelled_at)} {formatTime(p.cancelled_at)}</b> oleh <b>{p.cancelled_by}</b>
                  {p.cancel_reason && <> — alasan: <i>"{p.cancel_reason}"</i></>}
                </p>
                {p.stock_restored && (
                  <p className="text-muted-foreground tabular mt-0.5">
                    Stok dikembalikan: {formatNumber(p.stock_restored.ekor)} ekor
                    {Number(p.stock_restored.kg) > 0 && <> · {formatNumber(p.stock_restored.kg, 2)} kg</>} {p.source_name}
                    {Object.keys(p.stock_restored.pcs || {}).length > 0 && (
                      <> · ditarik: {Object.entries(p.stock_restored.pcs).map(([n, v]) => `${n} ${formatNumber(v)} pcs`).join(", ")}</>
                    )}
                  </p>
                )}
              </div>
            )}
          </Card>
          );
        })}
        {rows.length === 0 && (
          <Card className="p-8 text-center text-muted-foreground">
            {all.length === 0 ? "Belum ada produksi." : "Semua produksi dibatalkan. Klik \"Tampilkan\" di atas untuk melihat lognya."}
          </Card>
        )}
      </div>
      {open && <ProductionDialog source={source} outs={outs} onClose={() => setOpen(false)} onSaved={afterSave} />}
      {edit && <ProductionDialog initial={edit} source={source} outs={outs} onClose={() => setEdit(null)} onSaved={afterSave} />}
      {cancelling && <CancelProductionDialog production={cancelling} onClose={() => setCancelling(null)} onDone={() => { setCancelling(null); reload(); reloadProducts(); }} />}
    </div>
  );
}

// Konfirmasi pembatalan: wajib alasan. Server mengembalikan stok ekor + kg ayam
// sumber dan menarik pcs hasil, lalu menyimpan log (tanggal, alasan, siapa).
function CancelProductionDialog({ production: p, onClose, onDone }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const totalPcs = (p.outputs || []).reduce((s, o) => s + Number(o.pcs || 0), 0);
  const run = async () => {
    if (reason.trim().length < 3) return toast.error("Isi alasan pembatalan (minimal 3 karakter)");
    setBusy(true);
    try {
      await api.post(`/productions/${p.id}/cancel`, { reason: reason.trim() });
      toast.success("Produksi dibatalkan, stok dikembalikan");
      onDone();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent data-testid="cancel-production-dialog" className="bg-popover max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive"><XCircle className="w-4 h-4" /> Batalkan produksi ini?</DialogTitle>
          <DialogDescription className="text-xs">
            Untuk produksi yang salah input atau tidak jadi dipotong. Data tetap tersimpan sebagai log pembatalan.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs space-y-1 tabular">
            <p className="font-semibold text-sm">{p.source_name} · {formatNumber(p.input_ekor)} ekor{Number(p.input_weight_kg) > 0 ? ` · ≈ ${formatNumber(p.input_weight_kg, 2)} kg` : ""}</p>
            <p className="text-muted-foreground">{formatDate(p.date)} · Operator {p.operator}</p>
            <p className="pt-1">Hasil: {(p.outputs || []).map((o) => `${o.name} ${formatNumber(o.pcs)} pcs`).join(", ") || "-"}</p>
          </div>
          <div className="rounded-lg border border-success/40 bg-success/10 p-2.5 text-[11px] leading-relaxed">
            <p className="font-semibold text-success">Yang akan terjadi pada stok</p>
            <p>Stok <b>{p.source_name}</b> kembali <b>+{formatNumber(p.input_ekor)} ekor</b>{Number(p.input_weight_kg) > 0 && <> dan <b>+{formatNumber(p.input_weight_kg, 2)} kg</b></>}.
              Stok hasil potong ditarik <b>−{formatNumber(totalPcs)} pcs</b>.</p>
          </div>
          <div>
            <Label className="text-xs">Alasan pembatalan <span className="text-destructive">*</span></Label>
            <Input data-testid="cancel-reason" value={reason} onChange={(e) => setReason(e.target.value)} autoFocus
              placeholder="mis. salah input jumlah / tidak jadi dipotong" className="mt-1" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>Kembali</Button>
          <Button data-testid="cancel-confirm" variant="destructive" onClick={run} disabled={busy || reason.trim().length < 3}>
            {busy ? "Membatalkan..." : "Ya, Batalkan Produksi"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const OUT_GROUPS = [
  { key: "potongan", label: "Potongan" },
  { key: "fillet", label: "Fillet" },
  { key: "sampingan", label: "Sampingan" },
];

function ProductionDialog({ initial, source, outs, onClose, onSaved }) {
  // initial terisi -> mode KOREKSI data lama (PUT), kosong -> produksi baru (POST)
  const isEdit = !!initial;
  const [f, setF] = useState(() => ({
    source_product_id: initial?.source_product_id || "",
    input_ekor: initial?.input_ekor ?? 0,
  }));
  // Semua bagian langsung tampil; kasir hanya mengisi jumlah pcs.
  // Bentuknya { [product_id]: "12" } supaya tidak perlu tambah/hapus baris.
  const [qty, setQty] = useState(() => {
    const q = {};
    (initial?.outputs || []).forEach((o) => { q[o.product_id] = String(o.pcs ?? ""); });
    return q;
  });
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const setQ = (id, v) => setQty((p) => ({ ...p, [id]: v.replace(/[^0-9]/g, "") }));

  const filled = outs.filter((p) => Number(qty[p.id]) > 0);
  const totalPcs = filled.reduce((s, p) => s + Number(qty[p.id]), 0);
  const oldPcs = (initial?.outputs || []).reduce((s, o) => s + Number(o.pcs || 0), 0);
  // Estimasi kg yang ikut berkurang dari stok: ekor x berat rata-rata/ekor
  // (aturan yang sama dengan penjualan per ekor di POS).
  const srcProd = source.find((p) => p.id === f.source_product_id);
  const avgW = Number(srcProd?.avg_weight_override) > 0
    ? Number(srcProd.avg_weight_override)
    : Number(srcProd?.avg_weight_used || srcProd?.avg_weight_ekor || 0);
  const estKg = Number(f.input_ekor) > 0 && avgW > 0 ? Number(f.input_ekor) * avgW : 0;

  const save = async () => {
    if (!f.source_product_id || !Number(f.input_ekor)) return toast.error("Lengkapi sumber & jumlah ayam");
    if (!filled.length) return toast.error("Isi jumlah pcs minimal satu bagian");
    setBusy(true);
    try {
      const payload = {
        source_product_id: f.source_product_id,
        input_ekor: Number(f.input_ekor),
        outputs: filled.map((p) => ({ product_id: p.id, pcs: Number(qty[p.id]) })),
      };
      if (isEdit) {
        // Tanggal & operator asli dipertahankan; stok disesuaikan server via selisih.
        await api.put(`/productions/${initial.id}`, { ...payload, date: initial.date, operator: initial.operator || "" });
        toast.success("Produksi diperbarui, stok disesuaikan");
      } else {
        await api.post("/productions", payload);
        toast.success("Produksi tersimpan");
      }
      onSaved();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent data-testid="production-dialog" className="bg-popover max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Produksi Potong" : "Produksi Potong"}</DialogTitle>
          <DialogDescription className="text-xs">
            {isEdit
              ? "Perbaiki angka yang salah input. Stok ayam (ekor + kg) & stok pcs tiap bagian otomatis disesuaikan sebesar selisihnya."
              : "Isi jumlah pcs pada bagian yang dihasilkan. Bagian yang dibiarkan kosong tidak dicatat. Stok ekor & kg ayam sumber berkurang otomatis."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {isEdit && (
            <div className="rounded-lg border border-warning/40 bg-warning/10 p-2.5 text-[11px] tabular">
              Data asli: {formatNumber(initial.input_ekor)} ekor → {formatNumber(oldPcs)} pcs
              {" · "}{formatDate(initial.date)}
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-xs">Sumber (ayam)</Label>
              <Select value={f.source_product_id} onValueChange={(v) => set("source_product_id", v)}>
                <SelectTrigger data-testid="prod-source" className="mt-1"><SelectValue placeholder="Pilih" /></SelectTrigger>
                <SelectContent className="bg-popover">{source.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label className="text-xs">Jumlah Ayam (ekor)</Label><Input data-testid="prod-input" type="number" value={f.input_ekor} onChange={(e) => set("input_ekor", e.target.value)} className="mt-1 tabular" /></div>
          </div>
          {srcProd && (
            <div data-testid="prod-kg-estimate" className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-[11px] leading-relaxed">
              {estKg > 0 ? (
                <>Stok <b>{srcProd.name}</b> akan berkurang <b className="tabular">{formatNumber(f.input_ekor)} ekor</b> dan{" "}
                  <b className="tabular">≈ {formatNumber(estKg, 2)} kg</b>{" "}
                  <span className="text-muted-foreground">({formatNumber(avgW, 2)} kg/ekor × {formatNumber(f.input_ekor)})</span>.
                  Stok kg & ekor selalu berkurang bersama, sama seperti penjualan per ekor.</>
              ) : (
                <span className="text-muted-foreground">Isi jumlah ekor — stok kg akan ikut berkurang sebesar ekor × berat rata-rata/ekor
                  {avgW > 0 ? ` (${formatNumber(avgW, 2)} kg/ekor)` : ""}.</span>
              )}
            </div>
          )}

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label className="text-xs">Hasil Potong (pcs)</Label>
              {totalPcs > 0 && (
                <button type="button" data-testid="prod-reset" onClick={() => setQty({})}
                  className="text-[11px] text-muted-foreground hover:text-destructive underline">
                  Kosongkan
                </button>
              )}
            </div>
            {OUT_GROUPS.map((g) => {
              const items = outs.filter((p) => p.category === g.key);
              if (!items.length) return null;
              return (
                <div key={g.key}>
                  <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">{g.label}</p>
                  <div className="space-y-1.5">
                    {items.map((p) => {
                      const active = Number(qty[p.id]) > 0;
                      return (
                        <div key={p.id}
                          className={`flex items-center gap-2 rounded-lg border px-2.5 py-1.5 transition-colors ${active ? "border-primary bg-accent" : "border-border"}`}>
                          <span className="flex-1 text-sm truncate">{p.name}</span>
                          <Input data-testid={`prod-qty-${p.id}`} value={qty[p.id] || ""}
                            onChange={(e) => setQ(p.id, e.target.value)} placeholder="0"
                            inputMode="numeric"
                            className="w-20 h-8 text-center tabular font-semibold" />
                          <span className="text-[11px] text-muted-foreground w-6">pcs</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="rounded-lg bg-accent p-3 text-sm flex justify-between tabular">
            <span>Total Output: {formatNumber(totalPcs)} pcs</span>
            <span className="text-muted-foreground">
              {isEdit && totalPcs !== oldPcs
                ? `Selisih ${totalPcs > oldPcs ? "+" : ""}${formatNumber(totalPcs - oldPcs)} pcs`
                : `${filled.length} bagian`}
            </span>
          </div>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Batal</Button><Button data-testid="save-production" disabled={busy} onClick={save}>{busy ? "..." : isEdit ? "Simpan Perubahan" : "Simpan"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
