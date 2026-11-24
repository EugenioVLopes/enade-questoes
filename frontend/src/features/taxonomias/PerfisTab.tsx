import { useState } from "react";
import { AlertCircle, GitBranchPlus } from "lucide-react";

import { getErrorMessage } from "@/api/errors";
import { usePerfisClassificacaoQuery, type PerfilClassificacaoResponse } from "@/api/taxonomias";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { NovaVersaoPerfilDialog } from "@/features/taxonomias/NovaVersaoPerfilDialog";

function Texto({ titulo, valor, mono = false }: { titulo: string; valor: string; mono?: boolean }) {
  return (
    <div className="space-y-1.5">
      <h4 className="text-xs font-semibold text-muted-foreground">{titulo}</h4>
      <p
        className={
          mono
            ? "whitespace-pre-wrap rounded-md border border-border bg-surface/65 p-3 font-mono text-xs leading-relaxed text-foreground"
            : "whitespace-pre-wrap text-sm leading-relaxed text-foreground/85"
        }
      >
        {valor || "—"}
      </p>
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
        <Card key={perfil.id} data-testid={`perfil-card-${perfil.id}`} className="overflow-hidden">
          <CardHeader className="gap-2 border-b border-border bg-surface/35 pb-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-1">
                <CardTitle className="font-mono text-base font-semibold tracking-tight">
                  {perfil.codigo} · {perfil.versao}
                </CardTitle>
                {perfil.descricao ? <CardDescription>{perfil.descricao}</CardDescription> : null}
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setBase(perfil);
                  setOpen(true);
                }}
                aria-label={`Criar nova versão de ${perfil.codigo} ${perfil.versao}`}
              >
                <GitBranchPlus className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                Criar nova versão
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 pt-4">
            <Texto titulo="Diretrizes gerais" valor={perfil.diretrizes_gerais} />
            <Texto titulo="Guia de fronteiras" valor={perfil.guia_fronteiras} />
            <details className="rounded-md border border-border bg-surface/30 p-3">
              <summary className="cursor-pointer text-xs font-semibold text-foreground">Avançado</summary>
              <div className="mt-3">
                <Texto titulo="Template do prompt" valor={perfil.template_prompt} mono />
              </div>
            </details>
          </CardContent>
        </Card>
      ))}

      <NovaVersaoPerfilDialog open={open} onOpenChange={setOpen} base={base} />
    </div>
  );
}
