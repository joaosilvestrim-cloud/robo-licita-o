"use client";
import { Scale, AlertTriangle, HelpCircle, Flag, FileText, MessageSquareReply, Clock, ExternalLink } from "lucide-react";

const ACOES = [
  {
    icon: HelpCircle, cor: "sky",
    nome: "Esclarecimento",
    quando: "Antes de participar, quando algo no edital não estiver claro.",
    oque: "Pergunta formal ao órgão para tirar dúvidas sobre edital, escopo, documentação, prazos ou critérios. Não é uma contestação.",
    prazo: "Até 3 dias úteis antes da data de abertura (art. 164).",
  },
  {
    icon: AlertTriangle, cor: "amber",
    nome: "Impugnação",
    quando: "Se o edital tiver uma exigência irregular, ilegal ou restritiva.",
    oque: "Questiona uma regra do edital considerada ilegal, restritiva ou inadequada. Ex.: exigência técnica excessiva que limita a concorrência.",
    prazo: "Até 3 dias úteis antes da data de abertura (art. 164).",
  },
  {
    icon: Flag, cor: "indigo",
    nome: "Intenção de recurso",
    quando: "Imediatamente após uma decisão desfavorável (julgamento ou habilitação).",
    oque: "Aviso de que você pretende recorrer contra uma decisão. Precisa ser manifestada ainda no prazo da sessão, sob pena de preclusão.",
    prazo: "Na própria sessão, logo após a decisão.",
  },
  {
    icon: FileText, cor: "emerald",
    nome: "Recurso",
    quando: "Para fundamentar sua contestação depois de manifestar a intenção.",
    oque: "Documento com os argumentos e provas para tentar modificar a decisão. Ex.: sua empresa foi inabilitada, mas você entende que apresentou os documentos corretamente.",
    prazo: "3 dias úteis após a intenção (art. 165).",
  },
  {
    icon: MessageSquareReply, cor: "rose",
    nome: "Contrarrazão",
    quando: "Quando outro participante recorre e você quer defender sua posição.",
    oque: "Resposta ao recurso apresentado por outro licitante, normalmente para defender a decisão ou a sua classificação.",
    prazo: "3 dias úteis após o recurso do concorrente (art. 165).",
  },
];

const COR: Record<string, string> = {
  sky: "bg-sky-50 text-sky-700 border-sky-100",
  amber: "bg-amber-50 text-amber-700 border-amber-100",
  indigo: "bg-indigo-50 text-indigo-700 border-indigo-100",
  emerald: "bg-emerald-50 text-emerald-700 border-emerald-100",
  rose: "bg-rose-50 text-rose-700 border-rose-100",
};

export default function JuridicoPage() {
  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Scale size={22} className="text-slate-700" /> Jurídico
        </h1>
        <p className="text-slate-500 text-sm mt-1 max-w-2xl">
          As manifestações que você pode apresentar durante uma licitação, o que é cada uma, quando usar e o prazo.
          Perder o prazo pode impedir o questionamento. Base: <strong>Lei nº 14.133/2021</strong> (impugnações e esclarecimentos no art. 164, recursos no art. 165).
        </p>
      </div>

      <div className="space-y-3">
        {ACOES.map((a, i) => {
          const Icon = a.icon;
          return (
            <div key={i} className="bg-white rounded-2xl border border-slate-100 shadow-card p-5">
              <div className="flex items-center gap-3 mb-2">
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center border ${COR[a.cor]}`}>
                  <Icon size={17} />
                </div>
                <h2 className="text-base font-bold text-slate-900">{i + 1}. {a.nome}</h2>
                <span className="ml-auto inline-flex items-center gap-1 text-xs font-semibold text-slate-500 bg-slate-50 border border-slate-100 px-2 py-1 rounded-full">
                  <Clock size={11} /> {a.prazo}
                </span>
              </div>
              <p className="text-sm text-slate-600 leading-relaxed">{a.oque}</p>
              <p className="text-xs text-slate-400 mt-2"><strong className="text-slate-500">Quando:</strong> {a.quando}</p>
            </div>
          );
        })}
      </div>

      <div className="mt-5 rounded-2xl border border-amber-100 bg-amber-50/60 p-4 flex items-start gap-2">
        <AlertTriangle size={16} className="text-amber-600 shrink-0 mt-0.5" />
        <p className="text-xs text-amber-900 leading-relaxed">
          <strong>Atenção aos prazos.</strong> Cada procedimento tem prazo específico e o edital pode detalhar tempos e regras.
          Ao adicionar uma licitação aos seus <strong>negócios</strong>, o Sonar já cria as tarefas de impugnação, disputa e recurso
          com as datas calculadas a partir da abertura.
        </p>
      </div>

      <p className="text-[11px] text-slate-400 mt-4 flex items-center gap-1">
        <ExternalLink size={11} /> Conteúdo informativo, não substitui a leitura do edital nem parecer jurídico.
      </p>
    </div>
  );
}
