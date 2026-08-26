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
  const [s, setS] = useState({ store_name: "", allow_negative_stock: false });

  useEffect(() => {
    api.get("/settings").then((r) => setS({
      store_name: r.data.store_name || "Berkah Ayam Mili",
      allow_negative_stock: !!r.data.allow_negative_stock,
    }));
  }, []);

  const put = async (key, value) => {
    try { await api.put("/settings", { key, value }); toast.success("Pengaturan disimpan"); }
    catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="bam-fade max-w-xl">
      <PageHeader title="Pengaturan" subtitle="Konfigurasi toko & stok" />
      <Card className="p-6 space-y-6">
        <div>
          <Label className="text-xs">Nama Toko</Label>
          <div className="flex gap-2 mt-1">
            <Input data-testid="set-store-name" value={s.store_name} onChange={(e) => setS({ ...s, store_name: e.target.value })} />
            <Button data-testid="save-store-name" onClick={() => put("store_name", s.store_name)}>Simpan</Button>
          </div>
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
