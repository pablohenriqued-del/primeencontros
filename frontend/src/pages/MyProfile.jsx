import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, brl, resolveMediaUrl } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import MediaEditor from "@/components/MediaEditor";
import ProfileStats from "@/components/ProfileStats";
import { ShieldAlert, ShieldCheck, Star, ImageIcon, Save, Plus, X, Loader2, FileText, ScanFace, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

const DEFAULT_SPECS = ["Relaxante", "Sueca", "Pedras Quentes", "Shiatsu", "Drenagem Linfática", "Esportiva", "Ortopédica", "Gestante", "Aromaterapia", "Tailandesa"];

export default function MyProfile() {
  const { user, loading: authLoading, login } = useAuth();
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [bairros, setBairros] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [media, setMedia] = useState(false);
  const [verifStatus, setVerifStatus] = useState({ id_document_front: null, id_document_back: null, selfie: null });
  const [verifPreview, setVerifPreview] = useState({ id_document_front: null, id_document_back: null, selfie: null });
  const [verifUploading, setVerifUploading] = useState({ id_document_front: false, id_document_back: false, selfie: false });
  const [pendingDocs, setPendingDocs] = useState({ id_document_front: null, id_document_back: null, selfie: null });
  const [docMode, setDocMode] = useState("photo"); // "photo" (frente+verso) | "pdf" (documento único)
  const idDocFrontInput = useRef(null);
  const idDocBackInput = useRef(null);
  const selfieInput = useRef(null);

  // form state
  const [form, setForm] = useState({
    name: "", bairro_slug: "", bio: "",
    specialties: [], price_60: "", price_90: "", price_120: "",
    experience_years: "", languages: ["Português"],
    ddd: "", phone: "",
  });
  const [newSpec, setNewSpec] = useState("");

  useEffect(() => {
    api.get("/bairros").then(({ data }) => setBairros(data));
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!user) { setLoading(false); return; }
    api.get("/me/profile")
      .then(({ data }) => {
        if (data.profile) {
          setProfile(data.profile);
          setForm({
            name: data.profile.name,
            bairro_slug: data.profile.bairro_slug,
            bio: data.profile.bio,
            specialties: data.profile.specialties || [],
            price_60: String(data.profile.price_60 || ""),
            price_90: String(data.profile.price_90 || ""),
            price_120: String(data.profile.price_120 || ""),
            experience_years: String(data.profile.experience_years || ""),
            languages: data.profile.languages || ["Português"],
            ddd: data.profile.ddd || "",
            phone: data.profile.phone || "",
          });
        } else {
          setForm((f) => ({ ...f, name: user.name || "" }));
        }
      })
      .catch(() => toast.error("Erro ao carregar perfil"))
      .finally(() => setLoading(false));
  }, [user, authLoading]);

  useEffect(() => {
    if (!profile) return;
    api.get("/me/profile/verification/status")
      .then(({ data }) => {
        setVerifStatus(data);
        ["id_document_front", "id_document_back", "selfie"].forEach((kind) => {
          if (!data[kind]) return;
          api.get(`/me/profile/verification/${kind}/file`, { responseType: "blob" })
            .then((res) => {
              const isPdf = res.data.type === "application/pdf";
              setVerifPreview((s) => ({ ...s, [kind]: { url: URL.createObjectURL(res.data), isPdf } }));
              if (kind === "id_document_front" && isPdf) setDocMode("pdf");
            })
            .catch(() => {});
        });
      })
      .catch(() => {});
    /* eslint-disable-next-line */
  }, [profile?.id]);

  const VERIF_PATHS = {
    id_document_front: "/me/profile/verification/id-document-front",
    id_document_back: "/me/profile/verification/id-document-back",
    selfie: "/me/profile/verification/selfie",
  };
  const VERIF_LABELS = {
    id_document_front: "Documento",
    id_document_back: "Verso do documento",
    selfie: "Selfie com o documento",
  };

  const uploadVerifDoc = async (kind, file) => {
    if (!file) return;
    setVerifUploading((s) => ({ ...s, [kind]: true }));
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post(VERIF_PATHS[kind], form, { headers: { "Content-Type": "multipart/form-data" } });
      setVerifStatus((s) => ({ ...s, [kind]: data.document.uploaded_at }));
      toast.success(`${VERIF_LABELS[kind]} enviado(a)`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Falha no upload");
      throw e;
    } finally {
      setVerifUploading((s) => ({ ...s, [kind]: false }));
    }
  };

  // Trocar de modo limpa a seleção pendente da frente/verso (senão um PDF
  // escolhido no modo PDF ficaria "preso" como se fosse a frente no modo foto).
  const switchDocMode = (mode) => {
    setDocMode(mode);
    setPendingDocs((s) => ({ ...s, id_document_front: null, id_document_back: null }));
  };

  // Seleção de arquivo: mostra prévia local na hora. Se o perfil já existe,
  // envia direto; se ainda não existe (autocadastro), guarda o File e só
  // envia depois que o perfil for criado (precisa do massagista_id).
  const onVerifFilePicked = (kind, file) => {
    if (!file) return;
    setVerifPreview((s) => ({ ...s, [kind]: { url: URL.createObjectURL(file), isPdf: file.type === "application/pdf" } }));
    if (profile) {
      uploadVerifDoc(kind, file).catch(() => {});
    } else {
      setPendingDocs((s) => ({ ...s, [kind]: file }));
    }
  };

  if (authLoading || loading) return <div className="max-w-7xl mx-auto px-4 py-20 text-zinc-500">Carregando...</div>;

  if (!user) {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center">
        <h2 className="font-display text-2xl font-medium text-zinc-50">Sou profissional</h2>
        <p className="text-zinc-400 mt-2 mb-6">Entre com Google para cadastrar seu perfil de massoterapeuta na plataforma.</p>
        <Button onClick={login} className="rounded-full bg-red-600 hover:bg-red-700 text-white px-6 h-11">Entrar com Google</Button>
      </div>
    );
  }

  const toggleSpec = (s) => setForm((f) => ({
    ...f,
    specialties: f.specialties.includes(s) ? f.specialties.filter(x => x !== s) : [...f.specialties, s],
  }));

  const addCustomSpec = () => {
    const s = newSpec.trim();
    if (!s) return;
    if (!form.specialties.includes(s)) {
      setForm((f) => ({ ...f, specialties: [...f.specialties, s] }));
    }
    setNewSpec("");
  };

  const save = async () => {
    // Frontend validation with clear PT-BR messages
    const name = form.name.trim();
    if (name.length < 2) { toast.error("Informe seu nome profissional"); return; }
    if (!form.bairro_slug) { toast.error("Selecione o bairro de atendimento"); return; }
    if (form.bio.trim().length < 10) { toast.error("A bio precisa ter pelo menos 10 caracteres"); return; }
    if (form.specialties.length === 0) { toast.error("Escolha ao menos uma especialidade"); return; }
    const p60 = parseFloat(form.price_60);
    if (!p60 || p60 <= 0) { toast.error("Preço de 60 min precisa ser maior que zero"); return; }
    const exp = parseInt(form.experience_years, 10);
    if (Number.isNaN(exp) || exp < 0) { toast.error("Informe seus anos de experiência"); return; }
    if (form.languages.length === 0) { toast.error("Informe ao menos um idioma"); return; }
    const ddd = (form.ddd || "").replace(/\D/g, "");
    const phone = (form.phone || "").replace(/\D/g, "");
    if (ddd.length !== 2) { toast.error("Informe o DDD com 2 dígitos"); return; }
    if (phone.length < 8 || phone.length > 9) { toast.error("Telefone precisa ter 8 ou 9 dígitos"); return; }
    if (!profile) {
      if (!pendingDocs.selfie) { toast.error("Envie a selfie com o documento antes de criar o perfil"); return; }
      if (docMode === "photo" && (!pendingDocs.id_document_front || !pendingDocs.id_document_back)) {
        toast.error("Envie a frente e o verso do documento antes de criar o perfil");
        return;
      }
      if (docMode === "pdf" && !pendingDocs.id_document_front) {
        toast.error("Envie o PDF do documento antes de criar o perfil");
        return;
      }
    }

    setSaving(true);
    try {
      const payload = {
        name,
        bairro_slug: form.bairro_slug,
        bio: form.bio.trim(),
        specialties: form.specialties,
        price_60: p60,
        price_90: form.price_90 ? parseFloat(form.price_90) : undefined,
        price_120: form.price_120 ? parseFloat(form.price_120) : undefined,
        experience_years: exp,
        languages: form.languages,
        ddd,
        phone,
      };
      const wasNew = !profile;
      if (profile) {
        const { data } = await api.put("/me/profile", payload);
        setProfile(data);
        toast.success("Perfil atualizado com sucesso");
      } else {
        const { data } = await api.post("/me/profile", payload);
        setProfile(data);
        try {
          await Promise.all([
            uploadVerifDoc("id_document_front", pendingDocs.id_document_front),
            uploadVerifDoc("selfie", pendingDocs.selfie),
            ...(pendingDocs.id_document_back ? [uploadVerifDoc("id_document_back", pendingDocs.id_document_back)] : []),
          ]);
        } catch {
          toast.error("Perfil criado, mas houve falha ao enviar os documentos — envie novamente na seção abaixo");
        }
        toast.success("Perfil criado · agora envie suas fotos");
        // Auto-open MediaEditor right after creation for a smoother flow
        if (wasNew) setTimeout(() => setMedia(true), 600);
      }
    } catch (e) {
      const detail = e?.response?.data?.detail;
      let msg = "Erro ao salvar";
      if (typeof detail === "string") msg = detail;
      else if (Array.isArray(detail) && detail[0]?.msg) msg = `Campo inválido: ${detail[0].msg}`;
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div data-testid="my-profile-page" className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex items-end justify-between flex-wrap gap-3 mb-6">
        <div>
          <h1 className="font-display text-3xl font-medium text-zinc-50">{profile ? "Meu perfil profissional" : "Cadastrar perfil profissional"}</h1>
          <p className="text-zinc-400 text-sm mt-1">{profile ? "Edite seus dados, preços e disponibilidade." : "Preencha os dados abaixo para começar a receber clientes."}</p>
        </div>
        {profile ? (
          <div className="flex items-center gap-2">
            {profile.verified ? (
              <Badge className="bg-red-600 text-white rounded-full border-0 shadow-[0_0_12px_rgba(220,38,38,0.6)]">
                <ShieldCheck className="h-3 w-3 mr-1" /> Verificada
              </Badge>
            ) : profile.verification?.status === "rejected" ? (
              <Badge className="bg-red-950/40 text-red-300 border border-red-900/50 rounded-full" data-testid="rejected-badge">
                <ShieldAlert className="h-3 w-3 mr-1" /> Verificação rejeitada
              </Badge>
            ) : (
              <Badge className="bg-amber-500/15 text-amber-300 border border-amber-500/40 rounded-full">
                <ShieldAlert className="h-3 w-3 mr-1" /> Aguardando verificação
              </Badge>
            )}
            <Button data-testid="edit-my-media" onClick={() => setMedia(true)} variant="outline" className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900">
              <ImageIcon className="h-4 w-4 mr-1.5" /> Editar fotos / vídeo
            </Button>
          </div>
        ) : (
          <div className="text-xs text-zinc-500 max-w-xs text-right">
            Salve seu perfil para liberar o envio de fotos e vídeo.
          </div>
        )}
      </div>

      {profile && (
        <div className="bg-zinc-950 border border-zinc-900 rounded-2xl p-4 mb-6 flex items-center gap-4">
          <img src={resolveMediaUrl(profile.main_image)} alt="" className="h-16 w-16 rounded-xl object-cover" />
          <div className="flex-1">
            <div className="text-xs text-zinc-500">Como aparece para clientes</div>
            <div className="font-display text-lg text-zinc-50">{profile.name}</div>
            <div className="text-xs text-zinc-400 flex items-center gap-3 mt-0.5">
              <span>{profile.bairro}</span>
              <span className="inline-flex items-center gap-1"><Star className="h-3 w-3 fill-amber-400 text-amber-400" /> {profile.rating?.toFixed(1)} ({profile.reviews})</span>
              <span>{profile.gallery?.length || 0} fotos</span>
            </div>
          </div>
        </div>
      )}

      {profile && (
        <div className="mb-6">
          <ProfileStats />
        </div>
      )}

      {profile?.verification?.status === "rejected" && (
        <div className="bg-red-950/20 border border-red-900/50 rounded-2xl p-4 mb-6 flex items-start gap-3" data-testid="rejection-banner">
          <ShieldAlert className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
          <div>
            <div className="text-sm font-medium text-red-300">Sua verificação foi rejeitada</div>
            <p className="text-sm text-zinc-300 mt-1">
              {profile.verification.notes || "Motivo não informado pelo admin."}
            </p>
            <p className="text-xs text-zinc-500 mt-2">Corrija e reenvie o documento/selfie na seção abaixo — assim que você enviar de novo, sua profissional volta pra fila de análise.</p>
          </div>
        </div>
      )}

      {(!profile || !profile.verified) && (
        <div className="bg-zinc-950 border border-zinc-900 rounded-2xl p-5 sm:p-6 mb-6" data-testid="verification-upload-section">
          <h2 className="font-display text-lg text-zinc-50 mb-1">
            Verificação de identidade {!profile && <span className="text-red-500">*</span>}
          </h2>
          <p className="text-zinc-400 text-sm mb-4">
            {!profile
              ? "Obrigatório para criar seu perfil: documento de identidade + selfie com o documento. Um admin analisa manualmente antes de aprovar o selo \"Verificada\"."
              : "Envie seu documento de identidade + uma selfie com o documento para receber o selo \"Verificada\". Um admin analisa manualmente antes de aprovar."}
          </p>

          <div className="flex gap-2 mb-4">
            <button
              type="button"
              data-testid="doc-mode-photo"
              onClick={() => switchDocMode("photo")}
              className={`text-sm rounded-full px-4 py-1.5 border transition-colors ${docMode === "photo" ? "bg-red-600 border-red-600 text-white" : "border-zinc-800 text-zinc-400 hover:border-zinc-700"}`}
            >
              Foto (frente e verso)
            </button>
            <button
              type="button"
              data-testid="doc-mode-pdf"
              onClick={() => switchDocMode("pdf")}
              className={`text-sm rounded-full px-4 py-1.5 border transition-colors ${docMode === "pdf" ? "bg-red-600 border-red-600 text-white" : "border-zinc-800 text-zinc-400 hover:border-zinc-700"}`}
            >
              PDF (documento único)
            </button>
          </div>

          <div className={`grid grid-cols-1 gap-4 ${docMode === "photo" ? "sm:grid-cols-3" : "sm:grid-cols-2"}`}>
            {(docMode === "photo"
              ? [
                  { kind: "id_document_front", label: "Frente do documento", icon: FileText, ref: idDocFrontInput, required: true, accept: "image/jpeg,image/png,image/webp", hint: "JPG, PNG ou WEBP · até 8MB" },
                  { kind: "id_document_back", label: "Verso do documento", icon: FileText, ref: idDocBackInput, required: true, accept: "image/jpeg,image/png,image/webp", hint: "JPG, PNG ou WEBP · até 8MB" },
                  { kind: "selfie", label: "Selfie com o documento", icon: ScanFace, ref: selfieInput, required: true, accept: "image/jpeg,image/png,image/webp", hint: "JPG, PNG ou WEBP · até 8MB" },
                ]
              : [
                  { kind: "id_document_front", label: "Documento (PDF)", icon: FileText, ref: idDocFrontInput, required: true, accept: "application/pdf", hint: "Arquivo PDF · até 8MB" },
                  { kind: "selfie", label: "Selfie com o documento", icon: ScanFace, ref: selfieInput, required: true, accept: "image/jpeg,image/png,image/webp", hint: "JPG, PNG ou WEBP · até 8MB" },
                ]
            ).map(({ kind, label, icon: Icon, ref, required, accept, hint }) => {
              const sent = !!verifStatus[kind];
              const selected = !profile && !!pendingDocs[kind];
              const preview = verifPreview[kind];
              return (
                <div key={kind}>
                  <button
                    type="button"
                    data-testid={`upload-${kind.replaceAll("_", "-")}-button`}
                    disabled={verifUploading[kind]}
                    onClick={() => ref.current?.click()}
                    className={`relative w-full overflow-hidden rounded-xl border-2 border-dashed px-4 py-5 flex flex-col items-center justify-center gap-2 transition-colors disabled:opacity-50
                      ${sent || selected ? "border-red-600/40 bg-red-600/5 text-red-300" : "border-zinc-800 hover:border-red-600 hover:bg-red-600/5 text-zinc-400 hover:text-red-400"}`}
                  >
                    {preview && !preview.isPdf && (
                      <img src={preview.url} alt={label} className="absolute inset-0 w-full h-full object-cover opacity-40" />
                    )}
                    <div className="relative flex flex-col items-center gap-2">
                      {verifUploading[kind] ? (
                        <Loader2 className="h-6 w-6 animate-spin" />
                      ) : sent || selected ? (
                        <CheckCircle2 className="h-6 w-6" />
                      ) : (
                        <Icon className="h-6 w-6" />
                      )}
                      <span className="text-sm font-medium">{label}{!profile && required && <span className="text-red-500"> *</span>}</span>
                      <span className="text-[10px] text-zinc-600">
                        {sent
                          ? `${preview?.isPdf ? "PDF enviado" : "Enviado"} em ${new Date(verifStatus[kind]).toLocaleDateString("pt-BR")} · toque para substituir`
                          : selected
                          ? `${preview?.isPdf ? "PDF selecionado" : "Selecionado"} · será enviado ao criar o perfil`
                          : hint}
                      </span>
                    </div>
                  </button>
                  <input
                    ref={ref}
                    type="file"
                    accept={accept}
                    className="hidden"
                    onChange={(e) => onVerifFilePicked(kind, e.target.files?.[0])}
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="bg-zinc-950 border border-zinc-900 rounded-2xl p-5 sm:p-6 space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">Nome profissional</Label>
            <Input data-testid="profile-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Como você aparece para os clientes" className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">Bairro de atendimento</Label>
            <Select value={form.bairro_slug} onValueChange={(v) => setForm({ ...form, bairro_slug: v })}>
              <SelectTrigger data-testid="profile-bairro" className="mt-2 h-10 rounded-xl bg-black border-zinc-800 text-zinc-200">
                <SelectValue placeholder="Selecione" />
              </SelectTrigger>
              <SelectContent className="bg-zinc-950 border-zinc-800 text-zinc-200">
                {bairros.map(b => <SelectItem key={b.slug} value={b.slug}>{b.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div>
          <Label className="text-xs uppercase tracking-wider text-zinc-500">Bio · descreva seu trabalho</Label>
          <Textarea data-testid="profile-bio" value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} maxLength={600} placeholder="Conte sua formação, técnicas, abordagem..." className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100 resize-none h-28" />
        </div>

        <div>
          <Label className="text-xs uppercase tracking-wider text-zinc-500">Especialidades</Label>
          <div className="mt-2 flex flex-wrap gap-2">
            {DEFAULT_SPECS.map(s => {
              const on = form.specialties.includes(s);
              return (
                <button
                  key={s}
                  type="button"
                  data-testid={`spec-${s}`}
                  onClick={() => toggleSpec(s)}
                  className={`text-sm rounded-full px-3 py-1.5 border transition-colors
                    ${on ? "bg-red-600 border-red-600 text-white" : "border-zinc-800 text-zinc-300 hover:border-zinc-700"}`}
                >
                  {s}
                </button>
              );
            })}
            {form.specialties.filter(s => !DEFAULT_SPECS.includes(s)).map(s => (
              <button
                key={s}
                type="button"
                onClick={() => toggleSpec(s)}
                className="text-sm rounded-full px-3 py-1.5 border bg-red-600 border-red-600 text-white inline-flex items-center gap-1"
              >
                {s} <X className="h-3 w-3" />
              </button>
            ))}
          </div>
          <div className="mt-2 flex gap-2">
            <Input value={newSpec} onChange={(e) => setNewSpec(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustomSpec())} placeholder="Adicionar outra..." className="flex-1 h-9 rounded-xl bg-black border-zinc-800 text-zinc-100" data-testid="profile-new-spec" />
            <Button type="button" onClick={addCustomSpec} variant="outline" className="rounded-xl border-zinc-700 text-zinc-200 hover:bg-zinc-900 h-9"><Plus className="h-4 w-4" /></Button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">60 min (R$)</Label>
            <Input data-testid="price-60" type="number" min="0" step="10" value={form.price_60} onChange={(e) => setForm({ ...form, price_60: e.target.value })} className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">90 min (R$)</Label>
            <Input data-testid="price-90" type="number" min="0" step="10" value={form.price_90} onChange={(e) => setForm({ ...form, price_90: e.target.value })} placeholder="auto" className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">120 min (R$)</Label>
            <Input data-testid="price-120" type="number" min="0" step="10" value={form.price_120} onChange={(e) => setForm({ ...form, price_120: e.target.value })} placeholder="auto" className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">Anos de experiência</Label>
            <Input data-testid="profile-experience" type="number" min="0" max="60" value={form.experience_years} onChange={(e) => setForm({ ...form, experience_years: e.target.value })} className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wider text-zinc-500">Idiomas (separados por vírgula)</Label>
            <Input data-testid="profile-languages" value={form.languages.join(", ")} onChange={(e) => setForm({ ...form, languages: e.target.value.split(",").map(s => s.trim()).filter(Boolean) })} className="mt-2 rounded-xl bg-black border-zinc-800 text-zinc-100" />
          </div>
        </div>

        <div>
          <Label className="text-xs uppercase tracking-wider text-zinc-500">WhatsApp · clientes vão te chamar direto por aqui</Label>
          <div className="mt-2 grid grid-cols-[100px_1fr] gap-3">
            <Input
              data-testid="profile-ddd"
              value={form.ddd}
              onChange={(e) => setForm({ ...form, ddd: e.target.value.replace(/\D/g, "").slice(0, 2) })}
              placeholder="DDD"
              maxLength={2}
              inputMode="numeric"
              className="rounded-xl bg-black border-zinc-800 text-zinc-100 text-center font-medium"
            />
            <Input
              data-testid="profile-phone"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value.replace(/\D/g, "").slice(0, 9) })}
              placeholder="Número (9 dígitos)"
              maxLength={9}
              inputMode="numeric"
              className="rounded-xl bg-black border-zinc-800 text-zinc-100"
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 pt-2 border-t border-zinc-900">
          {!profile && (
            <Button onClick={() => navigate("/")} variant="outline" className="rounded-full border-zinc-700 text-zinc-200 hover:bg-zinc-900">Cancelar</Button>
          )}
          <Button
            data-testid="save-profile"
            onClick={save}
            disabled={saving}
            className="rounded-full bg-red-600 hover:bg-red-700 text-white px-5 shadow-lg shadow-red-600/25"
          >
            {saving ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Save className="h-4 w-4 mr-1.5" />}
            {profile ? "Salvar alterações" : "Criar perfil"}
          </Button>
        </div>
      </div>

      {profile && (
        <MediaEditor
          open={media}
          massagista={profile}
          owner
          onClose={() => setMedia(false)}
          onUpdated={(updated) => setProfile(updated)}
        />
      )}
    </div>
  );
}
