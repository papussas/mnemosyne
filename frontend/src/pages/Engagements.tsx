import { useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, ChevronRight, X, Download } from "lucide-react";
import { crud, apiBase } from "../lib/api";
import { Button, Input, Textarea, Select, Field, Card, Modal, Badge } from "../components/ui";
import { PageHeader } from "../components/Layout";

export default function Engagements() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const [sp, setSp] = useSearchParams();
  const clientFilter = sp.get("client");
  const { data: all } = useQuery({ queryKey: ["engagements"], queryFn: () => crud.list("/engagements") });
  const { data: clients } = useQuery({ queryKey: ["clients"], queryFn: () => crud.list("/clients") });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<any>({ client_id: "", name: "", description: "", status: "active" });

  const data = clientFilter ? all?.filter((e: any) => e.client_id === Number(clientFilter)) : all;
  const clientName = (id: number) => clients?.find((c: any) => c.id === id)?.name || `#${id}`;

  const save = useMutation({
    mutationFn: () => crud.create("/engagements", { ...form, client_id: Number(form.client_id) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["engagements"] }); setOpen(false); },
  });
  const del = useMutation({
    mutationFn: (id: number) => crud.remove("/engagements", id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["engagements"] }),
  });

  return (
    <div>
      <PageHeader title="Engagements" subtitle="Each engagement owns its hosts. Click one to open its hosts & services."
        action={<Button onClick={() => { setForm({ client_id: clientFilter || clients?.[0]?.id || "", name: "", description: "", status: "active" }); setOpen(true); }}>
          <span className="flex items-center gap-1.5"><Plus size={16} /> New engagement</span></Button>} />

      {clientFilter && (
        <div className="mb-4 flex items-center gap-2 text-sm">
          <Badge>Client: {clientName(Number(clientFilter))}</Badge>
          <button onClick={() => { sp.delete("client"); setSp(sp); }} className="text-muted hover:text-text flex items-center gap-1"><X size={13} /> clear filter</button>
        </div>
      )}

      <Card>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-muted border-b border-border">
            <th className="px-5 py-3 font-medium">Name</th><th className="px-5 py-3 font-medium">Client</th>
            <th className="px-5 py-3 font-medium">Status</th><th></th></tr></thead>
          <tbody>
            {data?.map((e: any) => (
              <tr key={e.id} onClick={() => nav(`/engagements/${e.id}`)} className="border-b border-border/50 hover:bg-panel2/40 cursor-pointer">
                <td className="px-5 py-3 font-medium"><span className="flex items-center gap-1.5"><ChevronRight size={14} className="text-muted" />{e.name}</span></td>
                <td className="px-5 py-3 text-muted">{clientName(e.client_id)}</td>
                <td className="px-5 py-3"><Badge>{e.status}</Badge></td>
                <td className="px-5 py-3 text-right whitespace-nowrap">
                  <a href={`${apiBase}/engagements/${e.id}/export`} onClick={(ev) => ev.stopPropagation()}
                     title="Export bundle (JSON + images + integrity)" className="inline-block p-1.5 text-muted hover:text-brand align-middle"><Download size={15} /></a>
                  <button onClick={(ev) => { ev.stopPropagation(); confirm(`Delete ${e.name}?`) && del.mutate(e.id); }} className="p-1.5 text-muted hover:text-red-400 align-middle"><Trash2 size={15} /></button>
                </td>
              </tr>
            ))}
            {!data?.length && <tr><td colSpan={4} className="px-5 py-8 text-center text-muted">No engagements{clientFilter ? " for this client" : ""} yet.</td></tr>}
          </tbody>
        </table>
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title="New engagement">
        <div className="space-y-4">
          <Field label="Client">
            <Select value={form.client_id} onChange={(e: any) => setForm({ ...form, client_id: e.target.value })}>
              <option value="">Select a client…</option>
              {clients?.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
          </Field>
          <Field label="Name"><Input value={form.name} onChange={(e: any) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="Description"><Textarea rows={2} value={form.description} onChange={(e: any) => setForm({ ...form, description: e.target.value })} /></Field>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={() => save.mutate()} disabled={!form.name || !form.client_id || save.isPending}>Create</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
