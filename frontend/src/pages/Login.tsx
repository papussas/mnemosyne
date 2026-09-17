import { useState } from "react";
import { Brain } from "lucide-react";
import { useAuth } from "../lib/auth";
import { Button, Input, Field } from "../components/ui";

export default function Login() {
  const { login } = useAuth();
  const [identifier, setId] = useState("");
  const [password, setPw] = useState("");
  const [otp, setOtp] = useState("");
  const [needOtp, setNeedOtp] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      await login(identifier, password, needOtp ? otp : undefined);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      if (detail === "otp_required") { setNeedOtp(true); setErr("Enter your 2FA code."); }
      else setErr(typeof detail === "string" ? detail : "Login failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="h-full grid place-items-center">
      <form onSubmit={submit} className="w-full max-w-sm bg-panel border border-border rounded-2xl p-8 space-y-5">
        <div className="flex items-center gap-2.5 justify-center">
          <Brain className="text-brand" size={26} />
          <span className="text-xl font-semibold">Mnemosyne</span>
        </div>
        <p className="text-center text-sm text-muted -mt-2">Infra-first pentest knowledge base</p>
        <Field label="Username or email">
          <Input value={identifier} onChange={(e: any) => setId(e.target.value)} autoFocus />
        </Field>
        <Field label="Password">
          <Input type="password" value={password} onChange={(e: any) => setPw(e.target.value)} />
        </Field>
        {needOtp && (
          <Field label="2FA code">
            <Input value={otp} onChange={(e: any) => setOtp(e.target.value)} placeholder="123456" inputMode="numeric" />
          </Field>
        )}
        {err && <p className="text-sm text-amber-400">{err}</p>}
        <Button className="w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</Button>
      </form>
    </div>
  );
}
