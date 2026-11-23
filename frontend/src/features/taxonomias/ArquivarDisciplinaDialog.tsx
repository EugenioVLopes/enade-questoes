import { useState } from "react";
import { AlertCircle, Loader2 } from "lucide-react";

import { getErrorMessage } from "@/api/errors";
import { useAtualizarDisciplinaMutation, type DisciplinaResponse } from "@/api/taxonomias";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";

export interface ArquivarDisciplinaDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  disciplina: DisciplinaResponse | null;
}

function Body({
  disciplina,
  onOpenChange,
}: {
  disciplina: DisciplinaResponse;
  onOpenChange: (open: boolean) => void;
}) {
  const mutation = useAtualizarDisciplinaMutation();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const arquivando = disciplina.ativa;
  const impactadas = disciplina.classificacoes_vigentes_impactadas;

  async function handleConfirm() {
    setSubmitError(null);
    try {
      await mutation.mutateAsync({ disciplinaId: disciplina.id, ativa: !arquivando });
      onOpenChange(false);
    } catch (error) {
      setSubmitError(
        getErrorMessage(
          error,
          arquivando
            ? "Não foi possível arquivar a Disciplina."
            : "Não foi possível reativar a Disciplina.",
        ),
      );
    }
  }

  return (
    <>
      <AlertDialogHeader>
        <AlertDialogTitle>
          {arquivando ? "Arquivar Disciplina" : "Reativar Disciplina"}
        </AlertDialogTitle>
        <AlertDialogDescription>
          {disciplina.codigo} · {disciplina.nome}.{" "}
          {arquivando
            ? "A Disciplina não é excluída: ela deixa de ser sugerida em novas Classificações."
            : "A Disciplina volta a poder ser sugerida em novas Classificações."}
        </AlertDialogDescription>
      </AlertDialogHeader>

      <p className="text-sm" data-testid="impacto-classificacoes">
        {impactadas === 1
          ? "1 Classificação vigente "
          : `${impactadas} Classificações vigentes `}
        {arquivando
          ? "será marcada com o indicador \"usa disciplina arquivada\"."
          : "deixará de ser marcada com o indicador \"usa disciplina arquivada\"."}
      </p>

      {submitError ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Falha ao atualizar Disciplina</AlertTitle>
          <AlertDescription>{submitError}</AlertDescription>
        </Alert>
      ) : null}

      <AlertDialogFooter>
        <AlertDialogCancel disabled={mutation.isPending}>Cancelar</AlertDialogCancel>
        <Button type="button" onClick={handleConfirm} disabled={mutation.isPending}>
          {mutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
          ) : null}
          {arquivando ? "Confirmar arquivamento" : "Confirmar reativação"}
        </Button>
      </AlertDialogFooter>
    </>
  );
}

export function ArquivarDisciplinaDialog({
  open,
  onOpenChange,
  disciplina,
}: ArquivarDisciplinaDialogProps) {
  return (
    <AlertDialog open={open && disciplina !== null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        {open && disciplina ? (
          <Body key={disciplina.id} disciplina={disciplina} onOpenChange={onOpenChange} />
        ) : null}
      </AlertDialogContent>
    </AlertDialog>
  );
}
