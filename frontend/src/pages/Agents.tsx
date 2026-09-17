import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, ShieldCheck, ShieldX, Copy, Check } from "lucide-react";
import { crud, api } from "../lib/api";
import { copyText } from "../lib/clipboard";
import { Button, Input, Select, Field, Card, Modal, Badge } from "../components/ui";
import { PageHeader } from "../components/Layout";

export default function Agents() {
  const qc = useQueryClient();
  const tokens = useQuery({ queryKey: ["tokens"], queryFn: () => crud.list("/tokens") });
  const audit = useQuery({ queryKey: ["audit"], queryFn: () => crud.list("/integrity/audit") });
  const integrity = useQuery({ queryKey: ["integrity"], queryFn: () => api.get("/integrity/verify").then((r) => r.data) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<any>({ name: "", expires_days: "" });
  const [issued, setIssued] = useState<string>("");
  const [copied, setCopied] = useState(false);

  const create = useMutation({
    mutationFn: () => crud.create("/tokens", { name: form.name,
      expires_days: form.expires_days ? Number(form.expires_days) : null }),
    onSuccess: (t: any) => { setIssued(t.token); qc.invalidateQueries({ queryKey: ["tokens"] }); },
  });
  const revoke = useMutation({
    mutationFn: (id: number) => crud.remove("/tokens", id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tokens"] }),
  });

  const iv = integrity.data;
  return (
    <div>
      <PageHeader title="Agents & Integrity" subtitle="API tokens for AI agents, and the tamper-evident audit ledger." />

      <Card className="p-5 mb-6 flex items-center gap-3">
        {iv?.ok ? <ShieldCheck className="text-emerald-400" /> : <ShieldX className="text-red-400" />}
        <div className="flex-1">
          <div className="font-medium">Audit ledger {iv ? (iv.ok ? "verified" : "BROKEN") : "…"}</div>
          <div className="text-xs text-muted">{iv ? `${iv.entries} hash-chained entries` : "checking…"}</div>
        </div>
        <Button variant="outline" onClick={() => integrity.refetch()}>Re-verify</Button>
      </Card>

      <div className="flex items-center justify-between mb-1">
        <h2 className="font-semibold">My API tokens</h2>
        <Button onClick={() => { setForm({ name: "", expires_days: "" }); setIssued(""); setOpen(true); }}>
          <span className="flex items-center gap-1.5"><Plus size={16} /> New token</span></Button>
      </div>
      <p className="text-xs text-muted mb-3">Tokens act as an agent under your account and inherit your role. Use the value in an agent's <code>X-API-Key</code> header.</p>
      <Card className="mb-6">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-muted border-b border-border">
            <th className="px-5 py-3 font-medium">Name</th><th className="px-5 py-3 font-medium">Prefix</th>
            <th className="px-5 py-3 font-medium">Role</th><th className="px-5 py-3 font-medium">Last used</th><th></th></tr></thead>
          <tbody>
            {tokens.data?.map((t: any) => (
              <tr key={t.id} className="border-b border-border/50">
                <td className="px-5 py-3 font-medium">{t.name} {t.revoked && <Badge>revoked</Badge>}</td>
                <td className="px-5 py-3 font-mono text-muted">{t.prefix}…</td>
                <td className="px-5 py-3"><Badge>{t.role}</Badge></td>
                <td className="px-5 py-3 text-muted">{t.last_used_at ? new Date(t.last_used_at).toLocaleString() : "never"}</td>
                <td className="px-5 py-3 text-right">{!t.revoked && <Button variant="ghost" onClick={() => revoke.mutate(t.id)}>Revoke</Button>}</td>
              </tr>
            ))}
            {!tokens.data?.length && <tr><td colSpan={5} className="px-5 py-8 text-center text-muted">No tokens issued.</td></tr>}
          </tbody>
        </table>
      </Card>

      <h2 className="font-semibold mb-3">Recent audit entries</h2>
      <Card>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-muted border-b border-border">
            <th className="px-5 py-3 font-medium">Time</th><th className="px-5 py-3 font-medium">Actor</th>
            <th className="px-5 py-3 font-medium">Action</th><th className="px-5 py-3 font-medium">Entity</th></tr></thead>
          <tbody>
            {audit.data?.slice(0, 15).map((a: any) => (
              <tr key={a.id} className="border-b border-border/50">
                <td className="px-5 py-3 text-muted">{new Date(a.ts).toLocaleTimeString()}</td>
                <td className="px-5 py-3 font-mono text-xs">{a.actor}</td>
                <td className="px-5 py-3"><Badge>{a.action}</Badge></td>
                <td className="px-5 py-3 text-muted">{a.entity_type} #{a.entity_id}</td>
              </tr>
            ))}
            {!audit.data?.length && <tr><td colSpan={4} className="px-5 py-8 text-center text-muted">Ledger is empty.</td></tr>}
          </tbody>
        </table>
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title="New agent API token">
        {issued ? (
          <div className="space-y-3">
            <p className="text-sm text-amber-400">Copy this token now — it is shown only once.</p>
            <div className="flex items-center gap-2 bg-panel2 border border-border rounded-lg px-3 py-2">
              <code className="text-xs font-mono break-all flex-1">{issued}</code>
              <button onClick={async () => { const okc = await copyText(issued); setCopied(okc); if (okc) setTimeout(() => setCopied(false), 1500); }}
                className="text-muted hover:text-text flex items-center gap-1 text-xs shrink-0">
                {copied ? <><Check size={14} /> Copied</> : <><Copy size={15} /> Copy</>}
              </button>
            </div>
            <div className="flex justify-end"><Button onClick={() => setOpen(false)}>Done</Button></div>
          </div>
        ) : (
          <div className="space-y-4">
            <Field label="Name (e.g. aria-01)"><Input value={form.name} onChange={(e: any) => setForm({ ...form, name: e.target.value })} /></Field>
            <Field label="Expires in days (blank = never)"><Input value={form.expires_days} onChange={(e: any) => setForm({ ...form, expires_days: e.target.value })} /></Field>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
              <Button onClick={() => create.mutate()} disabled={!form.name || create.isPending}>Create</Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
