import { Link } from "react-router-dom";

// Terms of Use for Prime Encontros — professional massage marketplace (Rio de Janeiro).
// EDITE OS PLACEHOLDERS entre [colchetes] antes de publicar.
const CONTACT_EMAIL = "[contato@primeencontros.com.br]";
const CONTROLLER = "[Nome/Razão social do responsável]";
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

export default function Terms() {
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14" data-testid="terms-page">
      <div className="mb-6 text-xs uppercase tracking-[0.2em] text-red-500 font-semibold">Documento legal</div>
      <h1 className="font-display text-3xl sm:text-4xl text-zinc-50 mb-2">Termos de Uso</h1>
      <div className="text-xs text-zinc-500 mb-8">Última atualização: {UPDATED_AT}</div>

      <P>
        Bem-vindo(a) ao <strong>Prime Encontros</strong>. Estes Termos de Uso ("Termos") regem o uso
        da nossa plataforma, que conecta usuários a massoterapeutas independentes ("Profissionais")
        para agendamento de serviços de <strong>massagem terapêutica e de bem-estar</strong>.
      </P>
      <P>
        Ao criar conta, acessar ou usar o serviço, você concorda integralmente com estes Termos.
        Se não concordar, não utilize a plataforma.
      </P>

      <H2>1. Sobre o serviço</H2>
      <P>
        O Prime Encontros é uma <strong>plataforma de intermediação</strong> entre clientes e
        Profissionais autônomas de massagem terapêutica. Não somos empregadores das Profissionais,
        nem prestamos diretamente os serviços listados. A responsabilidade técnica pela execução
        do atendimento é exclusiva da Profissional contratada.
      </P>

      <H2>2. Elegibilidade</H2>
      <ul className="list-disc pl-6 space-y-2">
        <Li>Você deve ter <strong>no mínimo 18 anos completos</strong> e capacidade civil plena.</Li>
        <Li>Fornecer informações verdadeiras, atualizadas e completas no cadastro.</Li>
        <Li>Utilizar a plataforma apenas para fins lícitos e conforme estes Termos.</Li>
      </ul>

      <H2>3. Cadastro e conta</H2>
      <P>
        Sua conta é pessoal e intransferível. Você é responsável por manter a confidencialidade das
        credenciais de acesso e por todas as atividades realizadas em sua conta. Notifique-nos
        imediatamente em caso de uso não autorizado.
      </P>

      <H2>4. Regras para Profissionais</H2>
      <ul className="list-disc pl-6 space-y-2">
        <Li>Enviar apenas fotos suas, com aparência profissional, sem nudez explícita.</Li>
        <Li>Manter documentação e registros exigidos por lei em sua atividade.</Li>
        <Li>Cumprir os agendamentos confirmados. Cancelamentos devem ser comunicados com antecedência mínima de 4 horas.</Li>
        <Li>Prestar o serviço com técnica, ética e higiene adequados.</Li>
        <Li>Respeitar limites do cliente e recusar qualquer pedido que fuja do serviço de massagem terapêutica contratada.</Li>
      </ul>

      <H2>5. Regras para clientes</H2>
      <ul className="list-disc pl-6 space-y-2">
        <Li>Comparecer no horário reservado. Atrasos superiores a 15 minutos podem gerar cancelamento sem reembolso.</Li>
        <Li>Respeitar a Profissional, sua integridade física e o escopo do serviço contratado (massagem terapêutica).</Li>
        <Li>Fornecer endereço e informações corretas para atendimento a domicílio, quando aplicável.</Li>
        <Li>Efetuar o pagamento por meio da plataforma (Stripe) ou conforme combinado diretamente com a Profissional.</Li>
      </ul>

      <H2>6. Conteúdo proibido</H2>
      <P>É expressamente vedado o uso da plataforma para:</P>
      <ul className="list-disc pl-6 space-y-2">
        <Li>Oferta, solicitação ou prática de <strong>serviços sexuais de qualquer natureza</strong>.</Li>
        <Li>Publicação de fotos com nudez explícita, pornografia ou conteúdo obsceno.</Li>
        <Li>Assédio, discurso de ódio, discriminação ou ameaça a qualquer pessoa.</Li>
        <Li>Fraudes, falsificação de identidade ou uso indevido de dados de terceiros.</Li>
        <Li>Qualquer atividade ilícita conforme legislação brasileira.</Li>
      </ul>
      <P>
        O descumprimento resultará em <strong>suspensão imediata e permanente</strong> da conta,
        sem prejuízo das medidas legais cabíveis.
      </P>

      <H2>7. Pagamentos, taxas e reembolsos</H2>
      <ul className="list-disc pl-6 space-y-2">
        <Li>Os pagamentos são processados pela Stripe. O Prime Encontros não armazena dados de cartão.</Li>
        <Li>Podemos reter uma <strong>taxa de intermediação</strong> por reserva concluída, informada antes da confirmação.</Li>
        <Li>Cancelamentos feitos com mais de <strong>4 horas de antecedência</strong> são reembolsados integralmente.</Li>
        <Li>Cancelamentos abaixo de 4 horas ou "no-show" não geram reembolso.</Li>
        <Li>Disputas devem ser abertas em até 7 dias corridos após o atendimento, via <a href={`mailto:${CONTACT_EMAIL.replace(/\[|\]/g, "")}`} className="text-red-500 hover:underline">{CONTACT_EMAIL}</a>.</Li>
      </ul>

      <H2>8. Avaliações</H2>
      <P>
        Após um atendimento confirmado, o cliente pode registrar avaliação e comentário sobre a
        Profissional. Reservamo-nos o direito de moderar ou remover conteúdo que viole estes
        Termos ou nossas diretrizes de comunidade.
      </P>

      <H2>9. Propriedade intelectual</H2>
      <P>
        Todos os direitos sobre a marca, logotipo, layout e código da plataforma pertencem ao
        Prime Encontros. As Profissionais mantêm a titularidade das fotos e vídeos enviados,
        concedendo licença não-exclusiva de exibição na plataforma e em materiais de divulgação.
      </P>

      <H2>10. Limitação de responsabilidade</H2>
      <P>
        O Prime Encontros atua como intermediário. Não nos responsabilizamos por danos decorrentes
        de atos ou omissões dos usuários e Profissionais. Nosso limite total de responsabilidade,
        em qualquer hipótese, fica restrito ao valor da reserva questionada.
      </P>

      <H2>11. Suspensão e encerramento</H2>
      <P>
        Podemos suspender ou encerrar contas, a qualquer momento e sem aviso prévio, quando houver
        indício de violação destes Termos, fraude ou risco à segurança da plataforma ou de terceiros.
      </P>

      <H2>12. Alterações destes Termos</H2>
      <P>
        Reservamo-nos o direito de alterar estes Termos periodicamente. A continuidade do uso
        após a publicação da nova versão implica aceitação das mudanças.
      </P>

      <H2>13. Lei aplicável e foro</H2>
      <P>
        Estes Termos são regidos pelas leis da República Federativa do Brasil. Fica eleito o foro
        da Comarca de <strong>{LOCATION}</strong> para dirimir qualquer controvérsia,
        renunciando-se a qualquer outro por mais privilegiado que seja.
      </P>

      <H2>14. Contato</H2>
      <P>
        Dúvidas ou reclamações: <a href={`mailto:${CONTACT_EMAIL.replace(/\[|\]/g, "")}`} className="text-red-500 hover:underline">{CONTACT_EMAIL}</a><br />
        Controlador: <strong>{CONTROLLER}</strong>
      </P>

      <div className="mt-10 pt-6 border-t border-zinc-900 text-xs text-zinc-500 flex items-center justify-between">
        <Link to="/privacidade" className="hover:text-red-500">Política de Privacidade →</Link>
        <Link to="/" className="hover:text-red-500">← Voltar para a home</Link>
      </div>
    </div>
  );
}
