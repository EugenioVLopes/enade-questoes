import { useEffect, useState } from "react";
import { AlertCircle, Plus } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { getErrorMessage, type ConflitoProvaResponse } from "@/api/errors";
import {
  useProvasQuery,
  useReprocessarProvaMutation,
  type ProvaDetalheResponse,
} from "@/api/provas";
import { useTaxonomia } from "@/components/layout/useTaxonomia";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AtualizarGabaritoDialog,
  type GabaritoTargetProva,
} from "@/features/provas/AtualizarGabaritoDialog";
import { IngestaoFormDialog } from "@/features/provas/IngestaoFormDialog";
import { ProvaCard } from "@/features/provas/ProvaCard";
import {
  ReprocessarProvaDialog,
  type ReprocessarTargetProva,
} from "@/features/provas/ReprocessarProvaDialog";

export function ProvasPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { activeTaxonomiaId, taxonomias } = useTaxonomia();
  const provasQuery = useProvasQuery();
  const retryMutation = useReprocessarProvaMutation();

  const [ingestaoOpen, setIngestaoOpen] = useState(false);
  const [gabaritoTarget, setGabaritoTarget] = useState<GabaritoTargetProva | null>(null);
  const [reprocessarTarget, setReprocessarTarget] = useState<ReprocessarTargetProva | null>(null);
  const [retryingProvaId, setRetryingProvaId] = useState<string | null>(null);
  const [retryError, setRetryError] = useState<string | null>(null);

  useEffect(() => {
    if (searchParams.get("acao") === "ingerir") {
      setIngestaoOpen(true);
      const nextParams = new URLSearchParams(searchParams);
      nextParams.delete("acao");
      setSearchParams(nextParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const provas = provasQuery.data?.itens ?? [];

  function handleOpenAtualizarGabarito(prova: ProvaDetalheResponse) {
    setGabaritoTarget({
      id: prova.id,
      exame: prova.exame,
      curso: prova.curso,
      ano: prova.ano,
    });
  }

  function handleOpenReprocessar(prova: ProvaDetalheResponse) {
    setReprocessarTarget({
      id: prova.id,
      exame: prova.exame,
      curso: prova.curso,
      ano: prova.ano,
      editadasManualmente: prova.questoes.editadas_manualmente,
    });
  }

  function handleConflictAtualizarGabarito(conflito: ConflitoProvaResponse) {
    const found = provas.find((item) => item.id === conflito.prova_id);
    setIngestaoOpen(false);
    setGabaritoTarget(
      found
        ? {
            id: found.id,
            exame: found.exame,
            curso: found.curso,
            ano: found.ano,
          }
        : {
            id: conflito.prova_id,
            exame: conflito.exame,
            curso: conflito.curso,
            ano: conflito.ano,
          },
    );
  }

  function handleConflictReprocessarProva(conflito: ConflitoProvaResponse) {
    const found = provas.find((item) => item.id === conflito.prova_id);
    setIngestaoOpen(false);
    setReprocessarTarget(
      found
        ? {
            id: found.id,
            exame: found.exame,
            curso: found.curso,
            ano: found.ano,
            editadasManualmente: found.questoes.editadas_manualmente,
          }
        : {
            id: conflito.prova_id,
            exame: conflito.exame,
            curso: conflito.curso,
            ano: conflito.ano,
            editadasManualmente: null,
          },
    );
  }

  async function handleTentarNovamente(prova: ProvaDetalheResponse) {
    setRetryError(null);
    setRetryingProvaId(prova.id);
    try {
      await retryMutation.mutateAsync({
        provaId: prova.id,
        sobrescrever_editadas: false,
      });
    } catch (error) {
      setRetryError(getErrorMessage(error, "Não foi possível reiniciar a Ingestão da Prova."));
    } finally {
      setRetryingProvaId((current) => (current === prova.id ? null : current));
    }
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">Provas</h1>
          <p className="text-sm text-muted-foreground">
            Acompanhe Ingestões, extração de Questões, atualização de Gabarito e reprocessamento.
          </p>
        </div>

        {provas.length > 0 ? (
          <Button type="button" onClick={() => setIngestaoOpen(true)}>
            <Plus className="mr-1.5 h-4 w-4" aria-hidden="true" />
            Nova Ingestão
          </Button>
        ) : null}
      </div>

      {retryError ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Falha ao tentar novamente</AlertTitle>
          <AlertDescription>{retryError}</AlertDescription>
        </Alert>
      ) : null}

      {provasQuery.isLoading ? (
        <div className="space-y-4" aria-label="Carregando Provas">
          <Skeleton className="h-48 w-full rounded-lg" />
          <Skeleton className="h-48 w-full rounded-lg" />
        </div>
      ) : provasQuery.isError ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Não foi possível carregar as Provas</AlertTitle>
          <AlertDescription className="space-y-3">
            <p>{getErrorMessage(provasQuery.error)}</p>
            <Button type="button" variant="outline" size="sm" onClick={() => void provasQuery.refetch()}>
              Tentar novamente
            </Button>
          </AlertDescription>
        </Alert>
      ) : provas.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Nenhuma Prova ingerida ainda</CardTitle>
            <CardDescription>
              Comece realizando a primeira Ingestão de uma Prova e, opcionalmente, de seu Gabarito.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button type="button" onClick={() => setIngestaoOpen(true)}>
              Ingerir primeira prova
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {provas.map((prova) => (
            <ProvaCard
              key={prova.id}
              prova={prova}
              activeTaxonomiaId={activeTaxonomiaId}
              taxonomias={taxonomias}
              onAtualizarGabarito={handleOpenAtualizarGabarito}
              onReprocessar={handleOpenReprocessar}
              onTentarNovamente={(item) => void handleTentarNovamente(item)}
              isRetrying={retryingProvaId === prova.id && retryMutation.isPending}
            />
          ))}
        </div>
      )}

      <IngestaoFormDialog
        open={ingestaoOpen}
        onOpenChange={setIngestaoOpen}
        onSelectAtualizarGabarito={handleConflictAtualizarGabarito}
        onSelectReprocessarProva={handleConflictReprocessarProva}
      />

      <AtualizarGabaritoDialog
        open={gabaritoTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setGabaritoTarget(null);
          }
        }}
        prova={gabaritoTarget}
      />

      <ReprocessarProvaDialog
        open={reprocessarTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setReprocessarTarget(null);
          }
        }}
        target={reprocessarTarget}
      />
    </section>
  );
}
