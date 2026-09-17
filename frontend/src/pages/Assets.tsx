import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Boxes, ChevronRight, KeyRound, Search, Pencil } from "lucide-react";
import { crud } from "../lib/api";
import { Card, Badge, Input, Textarea, Field, Button } from "../components/ui";
import { PageHeader } from "../components/Layout";

const credStatusColor: Record<string, string> = { works: "text-emerald-400", failed: "text-red-400", untested: "text-muted" };

export default function Assets() {
  const nav = useNavigate();
  const [sp, setSp] = useSearchParams();
  const { data: engs } = useQuery({ queryKey: ["engagements"], queryFn: () => crud.list("/engagements") });
  const [sel, setSel] = useState<any>(null);
  const [eng, setEng] = useState("");
  const [q, setQ] = useState("");
  const [flags, setFlags] = useState({ has_findings: false, has_creds: false, has_services: false });

  const assets = useQuery({
    queryKey: ["assets", eng, q, flags],
    queryFn: () => crud.list("/assets", {
      engagement_id: eng || undefined, q: q || undefined,
      has_findings: flags.has_findings || undefined,
      has_creds: flags.has_creds || undefined,
      has_services: flags.has_services || undefined,
    }),
  });

  useEffect(() => {
    const focus = sp.get("focus");
    if (focus && assets.data) { const a = assets.data.find((x: any) => x.id === Number(focus)); if (a) setSel(a); }
  }, [sp, assets.data]);

  const Chk = ({ k, label }: any) => (
    <label className="flex items-center gap-1.5 text-sm text-muted whitespace-nowrap">
      <input type="checkbox" checked={(flags as any)[k]} onChange={(e) => setFlags({ ...flags, [k]: e.target.checked })} /> {label}
    </label>
  );

  return (
    <div>
      <PageHeader title="Assets" subtitle="Every machine discovered (by IP/FQDN), tracked across all engagements. Hosts & services are the per-engagement view of these." />

      <div className="flex flex-wrap items-center gap-3 mb-5">
        <div className="relative flex-1 min-w-[220px]">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <Input className="pl-9" placeholder="Search IP, FQDN, label, notes…" value={q} onChange={(e: any) => setQ(e.target.value)} />
        </div>
        <select className="bg-panel2 border border-border rounded-lg px-3 py-2 text-sm" value={eng} onChange={(e) => setEng(e.target.value)}>
          <option value="">All engagements</option>
          {engs?.map((e: any) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
        <Chk k="has_services" label="has services" />
        <Chk k="has_findings" label="has findings" />
        <Chk k="has_creds" label="has secrets" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:items-start">
        <Card className="divide-y divide-border/50 lg:max-h-[calc(100vh-13rem)] lg:overflow-y-auto">
          {assets.data?.map((a: any) => (
            <button key={a.id} onClick={() => setSel(a)}
              className={`w-full text-left px-5 py-3 flex items-center gap-3 hover:bg-panel2/40 ${sel?.id === a.id ? "bg-brand/10" : ""}`}>
              <Boxes size={16} className="text-muted" />
              <div className="flex-1 min-w-0">
                <div className="font-mono text-sm font-medium truncate">{a.ip || a.fqdn}</div>
                <div className="text-xs text-muted truncate">{a.label || (a.fqdn && a.ip ? a.fqdn : "")}</div>
              </div>
              <div className="flex gap-1.5 text-[10px] text-muted">
                <span className="bg-panel2 rounded px-1.5 py-0.5">{a.counts?.services ?? 0} svc</span>
                <span className="bg-panel2 rounded px-1.5 py-0.5">{a.counts?.findings ?? 0} find</span>
                <span className="bg-panel2 rounded px-1.5 py-0.5">{a.counts?.credentials ?? 0} sec</span>
              </div>
              <ChevronRight size={15} className="text-muted" />
            </button>
          ))}
          {!assets.data?.length && <div className="px-5 py-8 text-center text-muted text-sm">No assets match.</div>}
        </Card>

        <div className="lg:sticky lg:top-8 lg:max-h-[calc(100vh-13rem)] lg:overflow-y-auto">{sel ? <AssetDetail asset={sel} onOpenFinding={(f: any) => nav(`/findings?engagement=${f.engagement_id}&detail=${f.id}`)} /> :
          <Card className="p-5 text-center text-muted text-sm py-8">Select an asset to see its findings, secrets and history.</Card>}</div>
      </div>
    </div>
  );
}

function AssetDetail({ asset, onOpenFinding }: any) {
  const qc = useQueryClient();
  const detail = useQuery({ queryKey: ["asset", asset.id], queryFn: () => crud.get("/assets", asset.id), initialData: asset });
  const findings = useQuery({ queryKey: ["asset-findings", asset.id], queryFn: () => crud.list(`/assets/${asset.id}/findings`) });
  const credentials = useQuery({ queryKey: ["asset-creds", asset.id], queryFn: () => crud.list(`/assets/${asset.id}/credentials`) });
  const history = useQuery({ queryKey: ["asset-history", asset.id], queryFn: () => crud.get("/assets", `${asset.id}/history`) });
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<any>({ label: "", notes: "" });
  const save = useMutation({
    mutationFn: () => crud.update("/assets", asset.id, form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["asset", asset.id] }); qc.invalidateQueries({ queryKey: ["assets"] }); setEditing(false); },
  });
  const a = detail.data || asset;

  return (
    <div className="space-y-4">
      <Card className="p-5">
        {editing ? (
          <div className="space-y-3">
            <Field label="Label"><Input value={form.label} onChange={(e: any) => setForm({ ...form, label: e.target.value })} /></Field>
            <Field label="Notes"><Textarea rows={2} value={form.notes} onChange={(e: any) => setForm({ ...form, notes: e.target.value })} /></Field>
            <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setEditing(false)}>Cancel</Button><Button onClick={() => save.mutate()} disabled={save.isPending}>Save</Button></div>
          </div>
        ) : (
          <div className="flex items-start justify-between">
            <div><div className="font-mono text-lg font-medium">{a.ip || a.fqdn}</div>
              <div className="text-sm text-muted">{a.label || (a.fqdn && a.ip ? a.fqdn : "")}</div>
              {a.notes && <div className="text-sm mt-2">{a.notes}</div>}</div>
            <Button variant="outline" onClick={() => { setForm({ label: a.label || "", notes: a.notes || "" }); setEditing(true); }}>
              <span className="flex items-center gap-1.5"><Pencil size={14} /> Edit</span></Button>
          </div>
        )}
      </Card>

      <Card className="p-5">
        <div className="text-sm font-medium text-muted mb-3">Associated findings (all engagements)</div>
        <div className="space-y-1.5">
          {findings.data?.map((f: any) => (
            <button key={f.id} onClick={() => onOpenFinding(f)} className="w-full flex items-center gap-2 bg-panel2 rounded-lg px-3 py-2 text-sm text-left hover:bg-panel2/70">
              <Badge tone={f.severity}>{f.severity}</Badge><span className="flex-1">{f.title}</span>
              <span className="text-xs text-muted">{f.engagement}</span><Badge>{f.status}</Badge>
            </button>
          ))}
          {!findings.data?.length && <div className="text-xs text-muted">No findings recorded against this asset yet.</div>}
        </div>
      </Card>

      <Card className="p-5">
        <div className="text-sm font-medium text-muted mb-3">Secrets that work here</div>
        <div className="space-y-1.5">
          {credentials.data?.map((row: any) => (
            <div key={row.credential.id} className="bg-panel2 rounded-lg px-3 py-2 text-sm">
              <div className="flex items-center gap-2"><KeyRound size={14} className="text-muted" />
                <span className="font-mono font-medium">{row.credential.username || "—"}</span>
                <Badge>{row.credential.cred_type}</Badge>{row.credential.realm && <span className="text-xs text-muted">{row.credential.realm}</span>}</div>
              <div className="flex flex-wrap gap-1.5 mt-1.5 pl-6">
                {row.works_on.map((w: any, i: number) => (
                  <span key={i} className="text-xs font-mono bg-panel rounded px-2 py-0.5"><span className={credStatusColor[w.status] || "text-muted"}>{w.status}</span> · {w.service}</span>
                ))}
              </div>
            </div>
          ))}
          {!credentials.data?.length && <div className="text-xs text-muted">No secrets tested against this asset yet.</div>}
        </div>
      </Card>

      <Card className="p-5">
        <div className="text-sm font-medium text-muted mb-3">Sightings history</div>
        <div className="space-y-3">
          {(history.data as any)?.sightings?.map((s: any) => (
            <div key={s.host_id} className="border border-border rounded-lg p-3">
              <div className="flex justify-between text-sm mb-1"><span className="font-medium">Engagement #{s.engagement_id}</span>
                <span className="text-xs text-muted">{new Date(s.seen_at).toLocaleDateString()}</span></div>
              <div className="flex flex-wrap gap-1.5">
                {s.services?.map((sv: any, i: number) => (<span key={i} className="text-xs font-mono bg-panel2 rounded px-2 py-0.5">{sv.port}/{sv.proto} {sv.service_type}</span>))}
                {!s.services?.length && <span className="text-xs text-muted">no services</span>}
              </div>
            </div>
          ))}
          {!(history.data as any)?.sightings?.length && <div className="text-xs text-muted">No sightings.</div>}
        </div>
      </Card>
    </div>
  );
}
