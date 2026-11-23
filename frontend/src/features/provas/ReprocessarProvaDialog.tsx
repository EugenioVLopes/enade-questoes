import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, AlertTriangle, Loader2 } from "lucide-react";

import { getErrorMessage } from "@/api/errors";
import { obterProva, useReprocessarProvaMutation } from "@/api/provas";
import { queryKeys } from "@/api/queryKeys";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

export interface ReprocessarTargetProva {
  id: string;
  exame: string;
  curso: string;
  ano: number;
  editadasManualmente: number | null;
}

export interface ReprocessarProvaDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  target: ReprocessarTargetProva | null;
}

function ReprocessarProvaDialogBody({
  target,
  onOpenChange,
}: {
  target: ReprocessarTargetProva;
  onOpenChange: (open: boolean) => void;
}) {
  const mutation = useReprocessarProvaMutation();
  const [sobrescreverEditadas, setSobrescreverEditadas] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const detailQuery = useQuery({
    queryKey: queryKeys.provas.detail(target.id),
    queryFn: () => obterProva(target.id),
    enabled: target.editadasManualmente === null,
    retry: false,
  });

  const resolvedEditadasManualmente =
    target.editadasManualmente ?? detailQuery.data?.questoes.editadas_manualmente ?? null;

  async function handleConfirm() {
    setSubmitError(null);
    try {
      await mutation.mutateAsync({
        provaId: target.id,
        sobrescrever_editadas: sobrescreverEditadas,
      });
      onOpenChange(false);
    } catch (error) {
      setSubmitError(getErrorMessage(error, "Não foi possível reprocessar a Prova."));
    }
  }

  return (
    <>
      <AlertDialogHeader>
        <AlertDialogTitle>Reprocessar Prova</AlertDialogTitle>
        <AlertDialogDescription>
          Reconciliação para {target.exame} · {target.curso} · {target.ano}. A extração será
          refeita pelo número oficial de cada Questão, preservando o Gabarito e as Classificações
          existentes.
        </AlertDialogDescription>
      </AlertDialogHeader>

      {resolvedEditadasManualmente !== null && resolvedEditadasManualmente > 0 ? (
        <Alert variant={sobrescreverEditadas ? "destructive" : "default"}>
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>
            {resolvedEditadasManualmente} Questões editadas manualmente
          </AlertTitle>
          <AlertDescription>
            {sobrescreverEditadas
              ? "Atenção: essas edições manuais serão sobrescritas pela nova extração."
              : "Com a opção abaixo desmarcada, essas edições manuais serão preservadas."}
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="flex items-start gap-2.5 rounded-md border p-3">
        <Checkbox
          id="reprocessar-sobrescrever-editadas"
          checked={sobrescreverEditadas}
          disabled={mutation.isPending}
          onCheckedChange={(checked) => setSobrescreverEditadas(checked === true)}
        />
        <div className="space-y-1 leading-none">
          <Label htmlFor="reprocessar-sobrescrever-editadas" className="cursor-pointer">
            Sobrescrever questões editadas manualmente
          </Label>
          <p className="text-xs text-muted-foreground">
            Mantida desmarcada por padrão para proteger curadorias já feitas no enunciado ou nas
            Alternativas.
          </p>
        </div>
      </div>

      {submitError ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Falha ao reprocessar Prova</AlertTitle>
          <AlertDescription>{submitError}</AlertDescription>
        </Alert>
      ) : null}

      <AlertDialogFooter>
        <AlertDialogCancel disabled={mutation.isPending}>Cancelar</AlertDialogCancel>
        <Button type="button" onClick={handleConfirm} disabled={mutation.isPending}>
          {mutation.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              Reprocessando...
            </>
          ) : (
            "Confirmar reprocessamento"
          )}
        </Button>
      </AlertDialogFooter>
    </>
  );
}

export function ReprocessarProvaDialog({
  open,
  onOpenChange,
  target,
}: ReprocessarProvaDialogProps) {
  return (
    <AlertDialog open={open && target !== null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        {open && target ? (
          <ReprocessarProvaDialogBody
            key={target.id}
            target={target}
            onOpenChange={onOpenChange}
          />
        ) : null}
      </AlertDialogContent>
    </AlertDialog>
  );
}
