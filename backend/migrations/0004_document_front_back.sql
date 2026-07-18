-- Separa o documento de identidade em frente/verso. Verso é OPCIONAL de
-- propósito — CNH Digital (app) é uma tela única, sem verso; só RG/CNH física
-- têm os dois lados. A obrigatoriedade em server.py (approve_verification)
-- cobra só id_document_front + selfie; id_document_back fica de fora do
-- conjunto obrigatório.
--
-- Renomeia 'id_document' -> 'id_document_front' pra não perder o que já foi
-- enviado antes desta migration (ambiente local/dev, mas mantém o padrão de
-- migration segura mesmo assim).
ALTER TABLE verification_documents DROP CONSTRAINT verification_documents_kind_check;

UPDATE verification_documents SET kind = 'id_document_front' WHERE kind = 'id_document';

ALTER TABLE verification_documents
    ADD CONSTRAINT verification_documents_kind_check
    CHECK (kind IN ('id_document_front', 'id_document_back', 'selfie'));
