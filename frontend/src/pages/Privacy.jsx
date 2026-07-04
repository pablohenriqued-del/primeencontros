import { Link } from "react-router-dom";

// LGPD-compliant Privacy Policy for Prime Encontros.
const CONTACT_EMAIL = "contato@primeencontros.com";
const CONTROLLER = "Pablo Henrique Duarte";
const LOCATION = "Rio de Janeiro / RJ";
const UPDATED_AT = "13 de junho de 2026";

function H2({ children }) {
  return <h2 className="font-display text-xl sm:text-2xl text-zinc-50 mt-8 mb-3">{children}</h2>;
}
function P({ children }) {
  return <p className="text-sm text-zinc-300 leading-relaxed mb-3">{children}</p>;
}
function Li({ children }) {
  return <li className="text-sm text-zinc-300 leading-relaxed">{children}</li>;
}

export default function Privacy() {
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14" data-testid="privacy-page">
      <div className="mb-6 text-xs uppercase tracking-[0.2em] text-red-500 font-semibold">Documento legal</div>
      <h1 className="font-display text-3xl sm:text-4xl text-zinc-50 mb-2">Política de Privacidade</h1>
      <div className="text-xs text-zinc-500 mb-8">Última atualização: {UPDATED_AT}</div>

      <P>
        Esta Política de Privacidade descreve como o <strong>Prime Encontros</strong> coleta, usa,
        compartilha e protege suas informações pessoais, em conformidade com a Lei Geral de Proteção
        de Dados Pessoais (Lei nº 13.709/2018 — <strong>LGPD</strong>).
      </P>
      <P>
        Ao utilizar nossa plataforma (site, aplicativo ou qualquer serviço vinculado), você declara ter
        lido, compreendido e aceito integralmente os termos aqui descritos.
      </P>

      <H2>1. Controlador dos dados</H2>
      <P>
        O controlador dos dados pessoais coletados é <strong>{CONTROLLER}</strong>, sediado em {LOCATION},
        que pode ser contatado pelo e-mail <a href={`mailto:${CONTACT_EMAIL.replace(/\[|\]/g, "")}`} className="text-red-500 hover:underline">{CONTACT_EMAIL}</a>.
      </P>

      <H2>2. Dados que coletamos</H2>
      <ul className="list-disc pl-6 space-y-2">
        <Li><strong>Identificação:</strong> nome, e-mail e foto pública (via Google OAuth).</Li>
        <Li><strong>Contato:</strong> telefone/WhatsApp informado voluntariamente pelas profissionais.</Li>
        <Li><strong>Geolocalização:</strong> localização aproximada (bairro) apenas quando você usa "Perto de mim".</Li>
        <Li><strong>Reservas e transações:</strong> data, hora, duração, endereço de atendimento, valor, status.</Li>
        <Li><strong>Pagamentos:</strong> processados pela Stripe. Nós <strong>não armazenamos</strong> dados de cartão de crédito.</Li>
        <Li><strong>Métricas de uso:</strong> visitas ao perfil, cliques no WhatsApp, avaliações.</Li>
        <Li><strong>Conteúdo enviado:</strong> fotos, vídeo e biografia das profissionais.</Li>
      </ul>

      <H2>3. Finalidade do tratamento</H2>
      <P>Utilizamos seus dados para as seguintes finalidades:</P>
      <ul className="list-disc pl-6 space-y-2">
        <Li>Permitir a criação e gestão da sua conta.</Li>
        <Li>Intermediar reservas entre clientes e profissionais.</Li>
        <Li>Processar pagamentos e emitir recibos.</Li>
        <Li>Enviar comunicações operacionais (confirmação, cancelamento, avaliação).</Li>
        <Li>Prevenir fraude, uso indevido e garantir a segurança da plataforma.</Li>
        <Li>Melhorar a experiência do usuário por meio de métricas anonimizadas.</Li>
      </ul>

      <H2>4. Base legal (Art. 7º LGPD)</H2>
      <P>
        O tratamento dos seus dados baseia-se em <strong>consentimento</strong>,
        <strong> execução de contrato</strong>, <strong>legítimo interesse</strong> e
        <strong> cumprimento de obrigação legal ou regulatória</strong>, conforme o caso concreto.
      </P>

      <H2>5. Compartilhamento com terceiros</H2>
      <P>
        Compartilhamos dados apenas com <strong>operadores necessários à prestação do serviço</strong>:
      </P>
      <ul className="list-disc pl-6 space-y-2">
        <Li><strong>Google LLC</strong> — autenticação social (Google Sign-In).</Li>
        <Li><strong>Stripe, Inc.</strong> — processamento de pagamentos.</Li>
        <Li><strong>Emergent</strong> — infraestrutura de hospedagem e armazenamento de mídia.</Li>
        <Li>Autoridades públicas, mediante ordem judicial ou obrigação legal.</Li>
      </ul>
      <P>Não vendemos, alugamos nem cedemos seus dados para fins publicitários de terceiros.</P>

      <H2>6. Cookies e tecnologias similares</H2>
      <P>
        Utilizamos cookies essenciais (autenticação e sessão) e cookies analíticos anonimizados
        para medir o uso da plataforma. Você pode desabilitá-los nas configurações do navegador,
        ciente de que algumas funcionalidades podem deixar de funcionar corretamente.
      </P>

      <H2>7. Seus direitos (Art. 18 LGPD)</H2>
      <P>Você pode a qualquer momento solicitar:</P>
      <ul className="list-disc pl-6 space-y-2">
        <Li>Confirmação da existência de tratamento e acesso aos seus dados.</Li>
        <Li>Correção de dados incompletos, inexatos ou desatualizados.</Li>
        <Li>Anonimização, bloqueio ou eliminação de dados desnecessários.</Li>
        <Li>Portabilidade dos dados a outro fornecedor.</Li>
        <Li>Eliminação dos dados tratados com base no consentimento.</Li>
        <Li>Revogação do consentimento a qualquer momento.</Li>
      </ul>
      <P>
        Para exercer seus direitos, envie um e-mail para <a href={`mailto:${CONTACT_EMAIL.replace(/\[|\]/g, "")}`} className="text-red-500 hover:underline">{CONTACT_EMAIL}</a> com o assunto "LGPD — Direitos do titular". Responderemos em até 15 dias corridos.
      </P>

      <H2>8. Retenção e segurança</H2>
      <P>
        Retemos seus dados pelo tempo necessário ao cumprimento das finalidades ou de obrigações legais
        (mín. 5 anos para dados fiscais). Adotamos medidas técnicas e administrativas de segurança,
        incluindo criptografia em trânsito (HTTPS/TLS), armazenamento em ambientes com acesso restrito
        e monitoramento contínuo.
      </P>

      <H2>9. Uso por menores</H2>
      <P>
        A plataforma é destinada exclusivamente a maiores de <strong>18 anos</strong>. Não coletamos
        intencionalmente dados de menores. Ao criar conta você declara ter idade legal.
      </P>

      <H2>10. Alterações desta política</H2>
      <P>
        Podemos atualizar esta política periodicamente. A versão vigente estará sempre publicada
        nesta página, com a data da última atualização no topo.
      </P>

      <H2>11. Contato do encarregado (DPO)</H2>
      <P>
        Dúvidas, reclamações ou solicitações: <a href={`mailto:${CONTACT_EMAIL.replace(/\[|\]/g, "")}`} className="text-red-500 hover:underline">{CONTACT_EMAIL}</a>.
      </P>

      <div className="mt-10 pt-6 border-t border-zinc-900 text-xs text-zinc-500 flex items-center justify-between">
        <Link to="/termos" className="hover:text-red-500">Termos de Uso →</Link>
        <Link to="/" className="hover:text-red-500">← Voltar para a home</Link>
      </div>
    </div>
  );
}
