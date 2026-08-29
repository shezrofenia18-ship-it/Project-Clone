import { useCallback, useState } from "react";
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
import { formatRupiah, formatDate, PAYMENT_LABELS } from "@/lib/format";
import { Plus, Camera } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import PayMethodPicker from "@/components/PayMethodPicker";

// "Pembelian Ayam" & "Pembayaran Hutang" TIDAK ada di sini: keduanya dicatat otomatis
// dari modul Pembelian / pembayaran hutang. Kalau dipilih manual, pengeluaran itu akan
// dianggap modal dan tidak ikut mengurangi laba usaha (menyesatkan).
const EXP_CATS = ["Transportasi", "Tenaga Kerja", "Es", "Air", "Listrik", "Plastik", "Kemasan", "Sewa", "Peralatan", "Perawatan", "BBM", "Administrasi", "Marketing", "Pengeluaran Lainnya"];

export default function Finance() {
  const { user } = useAuth();
  const isKasir = user.role === "kasir";
  const [expOpen, setExpOpen] = useState(false);
  const [proof, setProof] = useState(null);
  const { data: expenses, reload: rExp } = useFetch("/expenses");
  const { data: incomes, reload: rInc } = useFetch(isKasir ? null : "/incomes");
  const { data: receivables, reload: rRec } = useFetch("/receivables");
  const { data: payables, reload: rPay } = useFetch(isKasir ? null : "/payables");

  // Halaman ini ikut berubah seketika saat kasir menjual, owner membeli, atau
  // ada pembayaran piutang/hutang — dulu angkanya baru berubah kalau di-refresh manual.
  const reloadAll = useCallback(() => {
    rExp();
    rRec();
    if (!isKasir) {
      rInc();
      rPay();
    }
  }, [rExp, rRec, rInc, rPay, isKasir]);
  useRealtimeReload(["expenses", "incomes", "receivables", "payables", "sales", "customers", "suppliers"], reloadAll);

  return (
    <div className="bam-fade">
      <PageHeader title="Keuangan" subtitle={isKasir ? "Catat pengeluaran operasional & piutang" : "Pemasukan, pengeluaran, piutang & hutang"} />
      <Tabs defaultValue="pengeluaran">
        <TabsList className="flex-wrap h-auto">
          <TabsTrigger value="pengeluaran" data-testid="tab-pengeluaran">Pengeluaran</TabsTrigger>
          {!isKasir && <TabsTrigger value="pemasukan" data-testid="tab-pemasukan">Pemasukan</TabsTrigger>}
          <TabsTrigger value="piutang" data-testid="tab-piutang">Piutang</TabsTrigger>
          {!isKasir && <TabsTrigger value="hutang" data-testid="tab-hutang">Hutang</TabsTrigger>}
        </TabsList>

        <TabsContent value="pengeluaran">
          <div className="flex justify-end mb-3"><Button data-testid="add-expense" onClick={() => setExpOpen(true)}><Plus className="w-4 h-4 mr-1" /> Tambah Pengeluaran</Button></div>
          <Card className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground"><th className="px-4 py-3">Tanggal</th><th className="px-4 py-3">Kategori</th><th className="px-4 py-3">Keterangan</th><th className="px-4 py-3">Bukti</th><th className="px-4 py-3 text-right">Jumlah</th></tr></thead>
              <tbody>{(expenses || []).map((e) => (
                <tr key={e.id} className="border-t border-border" data-testid={`expense-${e.id}`}>
                  <td className="px-4 py-2.5">{formatDate(e.date)}</td>
                  <td className="px-4 py-2.5"><Badge variant="secondary">{e.category}</Badge></td>
                  <td className="px-4 py-2.5 text-muted-foreground">{e.description}</td>
                  <td className="px-4 py-2.5">
                    {e.proof_url ? (
                      <button data-testid={`exp-proof-${e.id}`} onClick={() => setProof(e)} className="block">
                        <img src={e.proof_url} alt="bukti" className="w-10 h-10 rounded-md object-cover border border-border hover:ring-2 hover:ring-primary transition-all" />
                      </button>
                    ) : <span className="text-muted-foreground text-xs">—</span>}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular font-semibold text-destructive">{formatRupiah(e.amount)}</td>
                </tr>
              ))}
              {(expenses || []).length === 0 && <tr><td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">Belum ada pengeluaran.</td></tr>}
              </tbody>
            </table>
          </Card>
        </TabsContent>

        {!isKasir && (
          <TabsContent value="pemasukan">
            <Card className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground"><th className="px-4 py-3">Tanggal</th><th className="px-4 py-3">Kategori</th><th className="px-4 py-3">Sumber</th><th className="px-4 py-3 text-right">Jumlah</th></tr></thead>
                <tbody>{(incomes || []).slice(0, 200).map((e) => (
                  <tr key={e.id} className="border-t border-border"><td className="px-4 py-2.5">{formatDate(e.date)}</td><td className="px-4 py-2.5"><Badge variant="secondary">{e.category}</Badge></td><td className="px-4 py-2.5 text-muted-foreground">{e.source}</td><td className="px-4 py-2.5 text-right tabular font-semibold text-success">{formatRupiah(e.amount)}</td></tr>
                ))}</tbody>
              </table>
            </Card>
          </TabsContent>
        )}

        <TabsContent value="piutang">
          <DebtTable rows={receivables} nameKey="customer_name" onPay={async (id, amt, method) => { await api.post(`/receivables/${id}/pay`, { amount: amt, method }); rRec(); }} testid="receivable" />
        </TabsContent>

        {!isKasir && (
          <TabsContent value="hutang">
            <DebtTable rows={payables} nameKey="supplier_name" onPay={async (id, amt, method) => { await api.post(`/payables/${id}/pay`, { amount: amt, method }); rPay(); }} testid="payable" tone="destructive" />
          </TabsContent>
        )}
      </Tabs>

      {expOpen && <ExpenseDialog onClose={() => setExpOpen(false)} onSaved={() => { setExpOpen(false); rExp(); }} />}
      {proof && (
        <Dialog open onOpenChange={() => setProof(null)}>
          <DialogContent className="bg-popover max-w-lg">
            <DialogHeader>
              <DialogTitle>Bukti Pengeluaran · {proof.category}</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground -mt-2">
              {formatDate(proof.date)} · {formatRupiah(proof.amount)}
              {proof.created_by ? ` · dicatat oleh ${proof.created_by}` : ""}
            </p>
            <img src={proof.proof_url} alt="bukti pengeluaran" data-testid="proof-full"
              className="w-full max-h-[60vh] object-contain rounded-lg border border-border bg-muted" />
            <DialogFooter><Button variant="outline" onClick={() => setProof(null)}>Tutup</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

function DebtTable({ rows, nameKey, onPay, testid, tone = "warning" }) {
  const [pay, setPay] = useState(null);
  const [amt, setAmt] = useState("");
  const [method, setMethod] = useState("cash");
  const submit = async () => {
    if (!Number(amt)) return toast.error("Masukkan nominal pembayaran");
    try {
      await onPay(pay.id, Number(amt), method);
      toast.success(`Pembayaran tercatat · ${PAYMENT_LABELS[method]}`);
      setPay(null); setAmt(""); setMethod("cash");
    } catch (e) { toast.error(apiError(e)); }
  };
  return (
    <Card className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground"><th className="px-4 py-3">Tanggal</th><th className="px-4 py-3">Nama</th><th className="px-4 py-3 text-right">Total</th><th className="px-4 py-3 text-right">Dibayar</th><th className="px-4 py-3 text-right">Sisa</th><th className="px-4 py-3">Metode</th><th className="px-4 py-3"></th></tr></thead>
        <tbody>
          {(rows || []).map((r) => (
            <tr key={r.id} data-testid={`${testid}-${r.id}`} className="border-t border-border">
              <td className="px-4 py-2.5">{formatDate(r.date)}</td><td className="px-4 py-2.5 font-medium">{r[nameKey]}</td>
              <td className="px-4 py-2.5 text-right tabular">{formatRupiah(r.amount)}</td>
              <td className="px-4 py-2.5 text-right tabular text-success">{formatRupiah(r.paid)}</td>
              <td className={`px-4 py-2.5 text-right tabular font-semibold text-${tone}`}>{formatRupiah(r.remaining)}</td>
              <td className="px-4 py-2.5">
                {r.last_method
                  ? <Badge variant="secondary" data-testid={`method-${r.id}`}>{PAYMENT_LABELS[r.last_method] || r.last_method}</Badge>
                  : <span className="text-muted-foreground text-xs">—</span>}
              </td>
              <td className="px-4 py-2.5 text-right">{r.status !== "lunas" ? <Button size="sm" variant="outline" data-testid={`pay-${testid}-${r.id}`} onClick={() => { setPay(r); setAmt(String(r.remaining)); setMethod("cash"); }}>Bayar</Button> : <Badge className="bg-success text-white">Lunas</Badge>}</td>
            </tr>
          ))}
          {(rows || []).length === 0 && <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">Tidak ada data.</td></tr>}
        </tbody>
      </table>
      {pay && (
        <Dialog open onOpenChange={() => setPay(null)}>
          <DialogContent className="bg-popover">
            <DialogHeader><DialogTitle>Pembayaran · {pay[nameKey]}</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label className="text-xs">Jumlah Bayar (sisa {formatRupiah(pay.remaining)})</Label><Input data-testid="pay-amount" type="number" value={amt} onChange={(e) => setAmt(e.target.value)} className="mt-1 tabular" /></div>
              <PayMethodPicker
                value={method} onChange={setMethod} testid="debt-pay-method"
                label={nameKey === "supplier_name" ? "Uang Dibayar Lewat" : "Uang Diterima Lewat"}
              />
            </div>
            <DialogFooter><Button variant="outline" onClick={() => setPay(null)}>Batal</Button><Button data-testid="confirm-pay" onClick={submit}>Bayar</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </Card>
  );
}

function ExpenseDialog({ onClose, onSaved }) {
  const [f, setF] = useState({ category: "Pengeluaran Lainnya", amount: 0, description: "", proof_url: "", proof_file_id: "" });
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const onUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("folder", "proofs");
    try {
      const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setF((p) => ({ ...p, proof_file_id: data.id, proof_url: `${process.env.REACT_APP_BACKEND_URL}${data.url}` }));
      toast.success("Foto bukti terunggah");
    } catch (e2) { toast.error(apiError(e2)); } finally { setUploading(false); }
  };
  const save = async () => {
    if (!Number(f.amount)) return toast.error("Jumlah wajib diisi");
    setBusy(true);
    try { await api.post("/expenses", { ...f, amount: Number(f.amount) }); toast.success("Pengeluaran tersimpan"); onSaved(); }
    catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>Tambah Pengeluaran</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div><Label className="text-xs">Kategori</Label>
            <Select value={f.category} onValueChange={(v) => setF({ ...f, category: v })}>
              <SelectTrigger data-testid="exp-cat" className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-popover max-h-64">{EXP_CATS.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div><Label className="text-xs">Jumlah</Label><Input data-testid="exp-amount" type="number" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} className="mt-1 tabular" /></div>
          <div><Label className="text-xs">Keterangan</Label><Input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="mt-1" /></div>
          <div>
            <Label className="text-xs">Foto Bukti Pengeluaran <span className="text-muted-foreground">(opsional)</span></Label>
            <div className="mt-1.5 flex items-start gap-3">
              {f.proof_url
                ? <img src={f.proof_url} alt="bukti" data-testid="exp-proof-preview" className="w-20 h-20 rounded-lg object-cover border border-border" />
                : <div className="w-20 h-20 rounded-lg border border-dashed border-border flex items-center justify-center text-muted-foreground shrink-0"><Camera className="w-6 h-6" /></div>}
              <div className="min-w-0 flex-1">
                <Input
                  data-testid="exp-proof-file" type="file" accept="image/*" capture="environment"
                  onChange={onUpload} disabled={uploading}
                />
                <p className="text-[11px] text-muted-foreground mt-1">
                  {uploading ? "Mengunggah foto..." : "Boleh langsung ambil foto dari kamera. Maksimal 10 MB."}
                </p>
                {f.proof_url && (
                  <Button
                    type="button" variant="ghost" size="sm" data-testid="exp-proof-clear"
                    className="h-7 px-2 mt-1 text-xs text-destructive"
                    onClick={() => setF((p) => ({ ...p, proof_url: "", proof_file_id: "" }))}
                  >
                    Hapus foto
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Batal</Button><Button data-testid="save-expense" disabled={busy || uploading} onClick={save}>Simpan</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
