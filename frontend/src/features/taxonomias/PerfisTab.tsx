import { useState } from "react";
import { AlertCircle, GitBranchPlus } from "lucide-react";

import { getErrorMessage } from "@/api/errors";
import { usePerfisClassificacaoQuery, type PerfilClassificacaoResponse } from "@/api/taxonomias";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { NovaVersaoPerfilDialog } from "@/features/taxonomias/NovaVersaoPerfilDialog";

function Texto({ titulo, valor }: { titulo: string; valor: string }) {
  return (
    <div className="space-y-1">
      <h4 className="text-sm font-medium">{titulo}</h4>
      <p className="whitespace-pre-wrap text-sm text-muted-foreground">{valor || "—"}</p>
    </div>
  );
}

export function PerfisTab() {
  const perfisQuery = usePerfisClassificacaoQuery();
  const [base, setBase] = useState<PerfilClassificacaoResponse | null>(null);
  const [open, setOpen] = useState(false);

  const perfis = perfisQuery.data?.itens ?? [];

  if (perfisQuery.isLoading) {
    return <Skeleton className="h-32 w-full" aria-label="Carregando perfis" />;
  }

  if (perfisQuery.error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Falha ao carregar Perfis</AlertTitle>
        <AlertDescription>
          {getErrorMessage(perfisQuery.error, "Não foi possível listar os Perfis.")}
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      {perfis.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhum Perfil de Classificação cadastrado.</p>
      ) : null}

      {perfis.map((perfil) => (
        <Card key={perfil.id} data-testid={`perfil-card-${perfil.id}`}>
          <CardHeader className="gap-2">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-1">
                <CardTitle className="text-xl">
                  {perfil.codigo} · {perfil.versao}
                </CardTitle>
                {perfil.descricao ? <CardDescription>{perfil.descricao}</CardDescription> : null}
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setBase(perfil);
                  setOpen(true);
                }}
                aria-label={`Criar nova versão de ${perfil.codigo} ${perfil.versao}`}
              >
                <GitBranchPlus className="mr-1.5 h-4 w-4" aria-hidden="true" />
                Criar nova versão
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <Texto titulo="Diretrizes gerais" valor={perfil.diretrizes_gerais} />
            <Texto titulo="Guia de fronteiras" valor={perfil.guia_fronteiras} />
            <details className="rounded-md border p-3">
              <summary className="cursor-pointer text-sm font-medium">Avançado</summary>
              <div className="mt-3">
                <Texto titulo="Template do prompt" valor={perfil.template_prompt} />
              </div>
            </details>
          </CardContent>
        </Card>
      ))}

      <NovaVersaoPerfilDialog open={open} onOpenChange={setOpen} base={base} />
    </div>
  );
}
