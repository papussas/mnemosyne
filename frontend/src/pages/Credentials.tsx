import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, KeyRound, Trash2 } from "lucide-react";
import { crud, api } from "../lib/api";
import { Button, Input, Textarea, Select, Field, Card, Modal, Badge } from "../components/ui";
import { PageHeader } from "../components/Layout";

const statusColor: Record<string, string> = {
  works: "text-emerald-400", failed: "text-red-400", untested: "text-muted",
};

export default function Credentials() {
  const qc = useQueryClient();
  const [sp, setSp] = useSearchParams();
  const { data: engs } = useQuery({ queryKey: ["engagements"], queryFn: () => crud.list("/engagements") });
  const { data: enums } = useQuery({ queryKey: ["enums"], queryFn: () => api.get("/meta/enums").then((r) => r.data) });
  const engId = sp.get("engagement") || engs?.[0]?.id?.toString() || "";
  const setEng = (v: string) => { sp.set("engagement", v); setSp(sp); };

  const [open, setOpen] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [form, setForm] = useState<any>({ cred_type: "password", username: "", secret: "", realm: "", source: "", validated: false, notes: "" });

  const creds = useQuery({ queryKey: ["credentials", engId], enabled: !!engId,
    queryFn: () => crud.list("/credentials", { engagement_id: engId }) });
  const save = useMutation({
    mutationFn: () => crud.create("/credentials", { ...form, engagement_id: Number(engId) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["credentials", engId] }); setOpen(false); },
  });
  const del = useMutation({
    mutationFn: (id: number) => crud.remove("/credentials", id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["credentials", engId] }),
  });

  return (
    <div>
      <PageHeader title="Secrets" subtitle="Every secret/credential found in the engagement. Open one to see where it works."
        action={<div className="flex items-center gap-2">
          <Select value={engId} onChange={(e: any) => setEng(e.target.value)}>
            {engs?.map((e: any) => <option key={e.id} value={e.id}>{e.name}</option>)}
          </Select>
          <Button onClick={() => { setForm({ cred_type: "password", username: "", secret: "", realm: "", source: "", validated: false, notes: "" }); setOpen(true); }} disabled={!engId}>
            <span className="flex items-center gap-1.5"><Plus size={16} /> Secret</span></Button>
        </div>} />

      <Card>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-muted border-b border-border">
            <th className="px-5 py-3 font-medium">Username</th><th className="px-5 py-3 font-medium">Type</th>
            <th className="px-5 py-3 font-medium">Realm</th><th className="px-5 py-3 font-medium">Source</th>
            <th className="px-5 py-3 font-medium">Validated</th><th></th></tr></thead>
          <tbody>
            {creds.data?.map((c: any) => (
              <tr key={c.id} onClick={() => setDetailId(c.id)} className="border-b border-border/50 hover:bg-panel2/40 cursor-pointer">
                <td className="px-5 py-3 font-medium font-mono flex items-center gap-2"><KeyRound size={14} className="text-muted" />{c.username || "—"}</td>
                <td className="px-5 py-3"><Badge>{c.cred_type}</Badge></td>
                <td className="px-5 py-3 text-muted">{c.realm || "—"}</td>
                <td className="px-5 py-3 text-muted">{c.source || "—"}</td>
                <td className="px-5 py-3">{c.validated ? <Badge tone="low">validated</Badge> : <span className="text-muted text-xs">no</span>}</td>
                <td className="px-5 py-3 text-right">
                  <button onClick={(e) => { e.stopPropagation(); confirm(`Delete credential ${c.username}?`) && del.mutate(c.id); }} className="p-1.5 text-muted hover:text-red-400"><Trash2 size={15} /></button>
                </td>
              </tr>
            ))}
            {!creds.data?.length && <tr><td colSpan={6} className="px-5 py-8 text-center text-muted">No credentials in this engagement.</td></tr>}
          </tbody>
        </table>
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title="New secret">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Type"><Select value={form.cred_type} onChange={(e: any) => setForm({ ...form, cred_type: e.target.value })}>
              {enums?.cred_type?.map((t: string) => <option key={t}>{t}</option>)}</Select></Field>
            <Field label="Username"><Input value={form.username} onChange={(e: any) => setForm({ ...form, username: e.target.value })} /></Field>
          </div>
          <Field label="Secret (hash / password / key)"><Input value={form.secret} onChange={(e: any) => setForm({ ...form, secret: e.target.value })} className="font-mono" /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Realm / domain"><Input value={form.realm} onChange={(e: any) => setForm({ ...form, realm: e.target.value })} /></Field>
            <Field label="Source"><Input value={form.source} onChange={(e: any) => setForm({ ...form, source: e.target.value })} placeholder="responder, dump, spray…" /></Field>
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.validated} onChange={(e) => setForm({ ...form, validated: e.target.checked })} /> Validated</label>
          <Field label="Notes"><Textarea rows={2} value={form.notes} onChange={(e: any) => setForm({ ...form, notes: e.target.value })} /></Field>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={() => save.mutate()} disabled={save.isPending}>Create</Button>
          </div>
        </div>
      </Modal>

      {detailId && <CredDetail id={detailId} engId={engId} enums={enums} onClose={() => setDetailId(null)} />}
    </div>
  );
}

