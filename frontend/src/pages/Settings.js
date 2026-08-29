import { useState, useEffect } from "react";
import api, { apiError } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { formatRupiah } from "@/lib/format";
import { MessageCircle, Plus, Trash2, Loader2, Send, Printer, RefreshCw, ShieldCheck, AlertTriangle } from "lucide-react";
import { printReceipt, sampleSale, RECEIPT_PAPER_MM } from "@/lib/receipt";

// Pemeriksaan & perbaikan sinkronisasi data antar modul (penjualan, pembelian,
// pengeluaran, piutang/hutang, saldo pelanggan & supplier).
function DataSyncSettings() {
  const [busy, setBusy] = useState("");
  const [res, setRes] = useState(null);

  const run = async (mode) => {
    setBusy(mode);
    try {
      const r = mode === "fix"
        ? await api.post("/maintenance/reconcile")
        : await api.get("/maintenance/consistency");
      setRes(r.data);
      if (mode === "fix") {
        toast.success(r.data.fixed_count > 0
          ? `${r.data.fixed_count} data dirapikan`
          : "Semua data sudah sinkron — tidak ada yang perlu diperbaiki");
      } else {
        toast[r.data.issue_count > 0 ? "warning" : "success"](
          r.data.issue_count > 0
            ? `Ditemukan ${r.data.issue_count} data tidak sinkron`
            : "Semua data sinkron");
      }
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="space-y-3 border-t border-border pt-5" data-testid="data-sync-card">
      <div>
        <p className="font-semibold text-sm flex items-center gap-1.5">
          <ShieldCheck className="w-4 h-4 text-primary" /> Sinkronisasi Data
        </p>
        <p className="text-xs text-muted-foreground">
          Memastikan angka di Penjualan, Pembelian, Pengeluaran, Keuangan, Laporan, dan Riwayat
          selalu cocok satu sama lain. Aman dijalankan kapan saja.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" data-testid="sync-check" disabled={!!busy} onClick={() => run("check")}>
          {busy === "check" ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-1" />}
          Periksa Data
        </Button>
        <Button data-testid="sync-fix" disabled={!!busy} onClick={() => run("fix")}>
          {busy === "fix" ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <ShieldCheck className="w-4 h-4 mr-1" />}
          Perbaiki Sekarang
        </Button>
      </div>
      {res && (
        <div className="rounded-lg bg-muted/40 p-3 space-y-1.5" data-testid="sync-result">
          <p className="text-xs font-semibold flex items-center gap-1.5">
            {res.issue_count > 0
              ? <><AlertTriangle className="w-3.5 h-3.5 text-warning" /> {res.issue_count} temuan{res.repaired ? ` · ${res.fixed_count} diperbaiki` : ""}</>
              : <><ShieldCheck className="w-3.5 h-3.5 text-success" /> Semua data sinkron</>}
          </p>
          {(res.findings || []).slice(0, 8).map((f, i) => (
            <p key={`f-${i}`} className="text-[11px] text-muted-foreground">
              • {f.label} — {f.detail}{f.amount ? ` (${formatRupiah(f.amount)})` : ""}
            </p>
          ))}
          {(res.findings || []).length > 8 && (
            <p className="text-[11px] text-muted-foreground">…dan {res.findings.length - 8} lainnya</p>
          )}
        </div>
      )}
    </div>
  );
}

// Rekap tutup buku harian dikirim ke WhatsApp. Nomor bisa ditambah/diubah kapan saja.
function WhatsAppSettings() {
  const [w, setW] = useState(null);
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [log, setLog] = useState([]);

  const loadLog = () => api.get("/whatsapp/log?limit=5").then((r) => setLog(r.data || [])).catch(() => {});

  useEffect(() => {
    api.get("/whatsapp/settings")
      .then((r) => setW({ ...r.data, recipients: r.data.recipients?.length ? r.data.recipients : [{ name: "", number: "" }] }))
      .catch((e) => toast.error(apiError(e)));
    loadLog();
  }, []);

  if (!w) return <div className="h-24 rounded-xl bg-muted animate-pulse" />;

  const setRec = (i, k, v) => setW((p) => {
    const recipients = p.recipients.map((r, idx) => (idx === i ? { ...r, [k]: v } : r));
    return { ...p, recipients };
  });
  const addRec = () => setW((p) => ({ ...p, recipients: [...p.recipients, { name: "", number: "" }] }));
  const delRec = (i) => setW((p) => ({ ...p, recipients: p.recipients.filter((_, idx) => idx !== i) }));

  const save = async () => {
    setBusy(true);
    try {
      const body = {
        recipients: w.recipients.filter((r) => (r.number || "").trim()),
        auto_enabled: !!w.auto_enabled,
        auto_time: w.auto_time || "21:00",
      };
      const r = await api.put("/whatsapp/settings", body);
      setW({ ...r.data, recipients: r.data.recipients?.length ? r.data.recipients : [{ name: "", number: "" }] });
      toast.success("Pengaturan rekap WhatsApp disimpan");
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setBusy(false);
    }
  };

  const configured = w.provider?.configured;

  const sendTest = async () => {
    setTesting(true);
    try {
      const { data } = await api.post("/whatsapp/test");
      if (data.mode === "auto") {
        toast.success(`Pesan uji terkirim ke ${data.sent_count} nomor`);
      } else {
        const link = data.results?.[0]?.link;
        if (link) window.open(link, "_blank");
        toast.info("Provider belum dikonfigurasi — WhatsApp dibuka dengan pesan uji siap kirim");
      }
      loadLog();
    } catch (e) { toast.error(apiError(e)); } finally { setTesting(false); }
  };

  return (
    <div className="space-y-3 border-t border-border pt-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-sm flex items-center gap-1.5">
            <MessageCircle className="w-4 h-4 text-success" /> Rekap WhatsApp
          </p>
          <p className="text-xs text-muted-foreground">
            Rekap tutup buku (omzet, laba, uang masuk, piutang, stok sisa) dikirim ke nomor di bawah.
          </p>
        </div>
        <Badge className={configured
          ? "bg-success/15 text-success hover:bg-success/15 shrink-0"
          : "bg-warning/20 text-warning hover:bg-warning/20 shrink-0"}
          data-testid="wa-provider-badge">
          {configured ? "Otomatis penuh" : "Mode 1-tap"}
        </Badge>
      </div>

      {!configured && (
        <p className="text-[11px] text-muted-foreground leading-relaxed rounded-lg bg-muted/40 p-2.5">
          Pengiriman otomatis penuh belum aktif karena kredensial WhatsApp Business (Meta Cloud API) belum diisi.
          Sementara ini, setelah tutup buku akan muncul tombol <b>Kirim</b> yang membuka WhatsApp dengan teks rekap
          sudah siap — tinggal ditekan sekali.
        </p>
      )}

      <div className="space-y-2">
        {w.recipients.map((r, i) => (
          <div key={`rec-${i}`} className="flex items-end gap-2">
            <div className="flex-1">
              <Label className="text-xs">Nama</Label>
              <Input data-testid={`wa-name-${i}`} className="mt-1" placeholder="mis. Owner / Istri / Manajer"
                value={r.name} onChange={(e) => setRec(i, "name", e.target.value)} />
            </div>
            <div className="flex-1">
              <Label className="text-xs">Nomor WhatsApp</Label>
              <Input data-testid={`wa-number-${i}`} className="mt-1 tabular" placeholder="mis. 081289478221"
                value={r.number} onChange={(e) => setRec(i, "number", e.target.value)} />
            </div>
            <Button variant="ghost" size="sm" data-testid={`wa-del-${i}`} onClick={() => delRec(i)}
              disabled={w.recipients.length === 1}>
              <Trash2 className="w-4 h-4 text-destructive" />
            </Button>
          </div>
        ))}
        <Button variant="outline" size="sm" data-testid="wa-add" onClick={addRec}>
          <Plus className="w-4 h-4 mr-1" /> Tambah Nomor
        </Button>
        <p className="text-[11px] text-muted-foreground">
          Nomor 08... otomatis diubah ke format internasional 62...
        </p>
      </div>

      <div className="flex items-center justify-between pt-2">
        <div>
          <p className="font-semibold text-sm">Tutup Buku & Kirim Otomatis</p>
          <p className="text-xs text-muted-foreground">
            Setiap hari pada jam ini, sistem menutup buku sendiri lalu menyiapkan/mengirim rekap.
          </p>
        </div>
        <Switch data-testid="wa-auto-toggle" checked={!!w.auto_enabled}
          onCheckedChange={(v) => setW((p) => ({ ...p, auto_enabled: v }))} />
      </div>
      <div className="w-40">
        <Label className="text-xs">Jam kirim (WIB)</Label>
        <Input data-testid="wa-auto-time" type="time" className="mt-1" value={w.auto_time || "21:00"}
          onChange={(e) => setW((p) => ({ ...p, auto_time: e.target.value }))} />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button data-testid="wa-save" disabled={busy} onClick={save}>
          {busy && <Loader2 className="w-4 h-4 mr-1 animate-spin" />} Simpan Pengaturan WhatsApp
        </Button>
        <Button variant="outline" data-testid="wa-test" disabled={testing} onClick={sendTest}>
          {testing ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Send className="w-4 h-4 mr-1" />}
          Kirim Uji Coba
        </Button>
      </div>

      {log.length > 0 && (
        <div className="pt-2" data-testid="wa-log">
          <p className="text-xs font-semibold mb-1.5">Riwayat pengiriman terakhir</p>
          <div className="space-y-1">
            {log.map((l) => (
              <div key={l.id} className="text-[11px] text-muted-foreground flex items-center gap-2">
                <span className="tabular">{(l.created_at || "").slice(0, 16).replace("T", " ")}</span>
                <Badge variant="secondary" className="text-[10px]">{l.trigger}</Badge>
                <span>{l.kind === "test" ? "uji coba" : `rekap ${l.date}`}</span>
                <span className={l.sent_count > 0 ? "text-success" : "text-warning"}>
                  {l.sent_count > 0 ? `terkirim ${l.sent_count} nomor` : "disiapkan (mode 1-tap)"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Settings() {
  const [s, setS] = useState({ store_name: "", store_address: "", store_phone: "", allow_negative_stock: false, receipt_auto_print: false });

  useEffect(() => {
    api.get("/settings").then((r) => setS({
      store_name: r.data.store_name || "Berkah Ayam Mili",
      store_address: r.data.store_address || "",
      store_phone: r.data.store_phone || "",
      allow_negative_stock: !!r.data.allow_negative_stock,
      receipt_auto_print: !!r.data.receipt_auto_print,
    }));
  }, []);

  const put = async (key, value) => {
    try { await api.put("/settings", { key, value }); toast.success("Pengaturan disimpan"); }
    catch (e) { toast.error(apiError(e)); }
  };

  const saveIdentity = async () => {
    await put("store_name", s.store_name);
    await api.put("/settings", { key: "store_address", value: s.store_address }).catch(() => {});
    await api.put("/settings", { key: "store_phone", value: s.store_phone }).catch(() => {});
  };

  return (
    <div className="bam-fade max-w-xl">
      <PageHeader title="Pengaturan" subtitle="Konfigurasi toko & stok" />
      <Card className="p-6 space-y-6">
        <div className="space-y-3">
          <div>
            <p className="font-semibold text-sm">Identitas Toko</p>
            <p className="text-xs text-muted-foreground">Dipakai sebagai kop pada struk penjualan dan laporan PDF.</p>
          </div>
          <div>
            <Label className="text-xs">Nama Toko</Label>
            <Input data-testid="set-store-name" className="mt-1" value={s.store_name}
              onChange={(e) => setS({ ...s, store_name: e.target.value })} />
          </div>
          <div>
            <Label className="text-xs">Alamat Toko</Label>
            <Input data-testid="set-store-address" className="mt-1" placeholder="mis. Jl. Raya Pasar No. 12, Blitar"
              value={s.store_address} onChange={(e) => setS({ ...s, store_address: e.target.value })} />
          </div>
          <div>
            <Label className="text-xs">Nomor Telepon / WhatsApp</Label>
            <Input data-testid="set-store-phone" className="mt-1" placeholder="mis. 081234567890"
              value={s.store_phone} onChange={(e) => setS({ ...s, store_phone: e.target.value })} />
            <p className="text-[11px] text-muted-foreground mt-1">Kosongkan bila tidak ingin dicetak di struk & laporan.</p>
          </div>
          <Button data-testid="save-store-name" onClick={saveIdentity}>Simpan Identitas Toko</Button>
        </div>
        <div className="flex items-center justify-between border-t border-border pt-5">
          <div>
            <p className="font-semibold text-sm">Izinkan Stok Negatif</p>
            <p className="text-xs text-muted-foreground">Jika aktif, penjualan tetap bisa walau stok tidak cukup.</p>
          </div>
          <Switch data-testid="toggle-negative-stock" checked={s.allow_negative_stock}
            onCheckedChange={(v) => { setS({ ...s, allow_negative_stock: v }); put("allow_negative_stock", v); }} />
        </div>
        {/* Struk & printer termal kasir */}
        <div className="space-y-3 border-t border-border pt-5" data-testid="receipt-settings">
          <div>
            <p className="font-semibold text-sm flex items-center gap-1.5">
              <Printer className="w-4 h-4 text-primary" /> Struk & Printer
            </p>
            <p className="text-xs text-muted-foreground">
              Struk dicetak untuk printer termal <b>{RECEIPT_PAPER_MM}mm</b> (lebar kertas kasir).
              Pastikan printer termal sudah terpasang di tablet/PC kasir.
            </p>
          </div>
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="font-semibold text-sm">Cetak Struk Otomatis</p>
              <p className="text-xs text-muted-foreground">
                Begitu transaksi selesai, struk langsung dikirim ke printer tanpa kasir menekan tombol.
              </p>
            </div>
            <Switch data-testid="toggle-auto-print" checked={s.receipt_auto_print}
              onCheckedChange={(v) => { setS({ ...s, receipt_auto_print: v }); put("receipt_auto_print", v); }} />
          </div>
          <Button variant="outline" data-testid="test-print"
            onClick={() => {
              printReceipt(sampleSale(), {
                name: s.store_name, address: s.store_address, phone: s.store_phone,
              });
              toast.info("Struk contoh dikirim ke dialog cetak");
            }}>
            <Printer className="w-4 h-4 mr-1" /> Tes Cetak Struk
          </Button>
        </div>
        <DataSyncSettings />
        <WhatsAppSettings />
      </Card>
    </div>
  );
}
