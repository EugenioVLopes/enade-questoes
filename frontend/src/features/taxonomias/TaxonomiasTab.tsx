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

      <div className="flex justify-end">
        <Button
          type="button"
          onClick={() => {
            setTaxonomiaEdit(null);
            setTaxonomiaOpen(true);
          }}
        >
          <Plus className="mr-1.5 h-4 w-4" aria-hidden="true" />
          Nova Taxonomia
        </Button>
      </div>

      {activeTaxonomia ? (
        <Card data-testid="taxonomia-ativa">
          <CardHeader className="gap-2">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-1">
                <CardTitle className="text-xl">{activeTaxonomia.nome}</CardTitle>
                <CardDescription>
                  {activeTaxonomia.codigo}
                  {activeTaxonomia.curso_referencia ? ` · ${activeTaxonomia.curso_referencia}` : ""}
                </CardDescription>
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setTaxonomiaEdit(activeTaxonomia);
                  setTaxonomiaOpen(true);
                }}
              >
                <Pencil className="mr-1.5 h-4 w-4" aria-hidden="true" />
                Editar Taxonomia
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium">Disciplinas</h3>
              <Button
                type="button"
                size="sm"
                onClick={() => {
                  setDisciplinaEdit(null);
                  setDisciplinaOpen(true);
                }}
              >
                <Plus className="mr-1.5 h-4 w-4" aria-hidden="true" />
                Nova Disciplina
              </Button>
            </div>

            {activeTaxonomia.disciplinas.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nenhuma Disciplina cadastrada.</p>
            ) : (
              <ul className="divide-y rounded-md border">
                {activeTaxonomia.disciplinas.map((disciplina) => (
                  <li
                    key={disciplina.id}
                    className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:justify-between"
                    data-testid={`disciplina-${disciplina.id}`}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        {disciplina.nome}
                        {disciplina.ativa ? null : <Badge variant="outline">Arquivada</Badge>}
                      </div>
                      <p className="text-xs text-muted-foreground">{disciplina.codigo}</p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        aria-label={`Editar Disciplina ${disciplina.nome}`}
                        onClick={() => {
                          setDisciplinaEdit(disciplina);
                                  setDisciplinaOpen(true);
                        }}
                      >
                        <Pencil className="mr-1.5 h-4 w-4" aria-hidden="true" />
                        Editar
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        aria-label={`${disciplina.ativa ? "Arquivar" : "Reativar"} Disciplina ${disciplina.nome}`}
                        onClick={() => {
                          setArquivarAlvo(disciplina);
                          setArquivarOpen(true);
                        }}
                      >
                        {disciplina.ativa ? (
                          <Archive className="mr-1.5 h-4 w-4" aria-hidden="true" />
                        ) : (
                          <ArchiveRestore className="mr-1.5 h-4 w-4" aria-hidden="true" />
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
        <p className="text-sm text-muted-foreground">Nenhuma Taxonomia cadastrada.</p>
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
