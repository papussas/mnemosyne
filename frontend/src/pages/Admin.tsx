import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { UserPlus, Pencil, KeyRound, Ban, CheckCircle2 } from "lucide-react";
import { api } from "../lib/api";
import { Button, Input, Select, Field, Card, Modal, Badge } from "../components/ui";
import { PageHeader } from "../components/Layout";
import { useAuth } from "../lib/auth";

export default function Admin() {
  const { me } = useAuth();
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [editUser, setEditUser] = useState<any>(null);
  const [pwUser, setPwUser] = useState<any>(null);
  const [err, setErr] = useState("");
  const [form, setForm] = useState<any>({ email: "", username: "", full_name: "", password: "", role: "contributor" });

  const users = useQuery({ queryKey: ["users"], queryFn: () => api.get("/auth/users").then((r) => r.data) });
  const inval = () => qc.invalidateQueries({ queryKey: ["users"] });

  const create = useMutation({
    mutationFn: () => api.post("/auth/users", form).then((r) => r.data),
    onSuccess: () => { inval(); setAddOpen(false); setErr(""); },
    onError: (e: any) => setErr(e?.response?.data?.detail || "Failed"),
  });
  const patch = useMutation({
    mutationFn: (body: any) => api.patch(`/auth/users/${editUser.id}`, body).then((r) => r.data),
    onSuccess: () => { inval(); setEditUser(null); },
  });
  const toggleActive = useMutation({
    mutationFn: (u: any) => api.patch(`/auth/users/${u.id}`, { is_active: !u.is_active }).then((r) => r.data),
    onSuccess: inval,
  });
  const resetPw = useMutation({
    mutationFn: (pw: string) => api.post(`/auth/users/${pwUser.id}/password`, { new_password: pw }).then((r) => r.data),
    onSuccess: () => setPwUser(null),
  });

  if (me?.role !== "admin") return <div className="text-muted text-sm">Admin access required.</div>;

  return (
    <div>
      <PageHeader title="Admin" subtitle="Manage user accounts. Roles: admin (full control incl. user management) and contributor (read/write)."
        action={<Button onClick={() => { setForm({ email: "", username: "", full_name: "", password: "", role: "contributor" }); setErr(""); setAddOpen(true); }}>
          <span className="flex items-center gap-1.5"><UserPlus size={16} /> Add user</span></Button>} />
      <Card>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-muted border-b border-border">
            <th className="px-5 py-3 font-medium">Username</th><th className="px-5 py-3 font-medium">Email</th>
            <th className="px-5 py-3 font-medium">Name</th><th className="px-5 py-3 font-medium">Role</th>
            <th className="px-5 py-3 font-medium">Status</th><th className="px-5 py-3 font-medium text-right">Actions</th></tr></thead>
          <tbody>
            {users.data?.map((u: any) => (
              <tr key={u.id} className={`border-b border-border/50 ${!u.is_active ? "opacity-50" : ""}`}>
                <td className="px-5 py-3 font-medium">{u.username}</td>
                <td className="px-5 py-3 text-muted">{u.email}</td>
                <td className="px-5 py-3 text-muted">{u.full_name || "—"}</td>
                <td className="px-5 py-3"><Badge>{u.role}</Badge></td>
                <td className="px-5 py-3">{u.is_active ? <span className="text-emerald-400 text-xs">active</span> : <span className="text-red-400 text-xs">disabled</span>}</td>
                <td className="px-5 py-3 text-right whitespace-nowrap">
                  <button onClick={() => setEditUser(u)} title="Edit" className="p-1.5 text-muted hover:text-text align-middle"><Pencil size={15} /></button>
                  <button onClick={() => setPwUser(u)} title="Reset password" className="p-1.5 text-muted hover:text-text align-middle"><KeyRound size={15} /></button>
                  <button onClick={() => toggleActive.mutate(u)} title={u.is_active ? "Disable" : "Enable"} className="p-1.5 text-muted hover:text-text align-middle">
                    {u.is_active ? <Ban size={15} /> : <CheckCircle2 size={15} />}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {/* add */}
      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Add user">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Username"><Input value={form.username} onChange={(e: any) => setForm({ ...form, username: e.target.value })} /></Field>
            <Field label="Role"><Select value={form.role} onChange={(e: any) => setForm({ ...form, role: e.target.value })}>
              <option value="contributor">contributor</option><option value="admin">admin</option></Select></Field>
          </div>
          <Field label="Email"><Input value={form.email} onChange={(e: any) => setForm({ ...form, email: e.target.value })} /></Field>
          <Field label="Full name"><Input value={form.full_name} onChange={(e: any) => setForm({ ...form, full_name: e.target.value })} /></Field>
          <Field label="Temporary password"><Input type="password" value={form.password} onChange={(e: any) => setForm({ ...form, password: e.target.value })} /></Field>
          {err && <p className="text-sm text-amber-400">{err}</p>}
          <div className="flex justify-end gap-2 pt-2"><Button variant="ghost" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button onClick={() => create.mutate()} disabled={!form.username || !form.email || !form.password || create.isPending}>Create</Button></div>
        </div>
      </Modal>

      {/* edit */}
      {editUser && <EditModal user={editUser} onClose={() => setEditUser(null)} onSave={(b: any) => patch.mutate(b)} pending={patch.isPending} />}

      {/* reset pw */}
      {pwUser && <ResetModal user={pwUser} onClose={() => setPwUser(null)} onSave={(pw: string) => resetPw.mutate(pw)} pending={resetPw.isPending} />}
    </div>
  );
}

function EditModal({ user, onClose, onSave, pending }: any) {
  const [f, setF] = useState({ email: user.email, full_name: user.full_name || "", role: user.role, is_active: user.is_active });
  return (
    <Modal open onClose={onClose} title={`Edit ${user.username}`}>
      <div className="space-y-4">
        <Field label="Email"><Input value={f.email} onChange={(e: any) => setF({ ...f, email: e.target.value })} /></Field>
        <Field label="Full name"><Input value={f.full_name} onChange={(e: any) => setF({ ...f, full_name: e.target.value })} /></Field>
        <Field label="Role"><Select value={f.role} onChange={(e: any) => setF({ ...f, role: e.target.value })}>
          <option value="contributor">contributor</option><option value="admin">admin</option></Select></Field>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.is_active} onChange={(e) => setF({ ...f, is_active: e.target.checked })} /> Active</label>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={() => onSave(f)} disabled={pending}>Save</Button></div>
      </div>
    </Modal>
  );
}

function ResetModal({ user, onClose, onSave, pending }: any) {
  const [pw, setPw] = useState("");
  return (
    <Modal open onClose={onClose} title={`Reset password — ${user.username}`}>
      <div className="space-y-4">
        <Field label="New password (min 8)"><Input type="password" value={pw} onChange={(e: any) => setPw(e.target.value)} /></Field>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={() => onSave(pw)} disabled={pw.length < 8 || pending}>Reset</Button></div>
      </div>
    </Modal>
  );
}
