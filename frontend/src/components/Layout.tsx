import { NavLink } from "react-router-dom";
import { ReactNode, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Building2, Target, Server, ShieldAlert, Bot, LayoutDashboard, LogOut,
  Brain, Boxes, ShieldCheck, Images, KeyRound, ChevronDown, ChevronRight, Lock, BookOpen, Library } from "lucide-react";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { Button, Input, Field, Modal } from "./ui";

type Item = { to: string; label: string; icon: any; end?: boolean };
const GENERAL: Item[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/clients", label: "Clients", icon: Building2 },
  { to: "/engagements", label: "Engagements", icon: Target },
  { to: "/assets", label: "Assets (all discovered)", icon: Boxes },
  { to: "/finding-templates", label: "Finding Templates", icon: Library },
];
const PER_ENGAGEMENT: Item[] = [
  { to: "/hosts", label: "Hosts & Services", icon: Server },
  { to: "/services", label: "Services", icon: Images },
  { to: "/findings", label: "Findings", icon: ShieldAlert },
  { to: "/credentials", label: "Secrets", icon: KeyRound },
];
const SYSTEM: Item[] = [
  { to: "/agents", label: "Agents & Integrity", icon: Bot },
  { to: "/docs", label: "Docs & Agent Pack", icon: BookOpen },
];

function Group({ title, hint, items, defaultOpen = true }: { title: string; hint?: string; items: Item[]; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mb-1">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted hover:text-text">
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />} {title}
      </button>
      {open && (
        <div className="space-y-0.5">
          {hint && <div className="px-3 pb-1 text-[10px] text-muted/70 leading-tight">{hint}</div>}
          {items.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}
              className={({ isActive }) => `flex items-center gap-3 pl-6 pr-3 py-2 rounded-lg text-sm transition-colors ${
                isActive ? "bg-brand/15 text-white" : "text-muted hover:bg-panel2 hover:text-text"}`}>
              <n.icon size={16} /> {n.label}
            </NavLink>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const { me, logout } = useAuth();
  const [pwOpen, setPwOpen] = useState(false);
  const system = me?.role === "admin" ? [...SYSTEM, { to: "/admin", label: "Admin", icon: ShieldCheck }] : SYSTEM;

  return (
    <div className="flex h-full">
      <aside className="w-64 shrink-0 border-r border-border bg-panel flex flex-col">
        <div className="px-5 py-5 flex items-center gap-2 border-b border-border">
          <Brain className="text-brand" size={22} />
          <div><div className="font-semibold leading-tight">Mnemosyne</div>
            <div className="text-[11px] text-muted">pentest knowledge base</div></div>
        </div>
        <nav className="flex-1 overflow-auto p-3">
          <Group title="Workspace" items={GENERAL} />
          <Group title="Engagement" hint="Scoped to the engagement you pick on each page" items={PER_ENGAGEMENT} />
          <Group title="System" items={system} />
        </nav>
        <div className="p-3 border-t border-border">
          <div className="px-3 py-1 text-xs text-muted truncate">{me?.actor}
            <span className="ml-2 px-1.5 py-0.5 rounded bg-panel2 text-[10px] uppercase">{me?.role}</span></div>
          {me?.kind === "user" && (
            <button onClick={() => setPwOpen(true)} className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-muted hover:bg-panel2 hover:text-text">
              <Lock size={15} /> Change password
            </button>
          )}
          <button onClick={logout} className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-muted hover:bg-panel2 hover:text-text">
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto"><div className="max-w-6xl mx-auto p-8">{children}</div></main>
      {pwOpen && <ChangePassword onClose={() => setPwOpen(false)} />}
    </div>
  );
}

function ChangePassword({ onClose }: { onClose: () => void }) {
  const [cur, setCur] = useState("");
  const [nw, setNw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState("");
  const [done, setDone] = useState(false);
  const m = useMutation({
    mutationFn: () => api.post("/auth/change-password", { current_password: cur, new_password: nw }).then((r) => r.data),
    onSuccess: () => setDone(true),
    onError: (e: any) => setErr(e?.response?.data?.detail || "Failed"),
  });
  return (
    <Modal open onClose={onClose} title="Change password">
      {done ? (
        <div className="space-y-4"><p className="text-emerald-400 text-sm">Password changed.</p>
          <div className="flex justify-end"><Button onClick={onClose}>Done</Button></div></div>
      ) : (
        <div className="space-y-4">
          <Field label="Current password"><Input type="password" value={cur} onChange={(e: any) => setCur(e.target.value)} /></Field>
          <Field label="New password (min 8)"><Input type="password" value={nw} onChange={(e: any) => setNw(e.target.value)} /></Field>
          <Field label="Confirm new password"><Input type="password" value={confirm} onChange={(e: any) => setConfirm(e.target.value)} /></Field>
          {err && <p className="text-sm text-amber-400">{err}</p>}
          {nw && confirm && nw !== confirm && <p className="text-sm text-amber-400">Passwords do not match.</p>}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button onClick={() => { setErr(""); m.mutate(); }} disabled={!cur || nw.length < 8 || nw !== confirm || m.isPending}>Change</Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-end justify-between mb-6">
      <div><h1 className="text-2xl font-semibold">{title}</h1>
        {subtitle && <p className="text-sm text-muted mt-1">{subtitle}</p>}</div>
      {action}
    </div>
  );
}
