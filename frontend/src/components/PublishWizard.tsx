import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Check, Loader2, AlertTriangle, ExternalLink } from "lucide-react";
import { api } from "../lib/api";
import { Button, Input, Field, Badge, Modal } from "./ui";

const ALL_STATUSES = ["draft", "open", "confirmed", "remediated", "risk_accepted", "false_positive"];
const CFG_KEY = "mneme_publish_cfg";

function loadCfg() {
  try { return JSON.parse(localStorage.getItem(CFG_KEY) || "{}"); } catch { return {}; }
}

export default function PublishWizard({ engagementId, onClose }: { engagementId: number; onClose: () => void }) {
  const saved = loadCfg();
  const [step, setStep] = useState(1);
  const [conf, setConf] = useState<any>(saved.conf || { base_url: "", space_key: "", parent_page_id: "" });
  const [jira, setJira] = useState<any>(saved.jira || { base_url: "", project_key: "", issue_type: "Task" });
  const [doConf, setDoConf] = useState(saved.doConf ?? true);
  const [doJira, setDoJira] = useState(saved.doJira ?? true);
  const [email, setEmail] = useState(saved.email || "");
  const [token, setToken] = useState("");
  const [statuses, setStatuses] = useState<string[]>(saved.statuses || ["draft", "open", "confirmed", "remediated", "risk_accepted"]);
  const [plan, setPlan] = useState<any>(null);
  const [result, setResult] = useState<any>(null);

  const body = (dry: boolean) => ({
    confluence: doConf ? { base_url: conf.base_url, space_key: conf.space_key, parent_page_id: conf.parent_page_id || null } : null,
    jira: doJira ? { base_url: jira.base_url, project_key: jira.project_key, issue_type: jira.issue_type } : null,
    auth: { email, api_token: token },
    options: { statuses, create_confluence: doConf, create_jira: doJira },
    dry_run: dry,
  });
  const persist = () => { try { localStorage.setItem(CFG_KEY, JSON.stringify({ conf, jira, doConf, doJira, email, statuses })); } catch {} };

  const preview = useMutation({
    mutationFn: () => api.post(`/engagements/${engagementId}/publish`, body(true)).then((r) => r.data),
    onSuccess: (d) => { setPlan(d); persist(); setStep(4); },
  });
  const publish = useMutation({
    mutationFn: () => api.post(`/engagements/${engagementId}/publish`, body(false)).then((r) => r.data),
    onSuccess: (d) => { setResult(d); setStep(5); },
  });

  const toggleStatus = (s: string) =>
    setStatuses((cur) => cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]);

  return (
    <Modal open onClose={onClose} wide title="Publish to Confluence & Jira">
      <Steps step={step} />

      {step === 1 && (
        <div className="space-y-4">
          <label className="flex items-center gap-2 text-sm font-medium"><input type="checkbox" checked={doConf} onChange={(e) => setDoConf(e.target.checked)} /> Publish Confluence pages</label>
          {doConf && <div className="grid grid-cols-2 gap-3 pl-6">
            <Field label="Confluence base URL"><Input value={conf.base_url} onChange={(e: any) => setConf({ ...conf, base_url: e.target.value })} placeholder="https://you.atlassian.net/wiki" /></Field>
            <Field label="Space key"><Input value={conf.space_key} onChange={(e: any) => setConf({ ...conf, space_key: e.target.value })} placeholder="PENTEST" /></Field>
            <Field label="Parent page ID (optional)"><Input value={conf.parent_page_id} onChange={(e: any) => setConf({ ...conf, parent_page_id: e.target.value })} /></Field>
          </div>}
          <label className="flex items-center gap-2 text-sm font-medium"><input type="checkbox" checked={doJira} onChange={(e) => setDoJira(e.target.checked)} /> Create Jira tickets</label>
          {doJira && <div className="grid grid-cols-3 gap-3 pl-6">
            <Field label="Jira base URL"><Input value={jira.base_url} onChange={(e: any) => setJira({ ...jira, base_url: e.target.value })} placeholder="https://you.atlassian.net" /></Field>
            <Field label="Project key"><Input value={jira.project_key} onChange={(e: any) => setJira({ ...jira, project_key: e.target.value })} placeholder="SEC" /></Field>
            <Field label="Issue type"><Input value={jira.issue_type} onChange={(e: any) => setJira({ ...jira, issue_type: e.target.value })} /></Field>
          </div>}
          <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={() => setStep(2)} disabled={!doConf && !doJira}>Next</Button></div>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-4">
          <p className="text-sm text-muted">Atlassian Cloud credentials. Create an API token at id.atlassian.com → Security → API tokens. The token is used for this publish only and is not stored.</p>
          <Field label="Account email"><Input value={email} onChange={(e: any) => setEmail(e.target.value)} /></Field>
          <Field label="API token"><Input type="password" value={token} onChange={(e: any) => setToken(e.target.value)} /></Field>
          <div className="flex justify-between"><Button variant="ghost" onClick={() => setStep(1)}>Back</Button><Button onClick={() => setStep(3)} disabled={!email || !token}>Next</Button></div>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4">
          <div className="text-sm font-medium text-muted">Which finding statuses to publish?</div>
          <div className="flex flex-wrap gap-3">
            {ALL_STATUSES.map((s) => (
              <label key={s} className="flex items-center gap-2 text-sm bg-panel2 border border-border rounded-lg px-3 py-1.5">
                <input type="checkbox" checked={statuses.includes(s)} onChange={() => toggleStatus(s)} /> {s}
              </label>
            ))}
          </div>
          <div className="flex justify-between">
            <Button variant="ghost" onClick={() => setStep(2)}>Back</Button>
            <Button onClick={() => preview.mutate()} disabled={preview.isPending || !statuses.length}>
              {preview.isPending ? <span className="flex items-center gap-1.5"><Loader2 size={15} className="animate-spin" /> Building preview…</span> : "Preview (dry run)"}
            </Button>
          </div>
          {preview.isError && <ErrBox e={preview.error} />}
        </div>
      )}

      {step === 4 && plan && (
        <div className="space-y-4">
          <div className="text-sm">Dry run: <strong>{plan.finding_count}</strong> finding(s) will be published
            {plan.space_key ? <> to Confluence space <Badge>{plan.space_key}</Badge></> : null}
            {plan.jira_project ? <> and Jira project <Badge>{plan.jira_project}</Badge></> : null}. Nothing has been sent yet.</div>
          <div className="max-h-72 overflow-auto border border-border rounded-lg">
            <table className="w-full text-sm">
              <thead className="text-left text-muted border-b border-border sticky top-0 bg-panel"><tr>
                <th className="px-3 py-2 font-medium">Finding</th><th className="px-3 py-2 font-medium">Confluence</th><th className="px-3 py-2 font-medium">Jira</th></tr></thead>
              <tbody>
                {plan.items.map((it: any) => (
                  <tr key={it.finding_id} className="border-b border-border/50">
                    <td className="px-3 py-2"><Badge tone={it.severity}>{it.severity}</Badge> {it.title}</td>
                    <td className="px-3 py-2 text-muted">{it.confluence ? `${it.confluence.action} page` : "—"}</td>
                    <td className="px-3 py-2 text-muted">{it.jira ? `${it.jira.action} · ${it.jira.priority} · due ${it.jira.duedate || "n/a"}` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-between">
            <Button variant="ghost" onClick={() => setStep(3)}>Back</Button>
            <Button onClick={() => publish.mutate()} disabled={publish.isPending}>
              {publish.isPending ? <span className="flex items-center gap-1.5"><Loader2 size={15} className="animate-spin" /> Publishing…</span> : `Publish for real`}
            </Button>
          </div>
          {publish.isError && <ErrBox e={publish.error} />}
        </div>
      )}

      {step === 5 && result && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-emerald-400"><Check size={18} /> Published {result.published} finding(s).</div>
          <div className="max-h-72 overflow-auto border border-border rounded-lg">
            <table className="w-full text-sm">
              <tbody>
                {result.results.map((r: any) => (
                  <tr key={r.finding_id} className="border-b border-border/50">
                    <td className="px-3 py-2">{r.title}</td>
                    <td className="px-3 py-2 text-muted">
                      {r.confluence?.url && <a className="text-brand hover:underline flex items-center gap-1" href={r.confluence.url} target="_blank" rel="noreferrer"><ExternalLink size={12} /> page</a>}
                    </td>
                    <td className="px-3 py-2 text-muted">
                      {r.jira?.url ? <a className="text-brand hover:underline flex items-center gap-1" href={r.jira.url} target="_blank" rel="noreferrer"><ExternalLink size={12} /> {r.jira.key}</a> : r.jira?.key}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.errors?.length > 0 && (
            <div className="text-sm text-amber-400"><AlertTriangle size={14} className="inline mr-1" /> {result.errors.length} error(s):
              <ul className="list-disc pl-5 mt-1">{result.errors.map((e: any, i: number) => <li key={i} className="text-xs">#{e.finding_id} {e.target}: {e.error}</li>)}</ul>
            </div>
          )}
          <div className="flex justify-end"><Button onClick={onClose}>Done</Button></div>
        </div>
      )}
    </Modal>
  );
}

function Steps({ step }: { step: number }) {
  const labels = ["Targets", "Credentials", "Scope", "Review", "Done"];
  return (
    <div className="flex items-center gap-2 mb-5 text-xs">
      {labels.map((l, i) => (
        <div key={l} className={`flex items-center gap-2 ${i + 1 <= step ? "text-text" : "text-muted"}`}>
          <span className={`w-5 h-5 grid place-items-center rounded-full border ${i + 1 <= step ? "bg-brand border-brand text-white" : "border-border"}`}>{i + 1}</span>
          {l}{i < labels.length - 1 && <span className="text-border mx-1">→</span>}
        </div>
      ))}
    </div>
  );
}

function ErrBox({ e }: { e: any }) {
  const msg = e?.response?.data?.detail || e?.message || "Request failed";
  return <div className="text-sm text-red-400"><AlertTriangle size={14} className="inline mr-1" /> {String(msg)}</div>;
}
