import { useState } from "react";
import api, { apiError } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, UserCheck, UserX, AlertTriangle } from "lucide-react";

const ROLES = { owner: "Owner", admin: "Admin", kasir: "Kasir" };
const ROLE_TONE = { owner: "bg-primary/10 text-primary", admin: "bg-chart-4/10 text-chart-4", kasir: "bg-success/15 text-success", operator: "bg-warning/20 text-warning" };

export default function Users() {
  const { data, reload } = useFetch("/auth/users");
  const { user: me } = useAuth();
  // dialog: null | { mode: "create" } | { mode: "edit", row }
  const [dialog, setDialog] = useState(null);
  const [toDelete, setToDelete] = useState(null);
  const [busyId, setBusyId] = useState(null);
  // Halaman ini juga bisa dilihat Admin, tapi HANYA Owner yang boleh mengubah.
  const isOwner = me?.role === "owner";

  const toggleActive = async (row) => {
    const activating = row.active === false;
    setBusyId(row.id);
    try {
      await api.put(`/auth/users/${row.id}`, { active: activating });
      toast.success(activating ? `${row.name} diaktifkan` : `${row.name} dinonaktifkan`);
      reload();
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="bam-fade">
      <PageHeader title="Pengguna" subtitle="Kelola akun & role staf"
        actions={isOwner && (
          <Button data-testid="add-user" onClick={() => setDialog({ mode: "create" })}>
            <Plus className="w-4 h-4 mr-1" /> Tambah Pengguna
          </Button>
        )} />
      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr className="text-left text-xs text-muted-foreground">
              <th className="px-4 py-3">Nama</th>
              <th className="px-4 py-3">Username</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Status</th>
              {isOwner && <th className="px-4 py-3 text-right">Aksi</th>}
            </tr>
          </thead>
          <tbody>
            {(data || []).map((u) => {
              const isSelf = u.id === me?.id;
              return (
                <tr key={u.id} data-testid={`user-${u.id}`} className="border-t border-border">
                  <td className="px-4 py-3 font-medium">
                    {u.name}
                    {isSelf && <span className="ml-1.5 text-[10px] font-semibold text-primary">(Anda)</span>}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground font-mono text-xs">{u.username}</td>
                  <td className="px-4 py-3"><Badge className={ROLE_TONE[u.role]}>{ROLES[u.role]}</Badge></td>
                  <td className="px-4 py-3">{u.active === false ? <Badge variant="secondary">Nonaktif</Badge> : <Badge className="bg-success text-white">Aktif</Badge>}</td>
                  {isOwner && (
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button variant="outline" size="sm" className="h-8 px-2"
                          data-testid={`edit-user-${u.id}`} title="Ubah pengguna"
                          onClick={() => setDialog({ mode: "edit", row: u })}>
                          <Pencil className="w-3.5 h-3.5" />
                          <span className="hidden lg:inline ml-1">Ubah</span>
                        </Button>
                        <Button variant="outline" size="sm" className="h-8 px-2"
                          data-testid={`toggle-user-${u.id}`} disabled={isSelf || busyId === u.id}
                          title={isSelf ? "Tidak bisa menonaktifkan akun sendiri" : (u.active === false ? "Aktifkan" : "Nonaktifkan")}
                          onClick={() => toggleActive(u)}>
                          {u.active === false ? <UserCheck className="w-3.5 h-3.5" /> : <UserX className="w-3.5 h-3.5" />}
                          <span className="hidden lg:inline ml-1">{u.active === false ? "Aktifkan" : "Nonaktifkan"}</span>
                        </Button>
                        <Button variant="outline" size="sm"
                          className="h-8 px-2 text-destructive hover:bg-destructive hover:text-white"
                          data-testid={`delete-user-${u.id}`} disabled={isSelf}
                          title={isSelf ? "Tidak bisa menghapus akun sendiri" : "Hapus permanen"}
                          onClick={() => setToDelete(u)}>
                          <Trash2 className="w-3.5 h-3.5" />
                          <span className="hidden lg:inline ml-1">Hapus</span>
                        </Button>
                      </div>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
      {!isOwner && (
        <p className="mt-3 text-xs text-muted-foreground px-1">
          Hanya Owner yang dapat menambah, mengubah, atau menghapus pengguna.
        </p>
      )}
      {dialog && (
        <UserDialog mode={dialog.mode} row={dialog.row}
          onClose={() => setDialog(null)}
          onSaved={() => { setDialog(null); reload(); }} />
      )}
      {toDelete && (
        <DeleteUserDialog row={toDelete}
          onClose={() => setToDelete(null)}
          onDeleted={() => { setToDelete(null); reload(); }} />
      )}
    </div>
  );
}

function UserDialog({ mode, row, onClose, onSaved }) {
  const editing = mode === "edit";
  const [f, setF] = useState({
    name: row?.name || "",
    username: row?.username || "",
    password: "",
    role: row?.role || "kasir",
    active: row ? row.active !== false : true,
  });
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const save = async () => {
    if (!f.name.trim() || !f.username.trim()) return toast.error("Nama & username wajib diisi");
    // Saat menambah, kata sandi wajib. Saat mengubah, kosong = biarkan yang lama.
    if (!editing && !f.password) return toast.error("Kata sandi wajib diisi");
    if (f.password && f.password.length < 6) return toast.error("Kata sandi minimal 6 karakter");
    setBusy(true);
    try {
      if (editing) {
        const body = { name: f.name.trim(), username: f.username.trim(), role: f.role, active: f.active };
        if (f.password) body.password = f.password;
        await api.put(`/auth/users/${row.id}`, body);
        toast.success("Pengguna diperbarui");
      } else {
        await api.post("/auth/users", { ...f, name: f.name.trim(), username: f.username.trim() });
        toast.success("Pengguna dibuat");
      }
      onSaved();
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover">
        <DialogHeader>
          <DialogTitle>{editing ? "Ubah Pengguna" : "Tambah Pengguna"}</DialogTitle>
          <DialogDescription className="text-xs">
            {editing
              ? "Kosongkan kata sandi bila tidak ingin menggantinya."
              : "Akun baru langsung bisa dipakai untuk masuk."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div><Label className="text-xs">Nama</Label><Input data-testid="user-name" value={f.name} onChange={(e) => set("name", e.target.value)} className="mt-1" /></div>
          <div>
            <Label className="text-xs">Username</Label>
            <Input data-testid="user-username" value={f.username}
              onChange={(e) => set("username", e.target.value.replace(/\s/g, "").toLowerCase())}
              placeholder="mis. kasir_andi" autoCapitalize="none" autoCorrect="off"
              spellCheck="false" className="mt-1 font-mono" />
            <p className="text-[11px] text-muted-foreground mt-1">Minimal 5 karakter, tanpa spasi. Dipakai untuk masuk.</p>
          </div>
          <div>
            <Label className="text-xs">{editing ? "Kata Sandi Baru (opsional)" : "Kata Sandi"}</Label>
            <Input data-testid="user-password" type="text" value={f.password}
              placeholder={editing ? "Biarkan kosong = tidak diubah" : ""}
              onChange={(e) => set("password", e.target.value)} className="mt-1" />
          </div>
          <div><Label className="text-xs">Role</Label>
            <Select value={f.role} onValueChange={(v) => set("role", v)}>
              <SelectTrigger data-testid="user-role" className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-popover">{Object.entries(ROLES).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          {editing && (
            <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
              <div>
                <p className="text-xs font-semibold">Akun Aktif</p>
                <p className="text-[11px] text-muted-foreground">Nonaktif = tidak bisa masuk, riwayat tetap utuh.</p>
              </div>
              <Switch data-testid="user-active" checked={f.active} onCheckedChange={(v) => set("active", v)} />
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Batal</Button>
          <Button data-testid="save-user" disabled={busy} onClick={save}>Simpan</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DeleteUserDialog({ row, onClose, onDeleted }) {
  const [busy, setBusy] = useState(false);
  const remove = async () => {
    setBusy(true);
    try {
      await api.delete(`/auth/users/${row.id}`);
      toast.success(`${row.name} dihapus`);
      onDeleted();
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-popover max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="w-4 h-4" /> Hapus Pengguna
          </DialogTitle>
          <DialogDescription className="text-xs">Tindakan ini tidak bisa dibatalkan.</DialogDescription>
        </DialogHeader>
        <div className="rounded-lg border border-border px-3 py-2.5">
          <p className="text-sm font-semibold">{row.name}</p>
          <p className="text-xs text-muted-foreground">{row.username} · {ROLES[row.role]}</p>
        </div>
        <p className="text-[11px] text-muted-foreground leading-relaxed">
          Riwayat transaksi milik akun ini TIDAK hilang — laporan lama tetap menampilkan namanya.
          Bila hanya ingin menutup akses, pakai <span className="font-semibold">Nonaktifkan</span> saja.
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Batal</Button>
          <Button data-testid="confirm-delete-user" disabled={busy} onClick={remove}
            className="bg-destructive text-white hover:bg-destructive/90">
            Hapus Permanen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
