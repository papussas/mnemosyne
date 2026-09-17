import { ReactNode } from "react";

export function Button({ children, variant = "primary", className = "", ...p }: any) {
  const styles: Record<string, string> = {
    primary: "bg-brand hover:bg-brand2 text-white",
    ghost: "bg-transparent hover:bg-panel2 text-muted hover:text-text",
    danger: "bg-red-600/90 hover:bg-red-600 text-white",
    outline: "border border-border hover:bg-panel2 text-text",
  };
  return (
    <button {...p} className={`px-3.5 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${styles[variant]} ${className}`}>
      {children}
    </button>
  );
}

export function Input(p: any) {
  return <input {...p} className={`w-full bg-panel2 border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-brand ${p.className || ""}`} />;
}

export function Textarea(p: any) {
  return <textarea {...p} className={`w-full bg-panel2 border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-brand font-mono ${p.className || ""}`} />;
}

export function Select({ children, ...p }: any) {
  return <select {...p} className="w-full bg-panel2 border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-brand">{children}</select>;
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block space-y-1.5"><span className="text-xs font-medium text-muted">{label}</span>{children}</label>;
}

export function Card({ children, className = "", ...rest }: any) {
  return <div {...rest} className={`bg-panel border border-border rounded-xl ${className}`}>{children}</div>;
}

const sevColor: Record<string, string> = {
  critical: "bg-red-500/15 text-red-300 border-red-500/30",
  high: "bg-orange-500/15 text-orange-300 border-orange-500/30",
  medium: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
  low: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  info: "bg-slate-500/15 text-slate-300 border-slate-500/30",
};
export function Badge({ children, tone }: { children: ReactNode; tone?: string }) {
  const c = (tone && sevColor[tone]) || "bg-panel2 text-muted border-border";
  return <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border ${c}`}>{children}</span>;
}

export function Modal({ open, onClose, title, children, wide }: any) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div className={`w-full ${wide ? "max-w-3xl" : "max-w-lg"} max-h-[90vh] overflow-auto bg-panel border border-border rounded-xl p-5`} onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold mb-4">{title}</h3>
        {children}
      </div>
    </div>
  );
}
