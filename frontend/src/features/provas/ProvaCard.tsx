import { AlertTriangle, CheckCircle2, FileCheck2, Loader2, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";

import { isIngestaoAtiva, type ProvaDetalheResponse } from "@/api/provas";
import type { TaxonomiaResponse } from "@/api/taxonomias";
import { buildRevisaoProvaHref } from "@/components/layout/useTaxonomia";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatarFaixaCE } from "@/features/provas/faixasEnade";
import {
  formatarDataHora,
  getClassificacaoEncadeadaBadgeMeta,
  getIngestaoStatusMeta,
} from "@/features/provas/provasStatus";

export interface ProvaCardProps {
  prova: ProvaDetalheResponse;
  activeTaxonomiaId: string | null;
  taxonomias: readonly TaxonomiaResponse[];
  onAtualizarGabarito: (prova: ProvaDetalheResponse) => void;
  onReprocessar: (prova: ProvaDetalheResponse) => void;
  onTentarNovamente: (prova: ProvaDetalheResponse) => void;
  isRetrying?: boolean;
}

export function ProvaCard({
  prova,
  activeTaxonomiaId,
  taxonomias,
  onAtualizarGabarito,
  onReprocessar,
  onTentarNovamente,
  isRetrying = false,
}: ProvaCardProps) {
  const statusIngestao = prova.ultima_ingestao?.status ?? null;
  const ingestaoAtiva = isIngestaoAtiva(statusIngestao);
  const podeTentarNovamente = statusIngestao === "erro" || statusIngestao === "interrompida";

  const ingestaoMeta = getIngestaoStatusMeta(statusIngestao);
  const classificacaoMeta = getClassificacaoEncadeadaBadgeMeta(prova.classificacao_encadeada);

  const taxonomiaEncadeada = prova.classificacao_encadeada.taxonomia_id
    ? taxonomias.find((item) => item.id === prova.classificacao_encadeada.taxonomia_id)
    : undefined;

  const revisaoHref = buildRevisaoProvaHref(prova.id, activeTaxonomiaId);
  const podeRevisar = !ingestaoAtiva && prova.questoes.total > 0;
  const concluidaEm = formatarDataHora(prova.ultima_ingestao?.concluida_em);
  const metadados = prova.ultima_ingestao?.metadados;

  return (
    <Card data-testid={`prova-card-${prova.id}`}>
      <CardHeader className="gap-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <CardTitle className="text-xl">
              {prova.exame} {prova.ano}
            </CardTitle>
            <CardDescription>
              {prova.curso} · Questões CE {formatarFaixaCE(prova.questao_inicio, prova.questao_fim)}
            </CardDescription>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={ingestaoMeta.variant} className={ingestaoMeta.className}>
              {ingestaoMeta.isActive ? (
                <Loader2 className="mr-1.5 h-3 w-3 animate-spin" aria-hidden="true" />
              ) : null}
              <span>{ingestaoMeta.label}</span>
            </Badge>

            <Badge
              variant={prova.possui_gabarito ? "outline" : "secondary"}
              className={
                prova.possui_gabarito
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                  : undefined
              }
            >
              {prova.possui_gabarito ? (
                <CheckCircle2 className="mr-1.5 h-3 w-3" aria-hidden="true" />
              ) : null}
              <span>{prova.possui_gabarito ? "Possui Gabarito" : "Gabarito pendente"}</span>
            </Badge>

            {classificacaoMeta ? (
              <Badge variant={classificacaoMeta.variant} className={classificacaoMeta.className}>
                {classificacaoMeta.isActive ? (
                  <Loader2 className="mr-1.5 h-3 w-3 animate-spin" aria-hidden="true" />
                ) : null}
                <span>
                  {classificacaoMeta.label}
                  {taxonomiaEncadeada ? ` · ${taxonomiaEncadeada.nome}` : ""}
                </span>
              </Badge>
            ) : null}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="rounded-md border bg-muted/30 p-3">
            <p className="text-xs font-medium text-muted-foreground">Questões extraídas</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{prova.questoes.total}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {prova.questoes.gabarito_validas} válidas · {prova.questoes.gabarito_anuladas} anuladas
              {" · "}
              {prova.questoes.gabarito_pendentes} pendentes
            </p>
            {prova.questoes.editadas_manualmente > 0 ? (
              <p className="mt-1 text-xs font-medium text-foreground">
                {prova.questoes.editadas_manualmente} editadas manualmente
              </p>
            ) : (
              <p className="mt-1 text-xs text-muted-foreground">0 editadas manualmente</p>
            )}
          </div>

          <div className="rounded-md border bg-muted/30 p-3">
            <p className="text-xs font-medium text-muted-foreground">Alertas de Extração abertos</p>
            <p className="mt-1 flex items-center gap-1.5 text-2xl font-semibold tabular-nums">
              <span>{prova.alertas.abertos}</span>
              {prova.alertas.criticos_abertos > 0 ? (
                <AlertTriangle className="h-4 w-4 text-destructive" aria-hidden="true" />
              ) : null}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {prova.alertas.criticos_abertos} críticos ·{" "}
              {prova.alertas.questoes_com_alerta_aberto} questões com alerta
            </p>
          </div>

          <div className="rounded-md border bg-muted/30 p-3 sm:col-span-2 lg:col-span-1">
            <p className="text-xs font-medium text-muted-foreground">Resumo da Ingestão</p>
            {metadados ? (
              <div className="mt-1 space-y-1 text-xs text-muted-foreground">
                <p className="text-foreground">
                  {metadados.imagens_detectadas} Ativos Visuais detectados ·{" "}
                  {metadados.formulas_recortadas} fórmulas recortadas
                </p>
                <p>
                  {metadados.usou_ocr ? "Extração com OCR" : "Extração nativa"}
                  {metadados.paginas_fonte_symbol.length > 0
                    ? ` · Fonte Symbol em ${metadados.paginas_fonte_symbol.length} página(s)`
                    : ""}
                </p>
                {concluidaEm ? <p>Concluída em {concluidaEm}</p> : null}
              </div>
            ) : (
              <p className="mt-1 text-xs text-muted-foreground">
                Aguardando início da Ingestão.
              </p>
            )}
          </div>
        </div>

        {prova.ultima_ingestao?.mensagem_erro ? (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Falha na Ingestão</AlertTitle>
            <AlertDescription>{prova.ultima_ingestao.mensagem_erro}</AlertDescription>
          </Alert>
        ) : null}
      </CardContent>

      <CardFooter className="flex flex-wrap items-center justify-between gap-2 border-t pt-4">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={ingestaoAtiva}
            onClick={() => onAtualizarGabarito(prova)}
          >
            <FileCheck2 className="mr-1.5 h-4 w-4" aria-hidden="true" />
            Atualizar Gabarito
          </Button>

          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={ingestaoAtiva}
            onClick={() => onReprocessar(prova)}
          >
            <RefreshCw className="mr-1.5 h-4 w-4" aria-hidden="true" />
            Reprocessar Prova
          </Button>

          {podeTentarNovamente ? (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={ingestaoAtiva || isRetrying}
              onClick={() => onTentarNovamente(prova)}
            >
              {isRetrying ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <RefreshCw className="mr-1.5 h-4 w-4" aria-hidden="true" />
              )}
              Tentar novamente
            </Button>
          ) : null}
        </div>

        {podeRevisar ? (
          <Button asChild size="sm">
            <Link to={revisaoHref}>Revisar questões desta prova</Link>
          </Button>
        ) : (
          <Button type="button" size="sm" disabled>
            Revisar questões desta prova
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
