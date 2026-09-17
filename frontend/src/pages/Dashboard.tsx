import { useQuery } from "@tanstack/react-query";
import { crud, api } from "../lib/api";
import { Card } from "../components/ui";
import { PageHeader } from "../components/Layout";
import { Building2, Target, Server, ShieldAlert, ShieldCheck, ShieldX } from "lucide-react";

function Stat({ icon: Icon, label, value }: any) {
  return (
    <Card className="p-5 flex items-center gap-4">
      <div className="w-11 h-11 rounded-lg bg-brand/15 grid place-items-center text-brand"><Icon size={20} /></div>
      <div><div className="text-2xl font-semibold">{value ?? "—"}</div>
        <div className="text-xs text-muted">{label}</div></div>
    </Card>
  );
}

export default function Dashboard() {
  const clients = useQuery({ queryKey: ["clients"], queryFn: () => crud.list("/clients") });
  const engs = useQuery({ queryKey: ["engagements"], queryFn: () => crud.list("/engagements") });
  const hosts = useQuery({ queryKey: ["hosts"], queryFn: () => crud.list("/hosts") });
  const findings = useQuery({ queryKey: ["findings"], queryFn: () => crud.list("/findings") });
  const integrity = useQuery({ queryKey: ["integrity"], queryFn: () => api.get("/integrity/verify").then((r) => r.data) });

  const iv = integrity.data;
  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Overview of your knowledge base" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Stat icon={Building2} label="Clients" value={clients.data?.length} />
        <Stat icon={Target} label="Engagements" value={engs.data?.length} />
        <Stat icon={Server} label="Hosts" value={hosts.data?.length} />
        <Stat icon={ShieldAlert} label="Findings" value={findings.data?.length} />
      </div>
      <Card className="p-5">
        <div className="flex items-center gap-3">
          {iv?.ok ? <ShieldCheck className="text-emerald-400" /> : <ShieldX className="text-red-400" />}
          <div>
            <div className="font-medium">Integrity ledger {iv ? (iv.ok ? "verified" : "BROKEN") : "…"}</div>
            <div className="text-xs text-muted">
              {iv ? `${iv.entries} chained audit entries${iv.ok ? "" : ` — chain breaks at id ${iv.broken_at_id}`}` : "checking…"}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
