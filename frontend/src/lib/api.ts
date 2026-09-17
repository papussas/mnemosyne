import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "/api",
  withCredentials: true,
});

export const crud = {
  list: <T = any>(path: string, params?: any) => api.get<T[]>(path, { params }).then((r) => r.data),
  get: <T = any>(path: string, id: number | string) => api.get<T>(`${path}/${id}`).then((r) => r.data),
  create: <T = any>(path: string, body: any) => api.post<T>(path, body).then((r) => r.data),
  update: <T = any>(path: string, id: number | string, body: any) =>
    api.patch<T>(`${path}/${id}`, body).then((r) => r.data),
  remove: (path: string, id: number | string) => api.delete(`${path}/${id}`).then((r) => r.data),
};

export const apiBase = import.meta.env.VITE_API_BASE || "/api";
export const attThumb = (id: number) => `${apiBase}/attachments/${id}/thumb`;
export const attDownload = (id: number) => `${apiBase}/attachments/${id}/download`;

export async function uploadAttachment(targetType: string, targetId: number, file: File, caption?: string) {
  const fd = new FormData();
  fd.append("target_type", targetType);
  fd.append("target_id", String(targetId));
  if (caption) fd.append("caption", caption);
  fd.append("file", file);
  return api.post("/attachments", fd, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
}