function CredDetail({ id, engId, enums, onClose }: any) {
  const qc = useQueryClient();
  const cred = useQuery({ queryKey: ["credential", id], queryFn: () => crud.get("/credentials", id) });
  const worksOn = useQuery({ queryKey: ["works-on", id], queryFn: () => crud.list(`/credentials/${id}/works-on`) });
  const hosts = useQuery({ queryKey: ["hosts", engId], queryFn: () => crud.list("/hosts", { engagement_id: engId }) });
  const [hostId, setHostId] = useState("");
  const [svcId, setSvcId] = useState("");
  const [status, setStatus] = useState("works");
  const svcs = useQuery({ queryKey: ["services", hostId], enabled: !!hostId, queryFn: () => crud.list("/services", { host_id: hostId }) });

  const addLink = useMutation({
    mutationFn: () => crud.create(`/credentials/${id}/works-on`, { service_id: Number(svcId), status }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["works-on", id] }); setSvcId(""); },
  });
  const c = cred.data;
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<any>({});
  const [revealed, setRevealed] = useState<string | null>(null);
  const doReveal = async () => { const r = await api.get(`/credentials/${id}/reveal`); setRevealed(r.data.secret ?? "(empty)"); };
  const save = useMutation({
    mutationFn: () => { const b: any = { ...form }; if (!b.secret) delete b.secret; return crud.update("/credentials", id, b); },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["credential", id] }); setEditing(false); },
  });
  const beginEdit = () => {
    setForm({ cred_type: c.cred_type, username: c.username || "", secret: "",
      realm: c.realm || "", source: c.source || "", validated: c.validated, notes: c.notes || "" });
    setEditing(true);
  };

  return (
    <Modal open onClose={onClose} wide title={
      <span className="flex items-center gap-2 font-mono"><KeyRound size={16} /> {c?.username || "credential"}
        {c && <Badge>{c.cred_type}</Badge>}</span>}>
      {!c ? <div className="text-muted text-sm">Loading…</div> : editing ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Type"><Select value={form.cred_type} onChange={(e: any) => setForm({ ...form, cred_type: e.target.value })}>
              {enums?.cred_type?.map((t: string) => <option key={t}>{t}</option>)}</Select></Field>
            <Field label="Username"><Input value={form.username} onChange={(e: any) => setForm({ ...form, username: e.target.value })} /></Field>
          </div>
          <Field label="Secret (leave blank to keep current)"><Input value={form.secret} onChange={(e: any) => setForm({ ...form, secret: e.target.value })} className="font-mono" placeholder="••••••" /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Realm"><Input value={form.realm} onChange={(e: any) => setForm({ ...form, realm: e.target.value })} /></Field>
            <Field label="Source"><Input value={form.source} onChange={(e: any) => setForm({ ...form, source: e.target.value })} /></Field>
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.validated} onChange={(e) => setForm({ ...form, validated: e.target.checked })} /> Validated</label>
          <Field label="Notes"><Textarea rows={2} value={form.notes} onChange={(e: any) => setForm({ ...form, notes: e.target.value })} /></Field>
          <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setEditing(false)}>Cancel</Button><Button onClick={() => save.mutate()} disabled={save.isPending}>Save</Button></div>
        </div>
      ) : (
        <div>
          <div className="flex justify-end mb-2"><Button variant="outline" onClick={beginEdit}>Edit</Button></div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm mb-5">
            <div><span className="text-muted">Realm: </span>{c.realm || "—"}</div>
            <div><span className="text-muted">Source: </span>{c.source || "—"}</div>
            <div><span className="text-muted">Validated: </span>{c.validated ? "yes" : "no"}</div>
            <div className="col-span-2"><span className="text-muted">Secret: </span>
              <span className="font-mono break-all">{revealed ?? c.secret_masked ?? "—"}</span>
              {revealed === null
                ? <button onClick={doReveal} className="ml-2 text-xs text-brand hover:underline">Reveal</button>
                : <button onClick={() => setRevealed(null)} className="ml-2 text-xs text-muted hover:underline">Hide</button>}
            </div>
            {c.notes && <div className="col-span-2"><span className="text-muted">Notes: </span>{c.notes}</div>}
          </div>

          <div className="border-t border-border pt-4">
            <div className="text-sm font-medium text-muted mb-2">Where it works</div>
            <div className="space-y-1.5 mb-4">
              {worksOn.data?.map((w: any) => (
                <div key={w.link_id} className="flex items-center gap-3 bg-panel2 rounded-lg px-3 py-2 text-sm">
                  <span className={`text-xs font-semibold uppercase w-16 ${statusColor[w.status] || "text-muted"}`}>{w.status}</span>
                  <span className="font-mono">{w.host_ip}{w.hostname ? ` (${w.hostname})` : ""}</span>
                  <span className="text-muted">{w.service}</span>
                  {w.note && <span className="text-xs text-muted ml-auto">{w.note}</span>}
                </div>
              ))}
              {!worksOn.data?.length && <div className="text-xs text-muted">Not tested against any service yet.</div>}
            </div>

            <div className="grid grid-cols-4 gap-2 border-t border-border pt-3">
              <Select value={hostId} onChange={(e: any) => { setHostId(e.target.value); setSvcId(""); }}>
                <option value="">Host…</option>
                {hosts.data?.map((h: any) => <option key={h.id} value={h.id}>{h.ip}</option>)}
              </Select>
              <Select value={svcId} onChange={(e: any) => setSvcId(e.target.value)}>
                <option value="">Service…</option>
                {(svcs.data || []).map((s: any) => <option key={s.id} value={s.id}>{s.port}/{s.proto} {s.service_type}</option>)}
              </Select>
              <Select value={status} onChange={(e: any) => setStatus(e.target.value)}>
                {enums?.works_status?.map((s: string) => <option key={s}>{s}</option>)}
              </Select>
              <Button variant="outline" onClick={() => addLink.mutate()} disabled={!svcId || addLink.isPending}>Add link</Button>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}
