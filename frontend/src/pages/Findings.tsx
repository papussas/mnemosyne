import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, X } from "lucide-react";
import { crud, api } from "../lib/api";
import { Button, Input, Textarea, Select, Field, Card, Modal, Badge } from "../components/ui";
import { PageHeader } from "../components/Layout";
import { EvidencePanel, AttachmentPanel } from "../components/panels";

const emptyForm = {
  title: "", severity: "medium", status: "draft", cvss_vector: "", cve: "",
  description: "", business_impact: "", reproduction_steps: "", remediation: "",
  references: "", raw_notes: "",
};
const toRefs = (s: string) => s.split(/[\n,]/).map((x) => x.trim()).filter(Boolean);

export default function Findings() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const [sp, setSp] = useSearchParams();
  const { data: engs } = useQuery({ queryKey: ["engagements"], queryFn: () => crud.list("/engagements") });
  const { data: enums } = useQuery({ queryKey: ["enums"], queryFn: () => api.get("/meta/enums").then((r) => r.data) });

  const engId = sp.get("engagement") || engs?.[0]?.id?.toString() || "";
  const setEng = (v: string) => { sp.set("engagement", v); sp.delete("service"); setSp(sp); };

  const [creating, setCreating] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(sp.get("detail") ? Number(sp.get("detail")) : null);
  const [hostId, setHostId] = useState("");
  const [serviceId, setServiceId] = useState(sp.get("service") || "");
  const [form, setForm] = useState<any>(emptyForm);

  const [statusFilter, setStatusFilter] = useState("");
  const [templateId, setTemplateId] = useState<string>("");
  const templates = useQuery({ queryKey: ["finding-templates"], queryFn: () => crud.list("/finding-templates") });
  const findings = useQuery({ queryKey: ["findings", engId, statusFilter], enabled: !!engId,
    queryFn: () => crud.list("/findings", { engagement_id: engId, status: statusFilter || undefined }) });
  const hosts = useQuery({ queryKey: ["hosts", engId], enabled: !!engId,
    queryFn: () => crud.list("/hosts", { engagement_id: engId }) });
  const svcs = useQuery({ queryKey: ["services", hostId], enabled: !!hostId,
    queryFn: () => crud.list("/services", { host_id: hostId }) });

  // open create pre-anchored when arriving from a service drill-down (?service=&new=1)
  useEffect(() => {
    if (sp.get("new") && sp.get("service")) {
      if (sp.get("host")) setHostId(sp.get("host")!);
      setServiceId(sp.get("service")!); setForm(emptyForm); setCreating(true);
      sp.delete("new"); setSp(sp, { replace: true });
    }
  }, [sp]);

  const create = useMutation({
    mutationFn: () => crud.create("/findings", {
      engagement_id: Number(engId), service_id: Number(serviceId),
      ...form, references: toRefs(form.references),
      template_id: templateId ? Number(templateId) : undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["findings", engId] }); setCreating(false); },
  });

  return (
    <div>
      <PageHeader title="Findings" subtitle="One object per detected instance, anchored to a service. Click a finding to see detail + evidence."
        action={<div className="flex items-center gap-2">
          <Select value={statusFilter} onChange={(e: any) => setStatusFilter(e.target.value)}>
            <option value="">All statuses</option>
            {enums?.finding_status?.map((s: string) => <option key={s} value={s}>{s}</option>)}
          </Select>
          <Select value={engId} onChange={(e: any) => setEng(e.target.value)}>
            {engs?.map((e: any) => <option key={e.id} value={e.id}>{e.name}</option>)}
          </Select>
          <Button onClick={() => { setForm(emptyForm); setHostId(""); setServiceId(""); setTemplateId(""); setCreating(true); }} disabled={!engId}>
            <span className="flex items-center gap-1.5"><Plus size={16} /> Finding</span></Button>
        </div>} />

      <Card>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-muted border-b border-border">
            <th className="px-5 py-3 font-medium">Severity</th><th className="px-5 py-3 font-medium">Title</th>
            <th className="px-5 py-3 font-medium">Status</th><th className="px-5 py-3 font-medium">CVSS</th>
            <th className="px-5 py-3 font-medium">Affected</th></tr></thead>
          <tbody>
            {findings.data?.map((f: any) => (
              <tr key={f.id} onClick={() => setDetailId(f.id)} className="border-b border-border/50 hover:bg-panel2/40 cursor-pointer">
                <td className="px-5 py-3"><Badge tone={f.severity}>{f.severity}</Badge></td>
                <td className="px-5 py-3 font-medium">{f.effective_title}</td>
                <td className="px-5 py-3"><Badge>{f.status}</Badge></td>
                <td className="px-5 py-3 text-muted font-mono text-xs">{f.cvss_vector || "—"}</td>
                <td className="px-5 py-3 text-muted font-mono">{f.affected || f.host?.ip || `svc #${f.service_id}`}</td>
              </tr>
            ))}
            {!findings.data?.length && <tr><td colSpan={5} className="px-5 py-8 text-center text-muted">No findings in this engagement.</td></tr>}
          </tbody>
        </table>
      </Card>

      {/* create */}
      <Modal open={creating} onClose={() => setCreating(false)} title="New finding" wide>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Host">
              <Select value={hostId} onChange={(e: any) => { setHostId(e.target.value); setServiceId(""); }}>
                <option value="">Select host…</option>
                {hosts.data?.map((h: any) => <option key={h.id} value={h.id}>{h.ip} {h.hostname ? `(${h.hostname})` : ""}</option>)}
              </Select>
            </Field>
            <Field label="Service (anchor)">
              <Select value={serviceId} onChange={(e: any) => setServiceId(e.target.value)}>
                <option value="">Select service…</option>
                {(svcs.data || []).map((s: any) => <option key={s.id} value={s.id}>{s.port}/{s.proto} {s.service_type}</option>)}
              </Select>
            </Field>
          </div>
          <Field label="Apply template (optional)">
            <Select value={templateId} onChange={(e: any) => {
              const tid = e.target.value; setTemplateId(tid);
              const t = templates.data?.find((x: any) => String(x.id) === tid);
              if (t) setForm({ ...form, title: t.title, severity: t.default_severity,
                description: t.description || "", business_impact: t.business_impact || "",
                remediation: t.remediation || "", references: (t.references || []).join("\n") });
            }}>
              <option value="">— none —</option>
              {templates.data?.map((t: any) => <option key={t.id} value={t.id}>{t.title}{t.category ? ` (${t.category})` : ""}</option>)}
            </Select>
          </Field>
          <FindingFields form={form} setForm={setForm} enums={enums} />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setCreating(false)}>Cancel</Button>
            <Button onClick={() => create.mutate()} disabled={!serviceId || !form.title || create.isPending}>Create</Button>
          </div>
        </div>
      </Modal>

      {detailId && <FindingDetail id={detailId} enums={enums}
        onClose={() => { setDetailId(null); if (sp.get("detail")) { sp.delete("detail"); setSp(sp, { replace: true }); } }}
        onViewAsset={(aid: number) => nav(`/assets?focus=${aid}`)}
        onChanged={() => qc.invalidateQueries({ queryKey: ["findings", engId] })} />}
    </div>
  );
}

