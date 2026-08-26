import { useState } from "react";
import api, { apiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { formatRupiah, CUSTOMER_TYPES } from "@/lib/format";
import { Plus, Pencil, Phone } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function Customers() {
  const { user } = useAuth();
  const { data, reload } = useFetch("/customers");
  const [edit, setEdit] = useState(null);
  const canEdit = ["owner", "admin"].includes(user.role);

  return (
    <div className="bam-fade">
      <PageHeader title="Pelanggan" subtitle="Data pelanggan, jenis & piutang"
        actions={<Button data-testid="add-customer" onClick={() => setEdit({})}><Plus className="w-4 h-4 mr-1" /> Tambah</Button>} />
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {(data || []).map((c) => (
          <Card key={c.id} data-testid={`customer-${c.id}`} className="p-4 bam-card-hover">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-semibold">{c.name}</p>
                <Badge variant="secondary" className="mt-1 text-[10px]">{CUSTOMER_TYPES[c.type] || c.type}</Badge>
              </div>
              {canEdit && <Button variant="ghost" size="icon" onClick={() => setEdit(c)}><Pencil className="w-4 h-4" /></Button>}
            </div>
            {c.phone && <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1"><Phone className="w-3 h-3" /> {c.phone}</p>}
            <div className="flex justify-between mt-3 text-sm">
              <div><p className="text-[11px] text-muted-foreground">Total Beli</p><p className="font-semibold tabular">{formatRupiah(c.total_purchase)}</p></div>
              <div className="text-right"><p className="text-[11px] text-muted-foreground">Piutang</p><p className={`font-semibold tabular ${c.receivable > 0 ? "text-warning" : ""}`}>{formatRupiah(c.receivable)}</p></div>
            </div>
          </Card>
        ))}
      </div>
      {edit && <CustomerDialog init={edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); reload(); }} />}
    </div>
  );
}

function CustomerDialog({ init, onClose, onSaved }) {
  const [f, setF] = useState({ name: "", phone: "", address: "", type: "umum", ...init });
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const save = async () => {
    if (!f.name) return toast.error("Nama wajib diisi");
    setBusy(true);
    const body = { name: f.name, phone: f.phone || "", address: f.address || "", type: f.type, special_prices: f.special_prices || {} };
    try {
      if (init.id) await api.put(`/customers/${init.id}`, body); else await api.post("/customers", body);
      toast.success("Pelanggan disimpan"); onSaved();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover">
        <DialogHeader><DialogTitle>{init.id ? "Edit" : "Tambah"} Pelanggan</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div><Label className="text-xs">Nama</Label><Input data-testid="cust-name" value={f.name} onChange={(e) => set("name", e.target.value)} className="mt-1" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-xs">No. HP</Label><Input value={f.phone} onChange={(e) => set("phone", e.target.value)} className="mt-1" /></div>
            <div><Label className="text-xs">Jenis</Label>
              <Select value={f.type} onValueChange={(v) => set("type", v)}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-popover">{Object.entries(CUSTOMER_TYPES).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div><Label className="text-xs">Alamat</Label><Input value={f.address} onChange={(e) => set("address", e.target.value)} className="mt-1" /></div>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Batal</Button><Button data-testid="save-customer" disabled={busy} onClick={save}>Simpan</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
