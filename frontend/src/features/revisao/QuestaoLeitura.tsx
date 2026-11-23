import { useState, type ReactNode } from "react";
import { AlertTriangle, Check, ClipboardCopy, Info } from "lucide-react";

import type { AlertaExtracaoResponse, DetalheQuestaoResponse } from "@/api/revisao";
import { MarkdownContent } from "@/components/markdown/MarkdownContent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { GaleriaAtivos } from "@/features/revisao/GaleriaAtivos";
import { montarQuestaoMarkdown, rotuloGabarito } from "@/features/revisao/questaoMarkdown";

const ROTULOS_ALERTA: Record<AlertaExtracaoResponse["codigo"], string> = {
  formula_nao_decodificada: "Fórmula não decodificada",
  alternativas_incompletas: "Alternativas incompletas",
  pdf_via_ocr: "PDF lido via OCR",
  enunciado_suspeito: "Enunciado suspeito",
  fonte_symbol_detectada: "Fonte Symbol detectada",
  gabarito_ausente_na_prova: "Gabarito ausente na Prova",
};

export interface QuestaoLeituraProps {
  questao: DetalheQuestaoResponse;
  /** Ponto de encaixe da Tarefa 13 ("Editar conteúdo", "Ver página do PDF"). */
  acoesExtras?: ReactNode;
  onLightboxChange?: (aberto: boolean) => void;
}

function BadgesAlerta({ alertas }: { alertas: readonly AlertaExtracaoResponse[] }) {
  const abertos = alertas.filter((alerta) => alerta.status === "aberto");
  if (abertos.length === 0) {
    return null;
  }
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Alertas de Extração">
      {abertos.map((alerta) => {
        const critico = alerta.severidade === "critico";
        return (
          <li key={alerta.id}>
            <Badge
              variant={critico ? "destructive" : "outline"}
              className="gap-1"
              title={alerta.mensagem}
              data-severidade={alerta.severidade}
            >
              {critico ? <AlertTriangle className="h-3 w-3" aria-hidden="true" /> : <Info className="h-3 w-3" aria-hidden="true" />}
              <span className="sr-only">{critico ? "Alerta crítico: " : "Alerta informativo: "}</span>
              {ROTULOS_ALERTA[alerta.codigo] ?? alerta.codigo}
            </Badge>
          </li>
        );
      })}
    </ul>
  );
}

export function QuestaoLeitura({ questao, acoesExtras, onLightboxChange }: QuestaoLeituraProps) {
  const [copiada, setCopiada] = useState<"ok" | "erro" | null>(null);
  const ativosEnunciado = questao.ativos_visuais.filter((ativo) => !ativo.alternativa_letra);
  const correta = questao.gabarito.situacao_gabarito === "valida" ? questao.gabarito.alternativa_correta : null;
  const anulada = questao.gabarito.situacao_gabarito === "anulada";

  async function copiar() {
    try {
      await navigator.clipboard.writeText(montarQuestaoMarkdown(questao));
      setCopiada("ok");
    } catch {
      setCopiada("erro");
    }
  }

  return (
    <article className="space-y-5" aria-label={`Questão ${questao.numero}`}>
      <header className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="text-sm text-muted-foreground">
              {questao.prova.exame} · {questao.prova.curso} · {questao.prova.ano}
            </p>
            <h2 className="text-xl font-semibold tracking-tight">Questão Nº {questao.numero}</h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {acoesExtras}
            <Button type="button" variant="outline" size="sm" onClick={() => void copiar()}>
              <ClipboardCopy className="mr-1 h-4 w-4" aria-hidden="true" />
              Copiar questão em Markdown
            </Button>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Badge variant={anulada ? "destructive" : "outline"}>Gabarito: {rotuloGabarito(questao.gabarito)}</Badge>
          {questao.editada_manualmente ? <Badge variant="secondary">Editada manualmente</Badge> : null}
        </div>
        <BadgesAlerta alertas={questao.alertas_extracao} />
        <p className="text-xs text-muted-foreground" role="status" aria-live="polite">
          {copiada === "ok" ? "Questão copiada em Markdown." : copiada === "erro" ? "Não foi possível copiar para a área de transferência." : ""}
        </p>
      </header>

      <section aria-label="Enunciado" className="space-y-3">
        <MarkdownContent source={questao.enunciado} />
        <GaleriaAtivos ativos={ativosEnunciado} rotulo="Ativo Visual do enunciado" onAbertoChange={onLightboxChange} />
      </section>

      <section aria-label="Alternativas" className="space-y-2">
        <ol className="space-y-2">
          {questao.alternativas.map((alternativa) => {
            const ehCorreta = correta === alternativa.letra;
            const ativos = questao.ativos_visuais.filter((ativo) => ativo.alternativa_letra === alternativa.letra);
            return (
              <li
                key={alternativa.letra}
                data-correta={ehCorreta ? "true" : undefined}
                className={cn(
                  "flex gap-3 rounded-md border p-3",
                  ehCorreta && "border-emerald-500/50 bg-emerald-500/10",
                )}
              >
                <span className="font-semibold">{alternativa.letra})</span>
                <div className="min-w-0 flex-1 space-y-2">
                  <MarkdownContent source={alternativa.texto} />
                  <GaleriaAtivos
                    ativos={ativos}
                    rotulo={`Ativo Visual da alternativa ${alternativa.letra}`}
                    onAbertoChange={onLightboxChange}
                  />
                  {ehCorreta ? (
                    <span className="sr-only">Alternativa correta</span>
                  ) : null}
                </div>
                {ehCorreta ? <Check className="h-4 w-4 shrink-0 text-emerald-600" aria-hidden="true" /> : null}
              </li>
            );
          })}
        </ol>
      </section>
    </article>
  );
}