function FindingFields({ form, setForm, enums }: any) {
  const set = (k: string, v: any) => setForm({ ...form, [k]: v });
  return (
    <div className="space-y-3">
      <Field label="Title"><Input value={form.title} onChange={(e: any) => set("title", e.target.value)} /></Field>
      <div className="grid grid-cols-3 gap-3">
        <Field label="Severity"><Select value={form.severity} onChange={(e: any) => set("severity", e.target.value)}>
          {enums?.severity?.map((s: string) => <option key={s}>{s}</option>)}</Select></Field>
        <Field label="Status"><Select value={form.status} onChange={(e: any) => set("status", e.target.value)}>
          {enums?.finding_status?.map((s: string) => <option key={s}>{s}</option>)}</Select></Field>
        <Field label="CVE"><Input value={form.cve} onChange={(e: any) => set("cve", e.target.value)} placeholder="CVE-2024-…" /></Field>
      </div>
      <Field label="CVSS vector"><Input value={form.cvss_vector} onChange={(e: any) => set("cvss_vector", e.target.value)} placeholder="CVSS:3.1/AV:N/…" /></Field>
      <Field label="Description"><Textarea rows={3} value={form.description} onChange={(e: any) => set("description", e.target.value)} /></Field>
      <Field label="Business impact"><Textarea rows={2} value={form.business_impact} onChange={(e: any) => set("business_impact", e.target.value)} /></Field>
      <Field label="Reproduction steps"><Textarea rows={3} value={form.reproduction_steps} onChange={(e: any) => set("reproduction_steps", e.target.value)} /></Field>
      <Field label="Recommendation"><Textarea rows={2} value={form.remediation} onChange={(e: any) => set("remediation", e.target.value)} /></Field>
      <Field label="References (one per line or comma-separated)"><Textarea rows={2} value={form.references} onChange={(e: any) => set("references", e.target.value)} /></Field>
    </div>
  );
}

