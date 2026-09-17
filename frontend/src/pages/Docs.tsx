import { Download, Server, ShieldAlert, KeyRound, Boxes, Bot, FileArchive, UploadCloud } from "lucide-react";
import { Card } from "../components/ui";
import { PageHeader } from "../components/Layout";

function Step({ n, children }: any) {
  return (
    <div className="flex gap-3">
      <span className="w-6 h-6 shrink-0 grid place-items-center rounded-full bg-brand/15 text-brand text-xs font-semibold">{n}</span>
      <div className="text-sm">{children}</div>
    </div>
  );
}

export default function Docs() {
  return (
    <div>
      <PageHeader title="Documentation" subtitle="How Mnemosyne works, and the AI Agent Pack for Claude Code." />

      <Card className="p-5 mb-6">
        <div className="flex items-start gap-4">
          <div className="w-11 h-11 rounded-lg bg-brand/15 grid place-items-center text-brand shrink-0"><FileArchive size={20} /></div>
          <div className="flex-1">
            <div className="font-medium">AI Agent Pack</div>
            <p className="text-sm text-muted mt-1 mb-3">MCP server + Claude Code skills so an agent can populate Mnemosyne during an engagement (recon → services → evidence → findings → secrets). Includes <code>mnemosyne_mcp.py</code>, three skills, an <code>mcp.json</code> example, and a README.</p>
            <a href="/agent_pack.zip" download>
              <span className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium bg-brand hover:bg-brand2 text-white">
                <Download size={16} /> Download agent_pack.zip
              </span>
            </a>
          </div>
        </div>
      </Card>

      <Card className="p-5 mb-6">
        <div className="font-medium mb-3">How the data model works</div>
        <div className="grid sm:grid-cols-2 gap-3 text-sm">
          <div className="flex gap-2"><Boxes size={16} className="text-brand mt-0.5" /><div><b>Assets</b> — every machine ever discovered (by IP/FQDN), tracked across <i>all</i> engagements. From an asset you see its history, findings, and which secrets work on it.</div></div>
          <div className="flex gap-2"><Server size={16} className="text-brand mt-0.5" /><div><b>Hosts &amp; Services</b> — the <i>per-engagement</i> view. Document each host and its services (with description, notes, screenshots).</div></div>
          <div className="flex gap-2"><ShieldAlert size={16} className="text-brand mt-0.5" /><div><b>Findings</b> — one per detected instance, anchored to a service, in the Deliverables format (severity, CVSS, business impact, repro, remediation). Lifecycle: draft → confirmed → remediated → retested.</div></div>
          <div className="flex gap-2"><KeyRound size={16} className="text-brand mt-0.5" /><div><b>Secrets</b> — first-class, with a "works-on" graph (where does this hash work?). Masked in the UI; reveal on demand.</div></div>
        </div>
        <p className="text-xs text-muted mt-4">Everything is tamper-evident: findings and evidence write to a hash-chained audit ledger (see Agents &amp; Integrity). Only <b>confirmed</b> findings are exported.</p>
      </Card>

      <div className="grid md:grid-cols-2 gap-6">
        <Card className="p-5">
          <div className="font-medium mb-3">Working an engagement (human)</div>
          <div className="space-y-3">
            <Step n={1}>Create a <b>Client</b>, then an <b>Engagement</b> under it.</Step>
            <Step n={2}>Add <b>Hosts &amp; Services</b>; attach screenshots. Use the <b>Services</b> gallery to eyeball web pages fast.</Step>
            <Step n={3}>Record <b>Findings</b> anchored to a service, with evidence + screenshots. Store <b>Secrets</b> and mark where they work.</Step>
            <Step n={4}>Move findings to <b>confirmed</b> after review.</Step>
            <Step n={5}>From the engagement page: <b>Export bundle</b> (<UploadCloud size={12} className="inline" /> JSON + images + integrity) or run the <b>Confluence &amp; Jira</b> publish wizard.</Step>
          </div>
        </Card>

        <Card className="p-5">
          <div className="font-medium mb-3 flex items-center gap-2"><Bot size={16} /> Wiring Claude Code (agent)</div>
          <div className="space-y-3">
            <Step n={1}>In <b>Agents &amp; Integrity</b>, create an API token (copy it — shown once). It inherits your role.</Step>
            <Step n={2}>Download &amp; unzip the pack (button above). <code>pip install -r agent-pack/requirements.txt</code>.</Step>
            <Step n={3}>Register the MCP server with Claude Code, pointing <code>MNEME_URL</code> at <code>&lt;this-site&gt;/api</code> and <code>MNEME_TOKEN</code> at your token.</Step>
            <Step n={4}>Copy the skills into <code>.claude/skills/</code>. Then ask Claude Code to record recon, log findings, or export.</Step>
          </div>
          <p className="text-xs text-muted mt-4">Full setup steps are in the pack's <code>README.md</code>.</p>
        </Card>
      </div>
    </div>
  );
}
