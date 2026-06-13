import { useEffect, useRef, useState } from "react";
import { api, API_BASE } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Upload, Trash2, Star, Loader2, Image as ImageIcon, Video as VideoIcon, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

// resolves "/api/files/..." (relative) to absolute backend URL; passes through full URLs
function resolveUrl(u) {
  if (!u) return u;
  if (u.startsWith("http")) return u;
  const root = API_BASE.replace(/\/api$/, "");
  return `${root}${u}`;
}

export default function MediaEditor({ open, massagista, onClose, onUpdated, owner = false }) {
  const [m, setM] = useState(massagista);
  const [tab, setTab] = useState("photos");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const photoInput = useRef(null);
  const videoInput = useRef(null);

  useEffect(() => { setM(massagista); }, [massagista]);

  if (!m) return null;

  const paths = owner
    ? { photo: `/me/profile/photo`, setMain: `/me/profile/set-main`, video: `/me/profile/video` }
    : {
        photo: `/admin/massagistas/${m.id}/photo`,
        setMain: `/admin/massagistas/${m.id}/set-main`,
        video: `/admin/massagistas/${m.id}/video`,
      };

  const refresh = async () => {
    try {
      const { data } = await api.get(`/massagistas/${m.id}`);
      setM(data);
      onUpdated?.(data);
    } catch {}
  };

  const onPickPhoto = () => photoInput.current?.click();
  const onPickVideo = () => videoInput.current?.click();

  const uploadFile = async (file, kind) => {
    if (!file) return;
    setUploading(true);
    setProgress(0);
    try {
      const form = new FormData();
      form.append("file", file);
      const path = kind === "photo" ? paths.photo : paths.video;
      const { data } = await api.post(path, form, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => {
          if (e.total) setProgress(Math.round((e.loaded / e.total) * 100));
        },
      });
      setM(data.massagista);
      onUpdated?.(data.massagista);
      toast.success(kind === "photo" ? "Foto adicionada à galeria" : "Vídeo atualizado");
    } catch (e) {
      const msg = e?.response?.data?.detail || "Falha no upload";
      toast.error(msg);
    } finally {
      setUploading(false);
      setProgress(0);
      if (photoInput.current) photoInput.current.value = "";
      if (videoInput.current) videoInput.current.value = "";
    }
  };

  const removePhoto = async (url) => {
    if (!window.confirm("Remover esta foto da galeria?")) return;
    try {
      const { data } = await api.delete(paths.photo, { data: { url } });
      setM(data.massagista);
      onUpdated?.(data.massagista);
      toast.success("Foto removida");
    } catch {
      toast.error("Erro ao remover");
    }
  };

  const setAsMain = async (url) => {
    try {
      const { data } = await api.post(paths.setMain, { url });
      setM(data.massagista);
      onUpdated?.(data.massagista);
      toast.success("Imagem principal atualizada");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Erro ao definir principal");
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose?.()}>
      <DialogContent className="bg-zinc-950 border border-zinc-900 text-zinc-100 max-w-3xl">
        <DialogHeader>
          <DialogTitle className="font-display text-xl text-zinc-50">Mídia · {m.name}</DialogTitle>
          <DialogDescription className="text-zinc-400">{m.bairro} · {m.gallery?.length || 0} fotos · vídeo {m.video_url ? "configurado" : "ausente"}</DialogDescription>
        </DialogHeader>

        <Tabs value={tab} onValueChange={setTab} className="w-full">
          <TabsList className="bg-black border border-zinc-900 rounded-full p-1">
            <TabsTrigger value="photos" className="rounded-full data-[state=active]:bg-red-600 data-[state=active]:text-white text-zinc-400" data-testid="media-tab-photos">
              <ImageIcon className="h-4 w-4 mr-1.5" /> Fotos
            </TabsTrigger>
            <TabsTrigger value="video" className="rounded-full data-[state=active]:bg-red-600 data-[state=active]:text-white text-zinc-400" data-testid="media-tab-video">
              <VideoIcon className="h-4 w-4 mr-1.5" /> Vídeo
            </TabsTrigger>
          </TabsList>

          <TabsContent value="photos" className="mt-5">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {(m.gallery || []).map((url, i) => {
                const isMain = m.main_image === url;
                return (
                  <div key={`${url}-${i}`} className={`group relative aspect-square rounded-xl overflow-hidden border ${isMain ? "border-red-600 ring-2 ring-red-600/50" : "border-zinc-800"}`}>
                    <img src={resolveUrl(url)} alt="" className="w-full h-full object-cover" />
                    {isMain && (
                      <div className="absolute top-2 left-2 inline-flex items-center gap-1 text-[10px] uppercase tracking-wider bg-red-600 text-white px-2 py-0.5 rounded-full font-semibold">
                        <Star className="h-3 w-3 fill-white" /> Principal
                      </div>
                    )}
                    <div className="absolute inset-x-0 bottom-0 p-2 bg-gradient-to-t from-black to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex gap-1.5">
                      {!isMain && (
                        <Button
                          size="sm"
                          data-testid={`set-main-${i}`}
                          onClick={() => setAsMain(url)}
                          className="h-7 px-2 rounded-md bg-zinc-900 hover:bg-zinc-800 text-zinc-100 text-xs"
                        >
                          <Star className="h-3 w-3 mr-1" /> Tornar principal
                        </Button>
                      )}
                      <Button
                        size="sm"
                        data-testid={`delete-photo-${i}`}
                        onClick={() => removePhoto(url)}
                        className="h-7 px-2 rounded-md bg-red-600 hover:bg-red-700 text-white text-xs"
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                );
              })}
              <button
                onClick={onPickPhoto}
                data-testid="upload-photo-button"
                disabled={uploading}
                className="aspect-square rounded-xl border-2 border-dashed border-zinc-800 hover:border-red-600 hover:bg-red-600/5 text-zinc-400 hover:text-red-400 flex flex-col items-center justify-center gap-2 transition-colors disabled:opacity-50"
              >
                <Upload className="h-6 w-6" />
                <span className="text-xs font-medium">Enviar foto</span>
                <span className="text-[10px] text-zinc-600">JPG, PNG, WEBP · até 8MB</span>
              </button>
              <input
                ref={photoInput}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(e) => uploadFile(e.target.files?.[0], "photo")}
              />
            </div>
          </TabsContent>

          <TabsContent value="video" className="mt-5 space-y-4">
            {m.video_url ? (
              <video
                src={resolveUrl(m.video_url)}
                controls
                className="w-full rounded-xl border border-zinc-800 bg-black aspect-video"
                data-testid="current-video"
              />
            ) : (
              <div className="aspect-video rounded-xl border border-zinc-800 bg-black flex items-center justify-center text-zinc-500 text-sm">
                Nenhum vídeo configurado
              </div>
            )}
            <button
              onClick={onPickVideo}
              data-testid="upload-video-button"
              disabled={uploading}
              className="w-full rounded-xl border-2 border-dashed border-zinc-800 hover:border-red-600 hover:bg-red-600/5 text-zinc-400 hover:text-red-400 py-6 flex flex-col items-center justify-center gap-2 transition-colors disabled:opacity-50"
            >
              <Upload className="h-7 w-7" />
              <span className="text-sm font-medium">{m.video_url ? "Substituir vídeo" : "Enviar vídeo"}</span>
              <span className="text-xs text-zinc-600">MP4, MOV, WEBM · até 100MB</span>
            </button>
            <input
              ref={videoInput}
              type="file"
              accept="video/mp4,video/quicktime,video/webm"
              className="hidden"
              onChange={(e) => uploadFile(e.target.files?.[0], "video")}
            />
          </TabsContent>
        </Tabs>

        {uploading && (
          <div className="mt-4 bg-black border border-zinc-800 rounded-xl p-3 flex items-center gap-3">
            <Loader2 className="h-4 w-4 animate-spin text-red-500" />
            <div className="flex-1">
              <div className="text-xs text-zinc-300 mb-1">Enviando — {progress}%</div>
              <Progress value={progress} className="h-1.5 bg-zinc-900 [&>div]:bg-red-600" />
            </div>
          </div>
        )}

        {!uploading && (m.gallery?.length || 0) > 0 && (
          <div className="mt-3 text-[11px] text-zinc-500 flex items-center gap-1.5">
            <CheckCircle2 className="h-3 w-3 text-red-500" /> Alterações são publicadas imediatamente no perfil público.
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
