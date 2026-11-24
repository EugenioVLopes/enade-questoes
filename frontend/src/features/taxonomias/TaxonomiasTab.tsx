import { useState } from "react";
import { AlertCircle, Archive, ArchiveRestore, Pencil, Plus } from "lucide-react";

import { getErrorMessage } from "@/api/errors";
import type { DisciplinaResponse, TaxonomiaResponse } from "@/api/taxonomias";
import { useTaxonomia } from "@/components/layout/useTaxonomia";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ArquivarDisciplinaDialog } from "@/features/taxonomias/ArquivarDisciplinaDialog";
import { DisciplinaFormDialog } from "@/features/taxonomias/DisciplinaFormDialog";
import { TaxonomiaFormDialog } from "@/features/taxonomias/TaxonomiaFormDialog";

export function TaxonomiasTab() {
  const { taxonomias, activeTaxonomia, isLoading, error } = useTaxonomia();

  const [taxonomiaOpen, setTaxonomiaOpen] = useState(false);
  const [taxonomiaEdit, setTaxonomiaEdit] = useState<TaxonomiaResponse | null>(null);
  const [disciplinaOpen, setDisciplinaOpen] = useState(false);
  const [disciplinaEdit, setDisciplinaEdit] = useState<DisciplinaResponse | null>(null);
  const [arquivarOpen, setArquivarOpen] = useState(false);
  const [arquivarAlvo, setArquivarAlvo] = useState<DisciplinaResponse | null>(null);

  // Ao trocar a Taxonomia ativa os diálogos de Disciplina fecham: o alvo (editar/arquivar)
  // pertence à Taxonomia anterior e o PATCH nunca deve ir para ela por engano.
  const activeId = activeTaxonomia?.id ?? null;
  const [taxonomiaVista, setTaxonomiaVista] = useState(activeId);
  if (taxonomiaVista !== activeId) {
    setTaxonomiaVista(activeId);
    setDisciplinaOpen(false);
    setArquivarOpen(false);
  }

  if (isLoading) {
    return <Skeleton className="h-32 w-full" aria-label="Carregando taxonomias" />;
  }

  return (
    <div className="space-y-6">
      {error && taxonomias.length === 0 ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Falha ao carregar Taxonomias</AlertTitle>
          <AlertDescription>
            {getErrorMessage(error, "Não foi possível listar as Taxonomias.")}
          </AlertDescription>
        </Alert>
      ) : null}

      {activeTaxonomia ? (
        <Card data-testid="taxonomia-ativa" className="overflow-hidden">
          <CardHeader className="gap-2 border-b border-border bg-surface/35 pb-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-1.5">
                <CardTitle className="text-xl tracking-[-0.02em]">{activeTaxonomia.nome}</CardTitle>
                <CardDescription className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-sm border border-border bg-card px-1.5 py-0.5 font-mono text-[11px] font-medium text-foreground">
                    {activeTaxonomia.codigo}
                  </span>
                  {activeTaxonomia.curso_referencia ? (
                    <span className="text-muted-foreground">· {activeTaxonomia.curso_referencia}</span>
                  ) : null}
                </CardDescription>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground hover:text-foreground"
                  onClick={() => {
                    setTaxonomiaEdit(activeTaxonomia);
                    setTaxonomiaOpen(true);
                  }}
                >
                  <Pencil className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                  Editar Taxonomia
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setTaxonomiaEdit(null);
                    setTaxonomiaOpen(true);
                  }}
                >
                  <Plus className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                  Nova Taxonomia
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3.5 pt-5">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-foreground">
                Disciplinas{" "}
                <span className="ml-1 font-mono text-xs font-normal text-muted-foreground">
                  ({activeTaxonomia.disciplinas.length})
                </span>
              </h3>
              <Button
                type="button"
                size="sm"
                onClick={() => {
                  setDisciplinaEdit(null);
                  setDisciplinaOpen(true);
                }}
              >
                <Plus className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                Nova Disciplina
              </Button>
            </div>

            {activeTaxonomia.disciplinas.length === 0 ? (
              <p className="rounded-md border border-dashed border-border bg-surface/40 px-4 py-6 text-center text-sm text-muted-foreground">
                Nenhuma Disciplina cadastrada.
              </p>
            ) : (
              <ul className="divide-y divide-border rounded-md border border-border">
                {activeTaxonomia.disciplinas.map((disciplina) => (
                  <li
                    key={disciplina.id}
                    className="flex flex-col gap-2 px-4 py-2.5 transition-colors hover:bg-surface/40 sm:flex-row sm:items-center sm:justify-between"
                    data-testid={`disciplina-${disciplina.id}`}
                  >
                    <div className="min-w-0 space-y-0.5">
                      <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
                        <span>{disciplina.nome}</span>
                        {disciplina.ativa ? null : <Badge variant="outline">Arquivada</Badge>}
                      </div>
                      <p className="font-mono text-xs text-muted-foreground">{disciplina.codigo}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="text-muted-foreground hover:text-foreground"
                        aria-label={`Editar Disciplina ${disciplina.nome}`}
                        onClick={() => {
                          setDisciplinaEdit(disciplina);
                          setDisciplinaOpen(true);
                        }}
                      >
                        <Pencil className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                        Editar
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="text-muted-foreground hover:text-foreground"
                        aria-label={`${disciplina.ativa ? "Arquivar" : "Reativar"} Disciplina ${disciplina.nome}`}
                        onClick={() => {
                          setArquivarAlvo(disciplina);
                          setArquivarOpen(true);
                        }}
                      >
                        {disciplina.ativa ? (
                          <Archive className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                        ) : (
                          <ArchiveRestore className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                        )}
                        {disciplina.ativa ? "Arquivar" : "Reativar"}
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      ) : !error ? (
        <div className="flex flex-col items-start gap-3 rounded-md border border-dashed border-border bg-card p-6">
          <p className="text-sm text-muted-foreground">Nenhuma Taxonomia cadastrada.</p>
          <Button
            type="button"
            size="sm"
            onClick={() => {
              setTaxonomiaEdit(null);
              setTaxonomiaOpen(true);
            }}
          >
            <Plus className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
            Nova Taxonomia
          </Button>
        </div>
      ) : null}

      <TaxonomiaFormDialog
        open={taxonomiaOpen}
        onOpenChange={setTaxonomiaOpen}
        taxonomia={taxonomiaEdit}
      />
      {activeTaxonomia ? (
        <DisciplinaFormDialog
          open={disciplinaOpen}
          onOpenChange={setDisciplinaOpen}
          taxonomiaId={activeTaxonomia.id}
          disciplina={disciplinaEdit}
        />
      ) : null}
      <ArquivarDisciplinaDialog
        open={arquivarOpen}
        onOpenChange={setArquivarOpen}
        disciplina={arquivarAlvo}
      />
    </div>
  );
}
