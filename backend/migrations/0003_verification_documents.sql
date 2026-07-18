-- Documentos de verificação (documento de identidade + selfie) enviados pela
-- própria profissional no autocadastro, pra revisão manual do admin (ver
-- CONTRACTS.md #8 e #10 — sem verificação facial automática por decisão
-- consciente: dado biométrico é sensível pela LGPD e checagem automática
-- exigiria contratar um fornecedor terceiro de KYC).
--
-- UNIQUE (massagista_id, kind): só existe 1 documento de cada tipo por vez —
-- um novo envio SUBSTITUI o anterior (ON CONFLICT DO UPDATE em server.py),
-- nunca acumula histórico. Não fica exposto no endpoint público /api/files —
-- só admin autenticado consegue baixar o arquivo (ver /admin/verification-documents/{id}/file).
CREATE TABLE verification_documents (
    id              TEXT PRIMARY KEY,
    massagista_id   TEXT NOT NULL REFERENCES massagistas(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL CHECK (kind IN ('id_document', 'selfie')),
    storage_path    TEXT NOT NULL,
    content_type    TEXT NOT NULL,
    size            INTEGER NOT NULL,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (massagista_id, kind)
);
CREATE INDEX idx_verification_documents_massagista_id ON verification_documents(massagista_id);
