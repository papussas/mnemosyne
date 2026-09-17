import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, UploadCloud, Server, Images, ShieldAlert, KeyRound, ArrowLeft, Pencil } from "lucide-react";
import { crud, api, apiBase } from "../lib/api";
import { Button, Card, Badge, Modal, Input, Textarea, Select, Field } from "../components/ui";
import PublishWizard from "../components/PublishWizard";

function Stat({ icon: Icon, label, value, onClick }: any) {
  return (
    <button onClick={onClick} className="text-left bg-panel border border-border rounded-xl p-4 flex items-center gap-3 hover:border-brand transition-colors">
      <div className="w-10 h-10 rounded-lg bg-brand/15 grid place-items-center text-brand"><Icon size={18} /></div>
      <div><div className="text-xl font-semibold">{value ?? "—"}</div><div className="text-xs text-muted">{label}</div></div>
    </button>
  );
}

export default function EngagementDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const eid = Number(id);
  const qc = useQueryClient();
  const [wizard, setWizard] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [form, setForm] = useState<any>({ name: "", description: "", status: "active" });

  const eng = useQuery({ queryKey: ["engagement", eid], queryFn: () => crud.get("/engagements", eid) });
  const saveEng = useMutation({
    mutationFn: () => crud.update("/engagements", eid, form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["engagement", eid] }); qc.invalidateQueries({ queryKey: ["engagements"] }); setEditOpen(false); },
  });
  const clients = useQuery({ queryKey: ["clients"], queryFn: () => crud.list("/clients") });
  const hosts = useQuery({ queryKey: ["hosts", String(eid)], queryFn: () => crud.list("/hosts", { engagement_id: eid }) });
  const findings = useQuery({ queryKey: ["findings", String(eid)], queryFn: () => crud.list("/findings", { engagement_id: eid }) });
  const creds = useQuery({ queryKey: ["credentials", String(eid)], queryFn: () => crud.list("/credentials", { engagement_id: eid }) });
  const services = useQuery({ queryKey: ["gallery", String(eid)], queryFn: () => api.get("/gallery/services", { params: { engagement_id: eid } }).then((r) => r.data) });
  const activity = useQuery({ queryKey: ["activity", eid], queryFn: () => api.get(`/engagements/${eid}/activity`, { params: { limit: 25 } }).then((r) => r.data), refetchInterval: 30000 });
  const cov = useQuery({ queryKey: ["coverage", eid], queryFn: () => api.get(`/engagements/${eid}/coverage`).then((r) => r.data) });

  const e = eng.data;
  const clientName = clients.data?.find((c: any) => c.id === e?.client_id)?.name;

  return (
    <div>
      <button onClick={() => nav("/engagements")} className="text-sm text-muted hover:text-text flex items-center gap-1 mb-4"><ArrowLeft size={14} /> Engagements</button>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold">{e?.name || "Engagement"}</h1>
          <div className="text-sm text-muted mt-1 flex items-center gap-2">
            {clientName && <span>{clientName}</span>}{e && <Badge>{e.status}</Badge>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => { setForm({ name: e?.name || "", description: e?.description || "", status: e?.status || "active" }); setEditOpen(true); }}>
            <span className="flex items-center gap-1.5"><Pencil size={15} /> Edit</span></Button>
          <a href={`${apiBase}/engagements/${eid}/export`} className="inline-flex">
            <Button variant="outline"><span className="flex items-center gap-1.5"><Download size={16} /> Export bundle</span></Button>
          </a>
          <Button onClick={() => setWizard(true)}><span className="flex items-center gap-1.5"><UploadCloud size={16} /> Publish to Confluence & Jira</span></Button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <Stat icon={Server} label="Hosts" value={hosts.data?.length} onClick={() => nav(`/hosts?engagement=${eid}`)} />
        <Stat icon={Images} label="Services" value={services.data?.length} onClick={() => nav(`/services?engagement=${eid}`)} />
        <Stat icon={ShieldAlert} label="Findings" value={findings.data?.length} onClick={() => nav(`/findings?engagement=${eid}`)} />
        <Stat icon={KeyRound} label="Credentials" value={creds.data?.length} onClick={() => nav(`/credentials?engagement=${eid}`)} />
      </div>

      {cov.data && (
      <Card className="p-5 mb-6">
        <div className="font-medium mb-3">Coverage</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div><div className="text-muted text-xs">Hosts with services</div><div className="text-lg font-semibold">{cov.data.hosts.with_services}/{cov.data.hosts.total}</div></div>
          <div><div className="text-muted text-xs">Services with findings</div><div className="text-lg font-semibold">{cov.data.services.with_findings}/{cov.data.services.total}</div></div>
          <div><div className="text-muted text-xs">In-scope hosts</div><div className="text-lg font-semibold">{cov.data.hosts.in_scope}</div></div>
          <div><div className="text-muted text-xs">Secrets validated</div><div className="text-lg font-semibold">{cov.data.secrets.validated}/{cov.data.secrets.total}</div></div>
        </div>
        {Object.keys(cov.data.findings.by_severity).length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4">
            {Object.entries(cov.data.findings.by_severity).map(([sev, n]: any) => <Badge key={sev} tone={sev}>{sev}: {n}</Badge>)}
          </div>)}
        {Object.keys(cov.data.findings.by_status).length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {Object.entries(cov.data.findings.by_status).map(([st, n]: any) => <Badge key={st}>{st}: {n}</Badge>)}
          </div>)}
      </Card>
      )}

      <Card className="p-5">
        <div className="text-sm font-medium mb-3">Deliverables</div>
        <div className="grid md:grid-cols-2 gap-4 text-sm">
          <div className="bg-panel2 rounded-lg p-4">
            <div className="font-medium mb-1 flex items-center gap-2"><Download size={15} /> Export bundle</div>
            <p className="text-muted text-xs mb-3">JSON + evidence + all screenshots + integrity manifest. Secrets are obfuscated. Feed it to Rovo or archive it as the verifiable record.</p>
            <a href={`${apiBase}/engagements/${eid}/export`}><Button variant="outline">Download .zip</Button></a>
          </div>
          <div className="bg-panel2 rounded-lg p-4">
            <div className="font-medium mb-1 flex items-center gap-2"><UploadCloud size={15} /> Publish to Confluence & Jira</div>
            <p className="text-muted text-xs mb-3">Guided wizard: one page per finding, one Jira ticket per finding (severity→SLA). Dry-run preview before anything is sent.</p>
            <Button onClick={() => setWizard(true)}>Open wizard</Button>
          </div>
        </div>
      </Card>

      <Card className="p-5 mt-6">
        <div className="flex items-center justify-between mb-3">
          <div className="font-medium">Recent activity</div>
          <button onClick={() => activity.refetch()} className="text-xs text-muted hover:text-text">refresh</button>
        </div>
        <div className="space-y-1">
          {activity.data?.events?.map((e: any, i: number) => (
            <div key={i} className="flex items-center gap-2 text-sm py-1 border-b border-border/40 last:border-0">
              <span className="text-[11px] text-muted w-32 shrink-0">{new Date(e.ts).toLocaleString()}</span>
              <Badge>{e.kind}</Badge>
              <span className="flex-1 truncate">{e.summary}</span>
              <span className="text-[11px] text-muted shrink-0">{e.actor || "—"}</span>
            </div>
          ))}
          {!activity.data?.events?.length && <div className="text-xs text-muted">No activity yet.</div>}
        </div>
      </Card>

      {wizard && <PublishWizard engagementId={eid} onClose={() => setWizard(false)} />}

      <Modal open={editOpen} onClose={() => setEditOpen(false)} title="Edit engagement">
        <div className="space-y-4">
          <Field label="Name"><Input value={form.name} onChange={(ev: any) => setForm({ ...form, name: ev.target.value })} /></Field>
          <Field label="Status"><Select value={form.status} onChange={(ev: any) => setForm({ ...form, status: ev.target.value })}>
            <option value="active">active</option><option value="on-hold">on-hold</option><option value="completed">completed</option><option value="cancelled">cancelled</option>
          </Select></Field>
          <Field label="Description"><Textarea rows={3} value={form.description} onChange={(ev: any) => setForm({ ...form, description: ev.target.value })} /></Field>
          <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setEditOpen(false)}>Cancel</Button><Button onClick={() => saveEng.mutate()} disabled={!form.name || saveEng.isPending}>Save</Button></div>
        </div>
      </Modal>
    </div>
  );
}
