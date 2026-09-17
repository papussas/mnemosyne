import { useState, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Server, ChevronRight, Pencil, Upload } from "lucide-react";
import { crud, api } from "../lib/api";
import { Button, Input, Textarea, Select, Field, Card, Modal, Badge } from "../components/ui";
import { PageHeader } from "../components/Layout";
import { EvidencePanel, AttachmentPanel } from "../components/panels";

export default function Hosts() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const [sp, setSp] = useSearchParams();
  const { data: engs } = useQuery({ queryKey: ["engagements"], queryFn: () => crud.list("/engagements") });
  const { data: enums } = useQuery({ queryKey: ["enums"], queryFn: () => api.get("/meta/enums").then((r) => r.data) });
  const engId = sp.get("engagement") || engs?.[0]?.id?.toString() || "";
  const setEng = (v: string) => { sp.set("engagement", v); setSp(sp); setSel(null); };

  const [sel, setSel] = useState<any>(null);       // selected host
  const [svcSel, setSvcSel] = useState<any>(null);  // selected service (drawer)
  const [hOpen, setHOpen] = useState(false);
  const [hForm, setHForm] = useState<any>({ ip: "", hostname: "", os: "", in_scope: true, notes: "" });
  const [sForm, setSForm] = useState<any>({ port: "", service_type: "http", product: "", version: "", description: "" });

  const hosts = useQuery({ queryKey: ["hosts", engId], enabled: !!engId,
    queryFn: () => crud.list("/hosts", { engagement_id: engId }) });
  const services = useQuery({ queryKey: ["services", sel?.id], enabled: !!sel,
    queryFn: () => crud.list("/services", { host_id: sel.id }) });

  const addHost = useMutation({
    mutationFn: () => crud.create("/hosts", { ...hForm, engagement_id: Number(engId) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hosts", engId] }); setHOpen(false);
      setHForm({ ip: "", hostname: "", os: "", in_scope: true, notes: "" }); },
  });
  const addSvc = useMutation({
    mutationFn: () => crud.create("/services", { ...sForm, port: Number(sForm.port), host_id: sel.id }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["services", sel.id] });
      setSForm({ port: "", service_type: "http", product: "", version: "", description: "" }); },
  });
  const [heOpen, setHeOpen] = useState(false);
  const [heForm, setHeForm] = useState<any>({});
  const editHost = useMutation({
    mutationFn: () => crud.update("/hosts", sel.id, heForm),
    onSuccess: (u: any) => { qc.invalidateQueries({ queryKey: ["hosts", engId] }); setSel(u); setHeOpen(false); },
  });
  const scanRef = useRef<HTMLInputElement>(null);
  const [scanMsg, setScanMsg] = useState("");
  const importScan = useMutation({
    mutationFn: (file: File) => { const fd = new FormData(); fd.append("file", file);
      return api.post(`/engagements/${engId}/import`, fd, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data); },
    onSuccess: (d: any) => { qc.invalidateQueries({ queryKey: ["hosts", engId] });
      setScanMsg(`Imported: +${d.hosts_created} hosts, +${d.services_created} services (${d.hosts_existing} already present)`);
      setTimeout(() => setScanMsg(""), 8000); },
    onError: (e: any) => setScanMsg(e?.response?.data?.detail || "import failed"),
  });

  return (
    <div>
      <PageHeader title="Hosts & Services" subtitle="Document infrastructure. Click a host, then a service to see its evidence & findings."
        action={<div className="flex items-center gap-2">
          <Select value={engId} onChange={(e: any) => setEng(e.target.value)}>
            {engs?.map((e: any) => <option key={e.id} value={e.id}>{e.name}</option>)}
          </Select>
          <input ref={scanRef} type="file" accept=".xml,text/xml" className="hidden"
            onChange={(e) => e.target.files?.[0] && importScan.mutate(e.target.files[0])} />
          <Button variant="outline" onClick={() => scanRef.current?.click()} disabled={!engId || importScan.isPending}>
            <span className="flex items-center gap-1.5"><Upload size={16} /> {importScan.isPending ? "Importing…" : "Import scan"}</span></Button>
          <Button onClick={() => setHOpen(true)} disabled={!engId}>
            <span className="flex items-center gap-1.5"><Plus size={16} /> Host</span></Button>
        </div>} />
      {scanMsg && <div className="mb-3 text-sm text-brand">{scanMsg}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:items-start">
        <Card className="divide-y divide-border/50 lg:max-h-[calc(100vh-13rem)] lg:overflow-y-auto">
          {hosts.data?.map((h: any) => (
            <button key={h.id} onClick={() => { setSel(h); setSvcSel(null); }}
              className={`w-full text-left px-5 py-3 flex items-center gap-3 hover:bg-panel2/40 ${sel?.id === h.id ? "bg-brand/10" : ""}`}>
              <Server size={16} className="text-muted" />
              <div className="flex-1"><div className="font-medium font-mono text-sm">{h.ip}</div>
                <div className="text-xs text-muted">{h.hostname || "—"} {h.os ? `· ${h.os}` : ""}</div></div>
              {!h.in_scope && <Badge>out of scope</Badge>}
            </button>
          ))}
          {!hosts.data?.length && <div className="px-5 py-8 text-center text-muted text-sm">No hosts in this engagement.</div>}
        </Card>

        <Card className="p-5 lg:sticky lg:top-8 lg:max-h-[calc(100vh-13rem)] lg:overflow-y-auto">
          {!sel ? <div className="text-center text-muted text-sm py-8">Select a host to see its services.</div> : (
            <div>
              <div className="mb-4 flex items-start justify-between">
                <div><div className="font-mono font-medium">{sel.ip}</div>
                  <div className="text-xs text-muted">{sel.hostname} {sel.os ? `· ${sel.os}` : ""}</div>
                  {sel.notes && <div className="text-xs text-muted mt-1">{sel.notes}</div>}</div>
                <Button variant="ghost" onClick={() => { setHeForm({ ip: sel.ip, hostname: sel.hostname || "", os: sel.os || "", in_scope: sel.in_scope, notes: sel.notes || "" }); setHeOpen(true); }}>
                  <span className="flex items-center gap-1"><Pencil size={14} /> Edit</span></Button>
              </div>
              <div className="space-y-2 mb-4">
                {services.data?.map((s: any) => (
                  <button key={s.id} onClick={() => setSvcSel(s)}
                    className="w-full flex items-center gap-3 bg-panel2 rounded-lg px-3 py-2 text-sm hover:bg-panel2/70 text-left">
                    <span className="font-mono text-brand">{s.port}/{s.proto}</span>
                    <Badge>{s.service_type}</Badge>
                    <span className="text-muted flex-1">{s.product} {s.version}</span>
                    <ChevronRight size={15} className="text-muted" />
                  </button>
                ))}
                {!services.data?.length && <div className="text-xs text-muted">No services recorded yet.</div>}
              </div>
              <div className="border-t border-border pt-4 grid grid-cols-2 gap-2">
                <Input placeholder="port" value={sForm.port} onChange={(e: any) => setSForm({ ...sForm, port: e.target.value })} />
                <Select value={sForm.service_type} onChange={(e: any) => setSForm({ ...sForm, service_type: e.target.value })}>
                  {enums?.service_type?.map((t: string) => <option key={t}>{t}</option>)}
                </Select>
                <Input placeholder="product" value={sForm.product} onChange={(e: any) => setSForm({ ...sForm, product: e.target.value })} />
                <Input placeholder="version" value={sForm.version} onChange={(e: any) => setSForm({ ...sForm, version: e.target.value })} />
                <Input className="col-span-2" placeholder="description (optional)" value={sForm.description} onChange={(e: any) => setSForm({ ...sForm, description: e.target.value })} />
                <Button className="col-span-2" onClick={() => addSvc.mutate()} disabled={!sForm.port || addSvc.isPending}>Add service</Button>
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* service drawer */}
      {svcSel && <ServiceDrawer svc={svcSel} host={sel} engId={engId} enums={enums} onClose={() => setSvcSel(null)}
        onSaved={(u: any) => setSvcSel(u)}
        onNewFinding={() => nav(`/findings?engagement=${engId}&host=${sel.id}&service=${svcSel.id}&new=1`)} />}

      <Modal open={hOpen} onClose={() => setHOpen(false)} title="New host">
        <div className="space-y-4">
          <Field label="IP address"><Input value={hForm.ip} onChange={(e: any) => setHForm({ ...hForm, ip: e.target.value })} placeholder="10.0.0.28" /></Field>
          <Field label="Hostname"><Input value={hForm.hostname} onChange={(e: any) => setHForm({ ...hForm, hostname: e.target.value })} /></Field>
          <Field label="OS"><Input value={hForm.os} onChange={(e: any) => setHForm({ ...hForm, os: e.target.value })} /></Field>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={hForm.in_scope} onChange={(e) => setHForm({ ...hForm, in_scope: e.target.checked })} /> In scope</label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setHOpen(false)}>Cancel</Button>
            <Button onClick={() => addHost.mutate()} disabled={!hForm.ip || addHost.isPending}>Create</Button>
          </div>
        </div>
      </Modal>

      <Modal open={heOpen} onClose={() => setHeOpen(false)} title="Edit host">
        <div className="space-y-4">
          <Field label="IP address"><Input value={heForm.ip} onChange={(e: any) => setHeForm({ ...heForm, ip: e.target.value })} /></Field>
          <Field label="Hostname"><Input value={heForm.hostname} onChange={(e: any) => setHeForm({ ...heForm, hostname: e.target.value })} /></Field>
          <Field label="OS"><Input value={heForm.os} onChange={(e: any) => setHeForm({ ...heForm, os: e.target.value })} /></Field>
          <Field label="Notes"><Textarea rows={2} value={heForm.notes} onChange={(e: any) => setHeForm({ ...heForm, notes: e.target.value })} /></Field>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={heForm.in_scope} onChange={(e) => setHeForm({ ...heForm, in_scope: e.target.checked })} /> In scope</label>
          <div className="flex justify-end gap-2 pt-2"><Button variant="ghost" onClick={() => setHeOpen(false)}>Cancel</Button>
            <Button onClick={() => editHost.mutate()} disabled={!heForm.ip || editHost.isPending}>Save</Button></div>
        </div>
      </Modal>
    </div>
  );
}

