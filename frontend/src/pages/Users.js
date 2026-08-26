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
import { Plus } from "lucide-react";

const ROLES = { owner: "Owner", admin: "Admin", kasir: "Kasir", operator: "Operator" };
const ROLE_TONE = { owner: "bg-primary/10 text-primary", admin: "bg-chart-4/10 text-chart-4", kasir: "bg-success/15 text-success", operator: "bg-warning/20 text-warning" };

export default function Users() {
  const { data, reload } = useFetch("/auth/users");
  const [open, setOpen] = useState(false);

  return (
    <div className="bam-fade">
      <PageHeader title="Pengguna" subtitle="Kelola akun & role staf"
        actions={<Button data-testid="add-user" onClick={() => setOpen(true)}><Plus className="w-4 h-4 mr-1" /> Tambah Pengguna</Button>} />
      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50"><tr className="text-left text-xs text-muted-foreground"><th className="px-4 py-3">Nama</th><th className="px-4 py-3">Email</th><th className="px-4 py-3">Role</th><th className="px-4 py-3">Status</th></tr></thead>
          <tbody>
            {(data || []).map((u) => (
              <tr key={u.id} data-testid={`user-${u.id}`} className="border-t border-border">
                <td className="px-4 py-3 font-medium">{u.name}</td>
                <td className="px-4 py-3 text-muted-foreground">{u.email}</td>
                <td className="px-4 py-3"><Badge className={ROLE_TONE[u.role]}>{ROLES[u.role]}</Badge></td>
                <td className="px-4 py-3">{u.active === false ? <Badge variant="secondary">Nonaktif</Badge> : <Badge className="bg-success text-white">Aktif</Badge>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {open && <UserDialog onClose={() => setOpen(false)} onSaved={() => { setOpen(false); reload(); }} />}
    </div>
  );
}

function UserDialog({ onClose, onSaved }) {
  const [f, setF] = useState({ name: "", email: "", password: "", role: "kasir" });
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const save = async () => {
    if (!f.name || !f.email || !f.password) return toast.error("Lengkapi semua field");
    setBusy(true);
    try { await api.post("/auth/users", f); toast.success("Pengguna dibuat"); onSaved(); }
    catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover">
        <DialogHeader><DialogTitle>Tambah Pengguna</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div><Label className="text-xs">Nama</Label><Input data-testid="user-name" value={f.name} onChange={(e) => set("name", e.target.value)} className="mt-1" /></div>
          <div><Label className="text-xs">Email</Label><Input data-testid="user-email" type="email" value={f.email} onChange={(e) => set("email", e.target.value)} className="mt-1" /></div>
          <div><Label className="text-xs">Kata Sandi</Label><Input data-testid="user-password" type="text" value={f.password} onChange={(e) => set("password", e.target.value)} className="mt-1" /></div>
          <div><Label className="text-xs">Role</Label>
            <Select value={f.role} onValueChange={(v) => set("role", v)}>
              <SelectTrigger data-testid="user-role" className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-popover">{Object.entries(ROLES).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Batal</Button><Button data-testid="save-user" disabled={busy} onClick={save}>Simpan</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
