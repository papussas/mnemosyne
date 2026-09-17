import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, ChevronRight } from "lucide-react";
import { crud } from "../lib/api";
import { Button, Input, Textarea, Field, Card, Modal } from "../components/ui";
import { PageHeader } from "../components/Layout";

export default function Clients() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const { data } = useQuery({ queryKey: ["clients"], queryFn: () => crud.list("/clients") });
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [form, setForm] = useState({ name: "", description: "" });

  const save = useMutation({
    mutationFn: () => editing ? crud.update("/clients", editing.id, form) : crud.create("/clients", form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["clients"] }); setOpen(false); },
  });
  const del = useMutation({
    mutationFn: (id: number) => crud.remove("/clients", id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clients"] }),
  });

  const openNew = () => { setEditing(null); setForm({ name: "", description: "" }); setOpen(true); };
  const openEdit = (c: any) => { setEditing(c); setForm({ name: c.name, description: c.description || "" }); setOpen(true); };

  return (
    <div>
      <PageHeader title="Clients" subtitle="Top-level tenants. Assets and history are scoped per client."
        action={<Button onClick={openNew}><span className="flex items-center gap-1.5"><Plus size={16} /> New client</span></Button>} />
      <Card>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-muted border-b border-border">
            <th className="px-5 py-3 font-medium">Name</th><th className="px-5 py-3 font-medium">Description</th><th></th>
          </tr></thead>
          <tbody>
            {data?.map((c: any) => (
              <tr key={c.id} onClick={() => nav(`/engagements?client=${c.id}`)} className="border-b border-border/50 hover:bg-panel2/40 cursor-pointer">
                <td className="px-5 py-3 font-medium"><span className="flex items-center gap-1.5"><ChevronRight size={14} className="text-muted" />{c.name}</span></td>
                <td className="px-5 py-3 text-muted">{c.description}</td>
                <td className="px-5 py-3 text-right whitespace-nowrap">
                  <button onClick={(e) => { e.stopPropagation(); openEdit(c); }} className="p-1.5 text-muted hover:text-text"><Pencil size={15} /></button>
                  <button onClick={(e) => { e.stopPropagation(); confirm(`Delete ${c.name}?`) && del.mutate(c.id); }} className="p-1.5 text-muted hover:text-red-400"><Trash2 size={15} /></button>
                </td>
              </tr>
            ))}
            {!data?.length && <tr><td colSpan={3} className="px-5 py-8 text-center text-muted">No clients yet.</td></tr>}
          </tbody>
        </table>
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title={editing ? "Edit client" : "New client"}>
        <div className="space-y-4">
          <Field label="Name"><Input value={form.name} onChange={(e: any) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="Description"><Textarea rows={3} value={form.description} onChange={(e: any) => setForm({ ...form, description: e.target.value })} /></Field>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={() => save.mutate()} disabled={!form.name || save.isPending}>Save</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
