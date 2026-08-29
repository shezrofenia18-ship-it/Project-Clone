import { useState, useEffect } from "react";
import api, { apiError } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";

export default function Settings() {
  const [s, setS] = useState({ store_name: "", store_address: "", store_phone: "", allow_negative_stock: false });

  useEffect(() => {
    api.get("/settings").then((r) => setS({
      store_name: r.data.store_name || "Berkah Ayam Mili",
      store_address: r.data.store_address || "",
      store_phone: r.data.store_phone || "",
      allow_negative_stock: !!r.data.allow_negative_stock,
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
      </Card>
    </div>
  );
}
