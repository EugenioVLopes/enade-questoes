import { useState, type ReactNode } from "react";
import { Check, ClipboardCopy } from "lucide-react";

import type { DetalheQuestaoResponse } from "@/api/revisao";
import { MarkdownContent } from "@/components/markdown/MarkdownContent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { BadgesAlertaExtracao } from "@/features/revisao/edicao/BadgesAlertaExtracao";
import { GaleriaAtivos } from "@/features/revisao/GaleriaAtivos";
import { montarQuestaoMarkdown, rotuloGabarito } from "@/features/revisao/questaoMarkdown";

export interface QuestaoLeituraProps {
  questao: DetalheQuestaoResponse;
  acoesExtras?: ReactNode;
  onLightboxChange?: (aberto: boolean) => void;
  revisoesAtivos?: Readonly<Record<string, number>>;
  onVerificarAlerta?: (alertaId: string) => void;
  verificandoAlertaId?: string | null;
  erroAlerta?: string | null;
}

export function QuestaoLeitura({
  questao,
  acoesExtras,
  onLightboxChange,
  revisoesAtivos,
  onVerificarAlerta,
  verificandoAlertaId,
  erroAlerta,
}: QuestaoLeituraProps) {
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
    <article
      className="overflow-hidden rounded-lg border border-border bg-card"
      aria-label={`Questão ${questao.numero}`}
    >
      <header className="space-y-3 border-b border-border bg-surface/40 px-5 py-4 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <p className="font-mono text-xs text-muted-foreground">
              {questao.prova.exame} · {questao.prova.curso} · {questao.prova.ano}
            </p>
            <h2 className="text-xl font-semibold tracking-[-0.02em] text-foreground">
              Questão Nº {questao.numero}
            </h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {acoesExtras}
            <Button type="button" variant="outline" size="sm" onClick={() => void copiar()}>
              <ClipboardCopy className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
              Copiar questão em Markdown
            </Button>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Badge
            variant={anulada ? "destructive" : "outline"}
            className={!anulada && correta ? "border-emerald-700/25 bg-emerald-50 font-mono text-emerald-800" : "font-mono"}
          >
            Gabarito: {rotuloGabarito(questao.gabarito)}
          </Badge>
          {questao.editada_manualmente ? <Badge variant="secondary">Editada manualmente</Badge> : null}
        </div>
        <BadgesAlertaExtracao
          alertas={questao.alertas_extracao}
          onVerificarAlerta={onVerificarAlerta}
          verificandoAlertaId={verificandoAlertaId}
          erroAlerta={erroAlerta}
        />
        <p className="text-xs text-muted-foreground empty:hidden" role="status" aria-live="polite">
          {copiada === "ok"
            ? "Questão copiada em Markdown."
            : copiada === "erro"
              ? "Não foi possível copiar para a área de transferência."
              : ""}
        </p>
      </header>

      <div className="space-y-6 px-5 py-5 sm:px-6 sm:py-6">
        <section aria-label="Enunciado" className="max-w-[68ch] space-y-4">
          <MarkdownContent source={questao.enunciado} />
          <GaleriaAtivos
            ativos={ativosEnunciado}
            rotulo="Ativo Visual do enunciado"
            revisoesAtivos={revisoesAtivos}
            onAbertoChange={onLightboxChange}
          />
        </section>

        {questao.alternativas.length > 0 ? (
          <section aria-label="Alternativas" className="space-y-2.5 border-t border-border/70 pt-5">
            <h3 className="text-xs font-semibold text-muted-foreground">Alternativas</h3>
            <ol className="space-y-2.5">
              {questao.alternativas.map((alternativa) => {
                const ehCorreta = correta === alternativa.letra;
                const ativos = questao.ativos_visuais.filter((ativo) => ativo.alternativa_letra === alternativa.letra);
                return (
                  <li
                    key={alternativa.letra}
                    data-correta={ehCorreta ? "true" : undefined}
                    className={cn(
                      "flex items-start gap-3 rounded-md border p-3.5 transition-colors",
                      ehCorreta
                        ? "border-emerald-700/35 bg-emerald-50/75"
                        : "border-border bg-background/55",
                    )}
                  >
                    <span
                      className={cn(
                        "mt-0.5 inline-flex h-6 min-w-6 shrink-0 items-center justify-center rounded-sm border font-mono text-xs font-semibold",
                        ehCorreta
                          ? "border-emerald-700/35 bg-emerald-700 text-white"
                          : "border-border bg-card text-foreground",
                      )}
                    >
                      {alternativa.letra})
                    </span>
                    <div className="min-w-0 flex-1 space-y-2">
                      <MarkdownContent source={alternativa.texto} />
                      <GaleriaAtivos
                        ativos={ativos}
                        rotulo={`Ativo Visual da alternativa ${alternativa.letra}`}
                        revisoesAtivos={revisoesAtivos}
                        onAbertoChange={onLightboxChange}
                      />
                      {ehCorreta ? <span className="sr-only">Alternativa correta</span> : null}
                    </div>
                    {ehCorreta ? (
                      <Check className="mt-1 h-4 w-4 shrink-0 text-emerald-700" aria-hidden="true" />
                    ) : null}
                  </li>
                );
              })}
            </ol>
          </section>
        ) : null}
      </div>
    </article>
  );
}