function ServiceDrawer({ svc, host, engId, enums, onClose, onSaved, onNewFinding }: any) {
  const qc = useQueryClient();
  const findings = useQuery({ queryKey: ["findings", "svc", svc.id],
    queryFn: () => crud.list("/findings", { engagement_id: engId, service_id: svc.id }) });
  const [form, setForm] = useState<any>({
    service_type: svc.service_type || "other", product: svc.product || "", version: svc.version || "",
    description: svc.description || "", notes: svc.notes || "", banner: svc.banner || "",
  });
  const save = useMutation({
    mutationFn: () => crud.update("/services", svc.id, form),
    onSuccess: (u: any) => { qc.invalidateQueries({ queryKey: ["services", host.id] }); onSaved?.(u); },
  });
  const set = (k: string, v: any) => setForm({ ...form, [k]: v });

  return (
    <Modal open onClose={onClose} wide title={
      <span className="flex items-center gap-2 font-mono">{host?.ip} : {svc.port}/{svc.proto}
        <Badge>{form.service_type}</Badge></span>}>

      {/* editable service details */}
      <div className="mb-6 space-y-3">
        <div className="grid grid-cols-3 gap-3">
          <Field label="Service type"><Select value={form.service_type} onChange={(e: any) => set("service_type", e.target.value)}>
            {enums?.service_type?.map((t: string) => <option key={t}>{t}</option>)}</Select></Field>
          <Field label="Product"><Input value={form.product} onChange={(e: any) => set("product", e.target.value)} /></Field>
          <Field label="Version"><Input value={form.version} onChange={(e: any) => set("version", e.target.value)} /></Field>
        </div>
        <Field label="Description"><Textarea rows={2} value={form.description} onChange={(e: any) => set("description", e.target.value)} placeholder="What this service is / how it was identified" /></Field>
        <Field label="Notes"><Textarea rows={2} value={form.notes} onChange={(e: any) => set("notes", e.target.value)} placeholder="Working notes" /></Field>
        <Field label="Banner"><Textarea rows={2} value={form.banner} onChange={(e: any) => set("banner", e.target.value)} className="font-mono" /></Field>
        <div className="flex justify-end"><Button onClick={() => save.mutate()} disabled={save.isPending}>{save.isPending ? "Saving…" : "Save service"}</Button></div>
      </div>

      <div className="mb-6 border-t border-border pt-4">
        <div className="flex items-center justify-between mb-2">
          <div className="text-sm font-medium text-muted">Findings on this service</div>
          <Button variant="outline" onClick={onNewFinding}><span className="flex items-center gap-1.5"><Plus size={14} /> New finding</span></Button>
        </div>
        <div className="space-y-1.5">
          {findings.data?.map((f: any) => (
            <div key={f.id} className="flex items-center gap-2 bg-panel2 rounded-lg px-3 py-2 text-sm">
              <Badge tone={f.severity}>{f.severity}</Badge>
              <span className="flex-1">{f.effective_title}</span>
              <Badge>{f.status}</Badge>
            </div>
          ))}
          {!findings.data?.length && <div className="text-xs text-muted">No findings on this service yet.</div>}
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6 border-t border-border pt-4">
        <EvidencePanel query={{ service_id: svc.id }} createDefaults={{ service_id: svc.id }} />
        <AttachmentPanel targetType="service" targetId={svc.id} />
      </div>
    </Modal>
  );
}
