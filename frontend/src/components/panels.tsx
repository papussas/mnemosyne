import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Paperclip, FileText, Plus, Upload, Download, Trash2 } from "lucide-react";
import { crud, uploadAttachment, attThumb, attDownload } from "../lib/api";
import { Button, Input, Textarea } from "./ui";

export function EvidencePanel({ query, createDefaults }: { query: Record<string, any>; createDefaults: Record<string, any> }) {
  const qc = useQueryClient();
  const key = ["evidence", query];
  const { data } = useQuery({ queryKey: key, queryFn: () => crud.list("/evidence", query) });
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const add = useMutation({
    mutationFn: () => crud.create("/evidence", { ...createDefaults, title, content }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: key }); setTitle(""); setContent(""); },
  });
  return (
    <div>
      <div className="flex items-center gap-2 mb-2 text-sm font-medium text-muted"><FileText size={15} /> Evidence</div>
      <div className="space-y-2 mb-3">
        {data?.map((e: any) => (
          <div key={e.id} className="bg-panel2 border border-border rounded-lg px-3 py-2">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium">{e.title}</span>
              <span className="text-[11px] text-muted">{e.author} · {new Date(e.created_at).toLocaleString()}</span>
            </div>
            {e.content && <pre className="text-xs text-muted whitespace-pre-wrap font-mono mt-1">{e.content}</pre>}
          </div>
        ))}
        {!data?.length && <div className="text-xs text-muted">No evidence yet.</div>}
      </div>
      <div className="space-y-2 border-t border-border pt-3">
        <Input placeholder="Evidence title (e.g. nmap smb-protocols)" value={title} onChange={(e: any) => setTitle(e.target.value)} />
        <Textarea rows={2} placeholder="Tool output / observation…" value={content} onChange={(e: any) => setContent(e.target.value)} />
        <Button variant="outline" onClick={() => add.mutate()} disabled={!title || add.isPending}>
          <span className="flex items-center gap-1.5"><Plus size={15} /> Add evidence</span></Button>
      </div>
    </div>
  );
}

export function AttachmentPanel({ targetType, targetId }: { targetType: string; targetId: number }) {
  const qc = useQueryClient();
  const key = ["attachments", targetType, targetId];
  const { data } = useQuery({ queryKey: key, queryFn: () => crud.list("/attachments", { target_type: targetType, target_id: targetId }) });
  const fileRef = useRef<HTMLInputElement>(null);
  const [caption, setCaption] = useState("");
  const up = useMutation({
    mutationFn: (file: File) => uploadAttachment(targetType, targetId, file, caption),
    onSuccess: () => { qc.invalidateQueries({ queryKey: key }); setCaption(""); if (fileRef.current) fileRef.current.value = ""; },
  });
  const del = useMutation({
    mutationFn: (id: number) => crud.remove("/attachments", id),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  });
  return (
    <div>
      <div className="flex items-center gap-2 mb-2 text-sm font-medium text-muted"><Paperclip size={15} /> Attachments & screenshots</div>
      <div className="grid grid-cols-3 gap-2 mb-3">
        {data?.map((a: any) => (
          <div key={a.id} className="relative group bg-panel2 border border-border rounded-lg overflow-hidden hover:border-brand">
            <a href={attDownload(a.id)} target="_blank" rel="noreferrer" className="block">
              {a.mime?.startsWith("image/")
                ? <img src={attThumb(a.id)} alt={a.caption || a.filename} className="w-full h-24 object-cover" />
                : <div className="h-24 grid place-items-center text-muted"><Download size={20} /></div>}
              <div className="px-2 py-1 text-[11px] text-muted truncate">{a.caption || a.filename}</div>
            </a>
            <button title="Delete attachment"
              onClick={() => confirm("Delete this attachment?") && del.mutate(a.id)}
              className="absolute top-1 right-1 p-1 rounded bg-black/50 text-white opacity-0 group-hover:opacity-100 hover:bg-red-600 transition">
              <Trash2 size={13} />
            </button>
          </div>
        ))}
        {!data?.length && <div className="col-span-3 text-xs text-muted">No attachments yet.</div>}
      </div>
      <div className="flex items-center gap-2 border-t border-border pt-3">
        <Input placeholder="Caption (optional)" value={caption} onChange={(e: any) => setCaption(e.target.value)} className="flex-1" />
        <input ref={fileRef} type="file" className="hidden" onChange={(e) => e.target.files?.[0] && up.mutate(e.target.files[0])} />
        <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={up.isPending}>
          <span className="flex items-center gap-1.5"><Upload size={15} /> {up.isPending ? "Uploading…" : "Upload"}</span></Button>
      </div>
    </div>
  );
}
