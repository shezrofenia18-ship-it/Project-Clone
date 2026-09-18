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
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "sonner";
import { formatWeight, formatNumber, CATEGORY_LABELS, formatTime, formatDate } from "@/lib/format";
import { SlidersHorizontal, AlertTriangle, RefreshCw } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

// "mati" hanya dipertahankan agar riwayat lama tetap terbaca; pilihan barunya
// adalah "salah_potong" (permintaan owner).
const MOVE_LABELS = { pembelian: "Pembelian", penjualan: "Penjualan", pemotongan: "Pemotongan", produksi: "Produksi", retur: "Retur", penyesuaian: "Penyesuaian", rusak: "Rusak", salah_potong: "Salah Potong", mati: "Mati", susut: "Susut" };
const MOVE_TONE = { pembelian: "bg-success/15 text-success", produksi: "bg-success/15 text-success", penjualan: "bg-primary/10 text-primary", retur: "bg-chart-4/10 text-chart-4", pemotongan: "bg-warning/20 text-warning", salah_potong: "bg-destructive/10 text-destructive" };

export default function Stock() {
  const { user } = useAuth();
  // RBAC: fitur Penyesuaian Stok HANYA untuk owner. Admin & kasir tidak melihat
  // tombol maupun modalnya. Logika penyesuaian (AdjustDialog) tidak diubah.
  const isOwner = user?.role === "owner";
  const { data: products, reload } = useFetch("/products");
  const { data: moves, reload: reloadMoves } = useFetch("/stock-movements");
  const [adj, setAdj] = useState(false);

  // Stok bergerak seketika saat kasir menjual / ayam masuk dari device lain.
  const reloadAll = useCallback(() => { reload(); reloadMoves(); }, [reload, reloadMoves]);
  useRealtimeReload(["stock", "products"], reloadAll);

  const active = (products || []).filter((p) => p.active !== false);
  // Ayam utuh yang stok kg & ekornya tidak sejalan (dihitung backend: stock_sync).
  const outOfSync = active.filter((p) => p.stock_sync?.out_of_sync);
  const [syncing, setSyncing] = useState(null);
  const [syncAll, setSyncAll] = useState(false);
  // Nilai uang (rupiah) TIDAK ditampilkan di halaman Stok — permintaan owner supaya
  // modal/HPP tidak terlihat di layar operasional. Nilai stok tetap ada di
  // Laporan > Stok (khusus owner/admin) dan di PDF Laporan Nilai Stok.
  const totalKg = active.reduce((s, p) => s + (p.stock_kg || 0), 0);
  const totalEkor = active.reduce((s, p) => s + (p.stock_ekor || 0), 0);

  return (
    <div className="bam-fade">
      <PageHeader title="Stok Ayam"
        subtitle={`Total stok: ${formatWeight(totalKg)} · ${formatNumber(totalEkor)} ekor`}
        actions={isOwner ? <Button data-testid="add-adjustment" onClick={() => setAdj(true)}><SlidersHorizontal className="w-4 h-4 mr-1" /> Penyesuaian Stok</Button> : null} />

      {outOfSync.length > 0 && (
        <div data-testid="sync-warning-banner" className="mb-4 rounded-xl border border-warning/40 bg-warning/10 p-3.5 flex flex-wrap items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-warning shrink-0 mt-0.5" />
          <div className="text-sm flex-1 min-w-[240px]">
            <p className="font-semibold text-warning">{outOfSync.length} produk ayam utuh stok kg & ekornya tidak sejalan</p>
            <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
              {outOfSync.map((p) => p.name).join(", ")}. Biasanya sisa data lama sebelum stok kg ikut berkurang otomatis.
              {isOwner ? " Sinkronkan semua sekaligus, atau satu per satu lewat tombol di kartu produk." : " Hubungi owner untuk merapikan."}
            </p>
          </div>
          {isOwner && (
            <Button data-testid="sync-kg-all" size="sm" className="shrink-0 self-center" onClick={() => setSyncAll(true)}>
              <RefreshCw className="w-4 h-4 mr-1" /> Sinkronkan semua ({outOfSync.length})
            </Button>
          )}
        </div>
      )}

      <Tabs defaultValue="stok">
        <TabsList><TabsTrigger value="stok" data-testid="tab-stok">Stok Saat Ini</TabsTrigger><TabsTrigger value="movement" data-testid="tab-movement">Pergerakan Stok</TabsTrigger></TabsList>
        <TabsContent value="stok">
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {active.map((p) => {
              const low = p.min_stock_kg > 0 && p.stock_kg <= p.min_stock_kg;
              const sync = p.stock_sync;
              const gap = !!sync?.out_of_sync;
              return (
                <Card key={p.id} className={`p-4 bam-card-hover ${gap ? "border-warning/60" : ""}`} data-testid={`stock-${p.id}`}>
                  <div className="flex items-center justify-between">
                    <p className="font-semibold">{p.name}</p>
                    <Badge variant="secondary" className="text-[10px]">{CATEGORY_LABELS[p.category]}</Badge>
                  </div>
                  <div className="flex items-end gap-4 mt-3">
                    <div><p className="text-[11px] text-muted-foreground">Berat</p><p className={`font-head font-extrabold text-xl tabular ${low ? "text-warning" : ""}`}>{formatWeight(p.stock_kg)}</p></div>
                    {p.units.includes("ekor") && <div><p className="text-[11px] text-muted-foreground">Ekor</p><p className="font-head font-extrabold text-xl tabular">{formatNumber(p.stock_ekor)}</p></div>}
                    {p.units.includes("pcs") && <div><p className="text-[11px] text-muted-foreground">Pcs</p><p className="font-head font-extrabold text-xl tabular">{formatNumber(p.stock_pcs)}</p></div>}
                  </div>
                  {low && <Badge className="mt-2 bg-warning text-warning-foreground">Stok menipis</Badge>}
                  {gap && (
                    <div data-testid={`sync-gap-${p.id}`} className="mt-3 rounded-lg border border-warning/40 bg-warning/10 p-2.5 text-[11px] leading-relaxed">
                      <p className="font-semibold text-warning flex items-center gap-1"><AlertTriangle className="w-3.5 h-3.5" /> Kg & ekor tidak sejalan</p>
                      <p className="mt-0.5 tabular">
                        Seharusnya ≈ <b>{formatWeight(sync.expected_kg)}</b> ({formatNumber(p.stock_ekor)} ekor × {formatNumber(sync.avg_weight, 2)} kg),
                        selisih <b className={sync.diff_kg > 0 ? "text-success" : "text-destructive"}>{sync.diff_kg > 0 ? "+" : ""}{formatWeight(sync.diff_kg)}</b> ({formatNumber(sync.diff_pct, 1)}%) — {sync.reason}.
                      </p>
                      {isOwner && (
                        <Button data-testid={`sync-kg-${p.id}`} size="sm" variant="outline" className="mt-2 h-7 text-xs border-warning/60"
                          onClick={() => setSyncing(p)}>
                          <RefreshCw className="w-3.5 h-3.5 mr-1" /> Sinkronkan kg
                        </Button>
                      )}
                    </div>
                  )}
                  {!gap && sync && sync.expected_kg != null && Math.abs(sync.diff_kg) > 0.0005 && (
                    <p className="mt-2 text-[10px] text-muted-foreground tabular" title="Selisih kecil, masih dalam batas wajar">
                      ≈ {formatNumber(sync.implied_avg, 2)} kg/ekor · selisih {sync.diff_kg > 0 ? "+" : ""}{formatWeight(sync.diff_kg)}
                    </p>
                  )}
                </Card>
              );
            })}
          </div>
        </TabsContent>
        <TabsContent value="movement">
          <Card className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground">
                <th className="px-4 py-3">Waktu</th><th className="px-4 py-3">Produk</th><th className="px-4 py-3">Jenis</th>
                <th className="px-4 py-3 text-right">Qty</th><th className="px-4 py-3 text-right">Stok Sesudah</th><th className="px-4 py-3">User</th>
              </tr></thead>
              <tbody>
                {(moves || []).slice(0, 200).map((m) => (
                  <tr key={m.id} className="border-t border-border">
                    <td className="px-4 py-2.5 text-muted-foreground">{formatDate(m.created_at)} {formatTime(m.created_at)}</td>
                    <td className="px-4 py-2.5 font-medium">{m.product_name}</td>
                    <td className="px-4 py-2.5"><Badge className={MOVE_TONE[m.type] || "bg-muted text-foreground"}>{MOVE_LABELS[m.type] || m.type}</Badge></td>
                    <td className="px-4 py-2.5 text-right tabular">{m.qty_kg ? `${m.qty_kg > 0 ? "+" : ""}${formatWeight(m.qty_kg, 3)}` : ""}{m.qty_ekor ? ` ${m.qty_ekor > 0 ? "+" : ""}${m.qty_ekor} ekor` : ""}{m.qty_pcs ? ` ${m.qty_pcs > 0 ? "+" : ""}${formatNumber(m.qty_pcs)} pcs` : ""}</td>
                    <td className="px-4 py-2.5 text-right tabular">{m.qty_pcs && !m.qty_kg ? `${formatNumber(m.after_pcs)} pcs` : formatWeight(m.after_kg)}</td>
                    <td className="px-4 py-2.5 text-muted-foreground">{m.user}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </TabsContent>
      </Tabs>
      {isOwner && adj && <AdjustDialog products={active} onClose={() => setAdj(false)} onSaved={() => { setAdj(false); reload(); reloadMoves(); }} />}
      {isOwner && syncing && <SyncKgDialog product={syncing} onClose={() => setSyncing(null)} onDone={() => { setSyncing(null); reload(); reloadMoves(); }} />}
      {isOwner && syncAll && <SyncAllDialog products={outOfSync} onClose={() => setSyncAll(false)} onDone={() => { setSyncAll(false); reload(); reloadMoves(); }} />}
    </div>
  );
}

// Konfirmasi "Sinkronkan semua": daftar tiap produk bermasalah beserta kg
// sekarang -> kg target, lalu satu klik untuk semuanya. Server tetap mencatat
// tiap produk terpisah di Pergerakan Stok & Audit Log.
function SyncAllDialog({ products, onClose, onDone }) {
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");
  const totalDelta = products.reduce((s, p) => s + -(p.stock_sync?.diff_kg || 0), 0);
  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/products/sync-kg-all", { reason });
      toast.success(data.count
        ? `${data.count} produk disinkronkan (${data.total_delta_kg > 0 ? "+" : ""}${formatWeight(data.total_delta_kg)})`
        : "Semua stok sudah sejalan, tidak ada perubahan");
      onDone();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent data-testid="sync-all-dialog" className="bg-popover max-w-lg">
        <DialogHeader><DialogTitle className="flex items-center gap-2"><RefreshCw className="w-4 h-4" /> Sinkronkan semua ({products.length} produk)</DialogTitle></DialogHeader>
        <div className="space-y-3 text-sm">
          <div className="rounded-lg border border-border overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-muted/50 text-muted-foreground"><tr className="text-left">
                <th className="px-3 py-2">Produk</th><th className="px-3 py-2 text-right">Ekor</th>
                <th className="px-3 py-2 text-right">Kg sekarang</th><th className="px-3 py-2 text-right">Kg target</th><th className="px-3 py-2 text-right">Perubahan</th>
              </tr></thead>
              <tbody>
                {products.map((p) => {
                  const s = p.stock_sync || {};
                  const d = -(s.diff_kg || 0);
                  return (
                    <tr key={p.id} data-testid={`sync-all-row-${p.id}`} className="border-t border-border tabular">
                      <td className="px-3 py-2 font-medium">{p.name} <span className="text-muted-foreground">· {formatNumber(s.avg_weight, 2)} kg/ekor</span></td>
                      <td className="px-3 py-2 text-right">{formatNumber(p.stock_ekor)}</td>
                      <td className="px-3 py-2 text-right">{formatWeight(p.stock_kg)}</td>
                      <td className="px-3 py-2 text-right font-semibold text-primary">{formatWeight(s.expected_kg)}</td>
                      <td className={`px-3 py-2 text-right font-semibold ${d < 0 ? "text-destructive" : "text-success"}`}>{d > 0 ? "+" : ""}{formatWeight(d)}</td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot className="bg-muted/30 tabular"><tr className="border-t border-border">
                <td colSpan={4} className="px-3 py-2 text-right text-muted-foreground">Total perubahan</td>
                <td className={`px-3 py-2 text-right font-bold ${totalDelta < 0 ? "text-destructive" : "text-success"}`} data-testid="sync-all-total">{totalDelta > 0 ? "+" : ""}{formatWeight(totalDelta)}</td>
              </tr></tfoot>
            </table>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Setiap produk diset ke ekor × berat rata-rata/ekor dan dicatat terpisah sebagai Penyesuaian di Pergerakan Stok & Audit Log.
            Jika angka kg di lapangan memang benar, perbarui berat rata-rata/ekor di Produk & Harga alih-alih menyinkronkan.
          </p>
          <div><Label className="text-xs">Catatan (opsional)</Label>
            <Input data-testid="sync-all-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="mis. rapikan data lama" className="mt-1" /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>Batal</Button>
          <Button data-testid="sync-all-confirm" onClick={run} disabled={busy || !products.length}>{busy ? "Menyinkronkan..." : `Sinkronkan ${products.length} Produk`}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Konfirmasi "Sinkronkan kg": set stok kg = ekor x berat rata-rata/ekor.
// Dicatat server sebagai penyesuaian stok sebesar selisihnya (bukan menimpa).
function SyncKgDialog({ product, onClose, onDone }) {
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");
  const s = product.stock_sync || {};
  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/products/${product.id}/sync-kg`, { reason });
      toast.success(data.changed
        ? `Stok kg ${product.name} disinkronkan (${data.delta_kg > 0 ? "+" : ""}${formatWeight(data.delta_kg)})`
        : "Stok kg sudah sejalan, tidak ada perubahan");
      onDone();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent data-testid="sync-kg-dialog" className="bg-popover max-w-md">
        <DialogHeader><DialogTitle className="flex items-center gap-2"><RefreshCw className="w-4 h-4" /> Sinkronkan kg — {product.name}</DialogTitle></DialogHeader>
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg border border-border p-2.5">
              <p className="text-[11px] text-muted-foreground">Kg sekarang</p>
              <p className="font-head font-extrabold tabular text-lg">{formatWeight(product.stock_kg)}</p>
            </div>
            <div className="rounded-lg border border-border p-2.5">
              <p className="text-[11px] text-muted-foreground">Ekor</p>
              <p className="font-head font-extrabold tabular text-lg">{formatNumber(product.stock_ekor)}</p>
            </div>
            <div className="rounded-lg border border-primary/40 bg-accent p-2.5">
              <p className="text-[11px] text-muted-foreground">Kg setelah sinkron</p>
              <p className="font-head font-extrabold tabular text-lg text-primary" data-testid="sync-kg-target">{formatWeight(s.expected_kg)}</p>
            </div>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed tabular">
            Kg akan diset ke {formatNumber(product.stock_ekor)} ekor × {formatNumber(s.avg_weight, 2)} kg/ekor = <b>{formatWeight(s.expected_kg)}</b>.
            Perubahan <b className={s.diff_kg > 0 ? "text-destructive" : "text-success"}>{-s.diff_kg > 0 ? "+" : ""}{formatWeight(-s.diff_kg)}</b> dicatat sebagai
            Penyesuaian di Pergerakan Stok & Audit Log, jadi jejaknya tetap ada.
          </p>
          {Math.abs(s.diff_kg) > 5 && (
            <p className="text-[11px] rounded-lg border border-warning/40 bg-warning/10 p-2 text-warning">
              Selisihnya cukup besar. Jika angka kg di lapangan memang benar, pertimbangkan memperbarui berat rata-rata/ekor di Produk & Harga alih-alih menyinkronkan kg.
            </p>
          )}
          <div><Label className="text-xs">Catatan (opsional)</Label>
            <Input data-testid="sync-kg-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="mis. rapikan data lama" className="mt-1" /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>Batal</Button>
          <Button data-testid="sync-kg-confirm" onClick={run} disabled={busy}>{busy ? "Menyinkronkan..." : "Sinkronkan Sekarang"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AdjustDialog({ products, onClose, onSaved }) {
  const [f, setF] = useState({ product_id: "", delta_kg: 0, delta_ekor: 0, delta_pcs: 0, type: "penyesuaian", reason: "" });
  const [busy, setBusy] = useState(false);
  // true selama kolom Kg masih diisi otomatis dari ekor (belum disentuh manual).
  const [kgAuto, setKgAuto] = useState(true);
  // Kolom Pcs hanya relevan untuk produk bersatuan pcs (mis. Ati Ampela).
  const sel = products.find((p) => p.id === f.product_id);
  const pcsOk = !!(sel?.units || []).includes("pcs");
  // Ayam utuh (satuan ekor): kg mengikuti ekor x berat rata-rata/ekor, sama
  // seperti aturan penjualan & produksi potong, supaya stok kg & ekor sinkron.
  const wholeChicken = !!(sel?.units || []).includes("ekor");
  const avgW = Number(sel?.avg_weight_override) > 0
    ? Number(sel.avg_weight_override)
    : Number(sel?.avg_weight_used || sel?.avg_weight_ekor || 0);
  const pickProduct = (v) => {
    const p = products.find((x) => x.id === v);
    const ok = !!(p?.units || []).includes("pcs");
    setKgAuto(true);
    setF((prev) => ({ ...prev, product_id: v, delta_pcs: ok ? prev.delta_pcs : 0 }));
  };
  const changeEkor = (raw) => {
    const e = Number(raw) || 0;
    setF((prev) => {
      const next = { ...prev, delta_ekor: raw };
      if (wholeChicken && kgAuto && avgW > 0) next.delta_kg = e ? Number((e * avgW).toFixed(3)) : 0;
      return next;
    });
  };
  const changeKg = (raw) => { setKgAuto(false); setF((prev) => ({ ...prev, delta_kg: raw })); };
  const save = async () => {
    if (!f.product_id || !f.reason) return toast.error("Lengkapi produk & alasan");
    const d_kg = Number(f.delta_kg) || 0, d_ekor = Number(f.delta_ekor) || 0;
    const d_pcs = pcsOk ? (Number(f.delta_pcs) || 0) : 0;
    if (!d_kg && !d_ekor && !d_pcs) return toast.error("Isi minimal satu perubahan (kg, ekor, atau pcs)");
    setBusy(true);
    try {
      await api.post("/stock-adjustments", { ...f, delta_kg: d_kg, delta_ekor: d_ekor, delta_pcs: d_pcs });
      toast.success("Penyesuaian tersimpan"); onSaved();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover">
        <DialogHeader><DialogTitle>Penyesuaian Stok</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div><Label className="text-xs">Produk</Label>
            <Select value={f.product_id} onValueChange={pickProduct}>
              <SelectTrigger data-testid="adj-product" className="mt-1"><SelectValue placeholder="Pilih produk" /></SelectTrigger>
              <SelectContent className="bg-popover">{products.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div><Label className="text-xs">Jenis</Label>
            <Select value={f.type} onValueChange={(v) => setF({ ...f, type: v })}>
              <SelectTrigger data-testid="adj-type" className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-popover">
                <SelectItem value="penyesuaian">Penyesuaian</SelectItem><SelectItem value="rusak">Ayam Rusak</SelectItem>
                <SelectItem value="salah_potong">Salah Potong</SelectItem><SelectItem value="susut">Susut</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div><Label className="text-xs">Perubahan Kg (+/-)</Label><Input data-testid="adj-kg" type="number" value={f.delta_kg} onChange={(e) => changeKg(e.target.value)} className="mt-1 tabular" /></div>
            <div><Label className="text-xs">Perubahan Ekor (+/-)</Label><Input data-testid="adj-ekor" type="number" value={f.delta_ekor} onChange={(e) => changeEkor(e.target.value)} className="mt-1 tabular" /></div>
            <div>
              <Label className={`text-xs ${pcsOk ? "" : "text-muted-foreground"}`}>Perubahan Pcs (+/-)</Label>
              <Input data-testid="adj-pcs" type="number" disabled={!pcsOk} value={f.delta_pcs}
                onChange={(e) => setF({ ...f, delta_pcs: e.target.value })}
                title={pcsOk ? "" : "Produk ini tidak memakai satuan pcs"}
                className="mt-1 tabular disabled:opacity-50 disabled:cursor-not-allowed" />
            </div>
          </div>
          {f.product_id && !pcsOk && (
            <p className="text-[11px] text-muted-foreground">Produk ini tidak memakai satuan pcs, jadi kolom Pcs dinonaktifkan.</p>
          )}
          {wholeChicken && avgW > 0 && (
            <p className="text-[11px] text-muted-foreground" data-testid="adj-kg-sync-note">
              {kgAuto
                ? <>Kg diisi otomatis dari ekor × {formatNumber(avgW, 2)} kg/ekor agar stok kg & ekor tetap sinkron. Ubah kolom Kg jika berat sebenarnya berbeda.</>
                : <>Kg diisi manual. <button type="button" className="underline hover:text-foreground" data-testid="adj-kg-auto"
                    onClick={() => { setKgAuto(true); const e = Number(f.delta_ekor) || 0; setF((p) => ({ ...p, delta_kg: e ? Number((e * avgW).toFixed(3)) : 0 })); }}>
                    Ikuti ekor lagi</button></>}
            </p>
          )}
          <div><Label className="text-xs">Alasan</Label><Input data-testid="adj-reason" value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} className="mt-1" /></div>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Batal</Button><Button data-testid="save-adjustment" disabled={busy} onClick={save}>Simpan</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
