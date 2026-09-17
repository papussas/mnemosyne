import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Library } from "lucide-react";
import { crud, api } from "../lib/api";
import { Button, Input, Textarea, Select, Field, Card, Modal, Badge } from "../components/ui";
import { PageHeader } from "../components/Layout";

const empty = { title: "", category: "", default_severity: "medium", description: "", business_impact: "", remediation: "", references: "" };
const toRefs = (s: string) => s.split(/[\n,]/).map((x) => x.trim()).filter(Boolean);

export default function Templates() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["finding-templates"], queryFn: () => crud.list("/finding-templates") });
  const { data: enums } = useQuery({ queryKey: ["enums"], queryFn: () => api.get("/meta/enums").then((r) => r.data) });
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [form, setForm] = useState<any>(empty);

  const save = useMutation({
    mutationFn: () => { const body = { ...form, references: toRefs(form.references) };
      return editing ? crud.update("/finding-templates", editing.id, body) : crud.create("/finding-templates", body); },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["finding-templates"] }); setOpen(false); },
  });
  const del = useMutation({ mutationFn: (id: number) => crud.remove("/finding-templates", id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finding-templates"] }) });

  const openNew = () => { setEditing(null); setForm(empty); setOpen(true); };
  const openEdit = (t: any) => { setEditing(t);
    setForm({ title: t.title, category: t.category || "", default_severity: t.default_severity,
      description: t.description || "", business_impact: t.business_impact || "",
      remediation: t.remediation || "", references: (t.references || []).join("\n") }); setOpen(true); };

  return (
    <div>
      <PageHeader title="Finding Templates" subtitle="Reusable finding write-ups. Apply one when creating a finding to inherit its narrative."
        action={<Button onClick={openNew}><span className="flex items-center gap-1.5"><Plus size={16} /> New template</span></Button>} />
      <Card>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-muted border-b border-border">
            <th className="px-5 py-3 font-medium">Title</th><th className="px-5 py-3 font-medium">Category</th>
            <th className="px-5 py-3 font-medium">Severity</th><th></th></tr></thead>
          <tbody>
            {data?.map((t: any) => (
              <tr key={t.id} className="border-b border-border/50 hover:bg-panel2/40">
                <td className="px-5 py-3 font-medium flex items-center gap-2"><Library size={14} className="text-muted" />{t.title}</td>
                <td className="px-5 py-3 text-muted">{t.category || "—"}</td>
                <td className="px-5 py-3"><Badge tone={t.default_severity}>{t.default_severity}</Badge></td>
                <td className="px-5 py-3 text-right whitespace-nowrap">
                  <button onClick={() => openEdit(t)} className="p-1.5 text-muted hover:text-text"><Pencil size={15} /></button>
                  <button onClick={() => confirm(`Delete template "${t.title}"?`) && del.mutate(t.id)} className="p-1.5 text-muted hover:text-red-400"><Trash2 size={15} /></button>
                </td>
              </tr>
            ))}
            {!data?.length && <tr><td colSpan={4} className="px-5 py-8 text-center text-muted">No templates yet.</td></tr>}
          </tbody>
        </table>
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title={editing ? "Edit template" : "New template"} wide>
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <Field label="Title"><Input value={form.title} onChange={(e: any) => setForm({ ...form, title: e.target.value })} /></Field>
            <Field label="Category"><Input value={form.category} onChange={(e: any) => setForm({ ...form, category: e.target.value })} placeholder="e.g. SMB, Web" /></Field>
            <Field label="Default severity"><Select value={form.default_severity} onChange={(e: any) => setForm({ ...form, default_severity: e.target.value })}>
              {enums?.severity?.map((s: string) => <option key={s}>{s}</option>)}</Select></Field>
          </div>
          <Field label="Description"><Textarea rows={3} value={form.description} onChange={(e: any) => setForm({ ...form, description: e.target.value })} /></Field>
          <Field label="Business impact"><Textarea rows={2} value={form.business_impact} onChange={(e: any) => setForm({ ...form, business_impact: e.target.value })} /></Field>
          <Field label="Recommendation"><Textarea rows={2} value={form.remediation} onChange={(e: any) => setForm({ ...form, remediation: e.target.value })} /></Field>
          <Field label="References (one per line)"><Textarea rows={2} value={form.references} onChange={(e: any) => setForm({ ...form, references: e.target.value })} /></Field>
          <div className="flex justify-end gap-2 pt-1"><Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={() => save.mutate()} disabled={!form.title || save.isPending}>Save</Button></div>
        </div>
      </Modal>
    </div>
  );
}