function Section({ title, children }: any) {
  if (!children) return null;
  return <div className="mb-4"><div className="text-xs font-semibold text-muted uppercase tracking-wide mb-1">{title}</div>
    <div className="text-sm whitespace-pre-wrap">{children}</div></div>;
}

function FindingDetail({ id, enums, onClose, onChanged, onViewAsset }: any) {
  const qc = useQueryClient();
  const { data: f } = useQuery({ queryKey: ["finding", id], queryFn: () => crud.get("/findings", id) });
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<any>(emptyForm);

  const save = useMutation({
    mutationFn: () => crud.update("/findings", id, { ...form, references: toRefs(form.references) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["finding", id] }); onChanged?.(); setEditing(false); },
  });
  const beginEdit = () => {
    setForm({ title: f.title || f.effective_title || "", severity: f.severity, status: f.status,
      cvss_vector: f.cvss_vector || "", cve: f.cve || "", description: f.description || "",
      business_impact: f.business_impact || "", reproduction_steps: f.reproduction_steps || "",
      remediation: f.remediation || "", references: (f.references || []).join("\n"), raw_notes: f.raw_notes || "" });
    setEditing(true);
  };

  return (
    <Modal open onClose={onClose} wide title={
      <span className="flex items-center gap-3">{f ? <Badge tone={f.severity}>{f.severity}</Badge> : null}
        {f?.effective_title || "Finding"}</span>}>
      {!f ? <div className="text-muted text-sm">Loading…</div> : editing ? (
        <div className="space-y-4">
          <FindingFields form={form} setForm={setForm} enums={enums} />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
            <Button onClick={() => save.mutate()} disabled={save.isPending}>Save changes</Button>
          </div>
        </div>
      ) : (
        <div>
          <div className="flex items-center gap-2 mb-4 text-sm text-muted">
            <Badge>{f.status}</Badge>
            {f.cve && <Badge>{f.cve}</Badge>}
            <span className="ml-auto flex gap-2">
              <Button variant="outline" onClick={beginEdit}><span className="flex items-center gap-1.5"><Pencil size={14} /> Edit</span></Button>
            </span>
          </div>
          {(f.asset || f.host) && (
            <div className="mb-4 bg-panel2 border border-border rounded-lg px-4 py-3 flex items-center gap-3">
              <div className="flex-1">
                <div className="text-xs font-semibold text-muted uppercase tracking-wide mb-0.5">Affected asset</div>
                <div className="text-sm font-mono">{f.asset?.ip || f.host?.ip}{f.host?.hostname ? ` · ${f.host.hostname}` : ""}</div>
                <div className="text-xs text-muted">service anchor: svc #{f.service_id}</div>
              </div>
              {f.asset && <Button variant="outline" onClick={() => onViewAsset?.(f.asset.id)}>View asset</Button>}
            </div>
          )}
          {f.cvss_vector && <Section title="CVSS">{f.cvss_vector}</Section>}
          <Section title="Description">{f.effective_description}</Section>
          <Section title="Business impact">{f.effective_business_impact}</Section>
          <Section title="Reproduction steps">{f.reproduction_steps}</Section>
          <Section title="Recommendation">{f.effective_remediation}</Section>
          {f.references?.length ? <Section title="References">{f.references.join("\n")}</Section> : null}
          {f.raw_notes && <Section title="Raw notes">{f.raw_notes}</Section>}
          <div className="grid md:grid-cols-2 gap-6 border-t border-border pt-4 mt-4">
            <EvidencePanel query={{ finding_id: id }} createDefaults={{ finding_id: id, service_id: f.service_id }} />
            <AttachmentPanel targetType="finding" targetId={id} />
          </div>
        </div>
      )}
    </Modal>
  );
}
