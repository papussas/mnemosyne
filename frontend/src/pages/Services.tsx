import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search, ExternalLink, ImageOff, Paperclip } from "lucide-react";
import { crud, attThumb, attDownload } from "../lib/api";
import { Input, Card, Badge, Modal } from "../components/ui";
import { PageHeader } from "../components/Layout";

const liveScheme = (t: string) => (t === "https" ? "https" : t === "http" ? "http" : null);
const liveUrlOf = (h: any, s: any) => {
  const sch = liveScheme(s.service_type);
  return sch ? `${sch}://${h.ip}:${s.port}` : null;
};

export default function Services() {
  const [sp, setSp] = useSearchParams();
  const { data: engs } = useQuery({ queryKey: ["engagements"], queryFn: () => crud.list("/engagements") });
  const engId = sp.get("engagement") || engs?.[0]?.id?.toString() || "";
  const setEng = (v: string) => { sp.set("engagement", v); setSp(sp); };

  const [q, setQ] = useState("");
  const [port, setPort] = useState("");
  const [onlyImages, setOnlyImages] = useState(false);
  const [overlay, setOverlay] = useState<any>(null);

  const gallery = useQuery({
    queryKey: ["gallery", engId, q, port, onlyImages],
    enabled: !!engId,
    queryFn: () => crud.list("/gallery/services", {
      engagement_id: engId, q: q || undefined, port: port || undefined,
      only_with_images: onlyImages || undefined,
    }),
  });

  return (
    <div>
      <PageHeader title="Services" subtitle="Every service in the engagement, with its screenshots. Click a card to preview the image and details."
        action={<select className="bg-panel2 border border-border rounded-lg px-3 py-2 text-sm"
          value={engId} onChange={(e) => setEng(e.target.value)}>
          {engs?.map((e: any) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>} />

      <div className="flex flex-wrap items-center gap-3 mb-5">
        <div className="relative flex-1 min-w-[220px]">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <Input className="pl-9" placeholder="Search description, product, banner, hostname…" value={q} onChange={(e: any) => setQ(e.target.value)} />
        </div>
        <Input className="w-28" placeholder="port" value={port} onChange={(e: any) => setPort(e.target.value.replace(/[^0-9]/g, ""))} />
        <label className="flex items-center gap-2 text-sm text-muted whitespace-nowrap">
          <input type="checkbox" checked={onlyImages} onChange={(e) => setOnlyImages(e.target.checked)} /> With screenshots only
        </label>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {gallery.data?.map((row: any) => {
          const s = row.service, h = row.host;
          const img = row.images?.[0];
          const liveUrl = liveUrlOf(h, s);
          return (
            <Card key={s.id} className="overflow-hidden flex flex-col cursor-pointer hover:border-brand transition-colors"
                  onClick={() => setOverlay(row)}>
              <div className="h-40 bg-panel2">
                {img
                  ? <img src={attThumb(img.id)} alt={img.caption || ""} className="w-full h-40 object-cover" />
                  : <div className="h-40 grid place-items-center text-muted"><ImageOff size={26} /></div>}
              </div>
              <div className="p-4 flex-1 flex flex-col">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-sm font-medium">{h.ip}:{s.port}</span>
                  <Badge>{s.service_type}</Badge>
                  {row.images?.length > 1 && <span className="text-[11px] text-muted">+{row.images.length - 1} img</span>}
                </div>
                <div className="text-xs text-muted mb-1">{h.hostname || ""} {(s.product || s.version) ? `· ${s.product || ""} ${s.version || ""}` : ""}</div>
                {s.description && <div className="text-sm mb-3 line-clamp-3">{s.description}</div>}
                <div className="mt-auto flex items-center gap-3 pt-2">
                  {liveUrl && <a href={liveUrl} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="text-sm text-brand hover:underline flex items-center gap-1"><ExternalLink size={14} /> Open live</a>}
                  <span className="text-xs text-muted flex items-center gap-1"><Paperclip size={12} /> {row.attachment_count}</span>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
      {gallery.data && gallery.data.length === 0 && (
        <div className="text-center text-muted text-sm py-12">No services match. Add services & screenshots under Hosts & Services.</div>
      )}

      {overlay && <ServiceOverlay row={overlay} onClose={() => setOverlay(null)} />}
    </div>
  );
}

function ServiceOverlay({ row, onClose }: { row: any; onClose: () => void }) {
  const s = row.service, h = row.host;
  const images: any[] = row.images || [];
  const [active, setActive] = useState<number | null>(images[0]?.id ?? null);
  const liveUrl = liveUrlOf(h, s);

  const Detail = ({ label, value, mono }: any) => value ? (
    <div><span className="text-muted">{label}: </span><span className={mono ? "font-mono" : ""}>{value}</span></div>
  ) : null;

  return (
    <Modal open onClose={onClose} wide title={
      <span className="flex items-center gap-2 font-mono">{h.ip}:{s.port} <Badge>{s.service_type}</Badge></span>}>
      {/* image viewer */}
      {active != null ? (
        <a href={attDownload(active)} target="_blank" rel="noreferrer" title="Open full size in new tab" className="block">
          <img src={attDownload(active)} alt="" className="max-h-[60vh] w-auto mx-auto rounded-lg border border-border bg-panel2" />
        </a>
      ) : (
        <div className="h-40 grid place-items-center text-muted bg-panel2 rounded-lg"><ImageOff size={28} /></div>
      )}
      {images.length > 1 && (
        <div className="flex gap-2 mt-3 flex-wrap">
          {images.map((im) => (
            <button key={im.id} onClick={() => setActive(im.id)}
              className={`w-16 h-16 rounded overflow-hidden border ${active === im.id ? "border-brand" : "border-border"}`}>
              <img src={attThumb(im.id)} alt={im.caption || ""} className="w-full h-full object-cover" />
            </button>
          ))}
        </div>
      )}

      {/* details */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm mt-5 border-t border-border pt-4">
        <Detail label="Host" value={`${h.ip}${h.hostname ? ` (${h.hostname})` : ""}`} mono />
        <Detail label="Port" value={`${s.port}/${s.proto}`} mono />
        <Detail label="Type" value={s.service_type} />
        <Detail label="Product" value={[s.product, s.version].filter(Boolean).join(" ")} />
        {liveUrl && <div className="col-span-2"><a href={liveUrl} target="_blank" rel="noreferrer" className="text-brand hover:underline inline-flex items-center gap-1"><ExternalLink size={14} /> {liveUrl}</a></div>}
        {s.description && <div className="col-span-2"><span className="text-muted">Description: </span>{s.description}</div>}
        {s.notes && <div className="col-span-2"><span className="text-muted">Notes: </span>{s.notes}</div>}
        {s.banner && <div className="col-span-2"><span className="text-muted">Banner: </span><pre className="font-mono text-xs whitespace-pre-wrap mt-1 bg-panel2 rounded p-2">{s.banner}</pre></div>}
      </div>
    </Modal>
  );
}
