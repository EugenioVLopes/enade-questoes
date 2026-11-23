import { useState, type FormEvent } from "react";
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

import { getErrorMessage } from "@/api/errors";
import {
  useAtualizarGabaritoMutation,
  type ResumoAtualizacaoGabaritoResponse,
} from "@/api/provas";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { atualizarGabaritoFormSchema } from "@/features/provas/ingestaoSchema";

export interface GabaritoTargetProva {
  id: string;
  exame: string;
  curso: string;
  ano: number;
}

export interface AtualizarGabaritoDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  prova: GabaritoTargetProva | null;
}

function AtualizarGabaritoDialogBody({
  prova,
  onOpenChange,
}: {
  prova: GabaritoTargetProva;
  onOpenChange: (open: boolean) => void;
}) {
  const mutation = useAtualizarGabaritoMutation();
  const [arquivoGabarito, setArquivoGabarito] = useState<File | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [resumo, setResumo] = useState<ResumoAtualizacaoGabaritoResponse | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);

    const parsed = atualizarGabaritoFormSchema.safeParse({
      arquivo_gabarito: arquivoGabarito,
    });

    if (!parsed.success) {
      setFieldError(parsed.error.issues[0]?.message ?? "Selecione um PDF válido para o Gabarito.");
      return;
    }

    setFieldError(null);

    try {
      const resultado = await mutation.mutateAsync({
        provaId: prova.id,
        arquivo_gabarito: parsed.data.arquivo_gabarito,
      });
      setResumo(resultado);
    } catch (error) {
      setSubmitError(getErrorMessage(error, "Não foi possível atualizar o Gabarito."));
    }
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Atualizar Gabarito</DialogTitle>
        <DialogDescription>
          {prova.exame} · {prova.curso} · {prova.ano}. As Classificações e edições manuais de
          enunciado ou Alternativas serão preservadas.
        </DialogDescription>
      </DialogHeader>

      {resumo ? (
        <div className="space-y-4">
          <Alert className="border-emerald-500/40 bg-emerald-500/10">
            <CheckCircle2 className="h-4 w-4 text-emerald-700 dark:text-emerald-300" />
            <AlertTitle>Gabarito atualizado</AlertTitle>
            <AlertDescription>
              Confira o resultado da conciliação nas Questões desta Prova.
            </AlertDescription>
          </Alert>

          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-md border p-3">
              <p className="text-xs text-muted-foreground">Mantidas</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">{resumo.mantidas}</p>
            </div>
            <div className="rounded-md border p-3">
              <p className="text-xs text-muted-foreground">Alteradas</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">{resumo.alteradas}</p>
            </div>
            <div className="rounded-md border p-3">
              <p className="text-xs text-muted-foreground">Anuladas</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">{resumo.anuladas}</p>
            </div>
          </div>

          {resumo.sem_correspondencia.length > 0 ? (
            <p className="text-xs text-muted-foreground">
              Sem correspondência na Prova: {resumo.sem_correspondencia.join(", ")}
            </p>
          ) : null}

          {resumo.questoes_sem_gabarito.length > 0 ? (
            <p className="text-xs text-muted-foreground">
              Questões sem Gabarito: {resumo.questoes_sem_gabarito.join(", ")}
            </p>
          ) : null}

          <DialogFooter>
            <Button type="button" onClick={() => onOpenChange(false)}>
              Concluir
            </Button>
          </DialogFooter>
        </div>
      ) : (
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="atualizar-gabarito-pdf">PDF do Gabarito</Label>
            <Input
              id="atualizar-gabarito-pdf"
              type="file"
              accept=".pdf,application/pdf"
              aria-invalid={Boolean(fieldError)}
              onChange={(event) => {
                setArquivoGabarito(event.target.files?.[0] ?? null);
                setFieldError(null);
              }}
            />
            {fieldError ? (
              <p className="text-xs text-destructive" role="alert">
                {fieldError}
              </p>
            ) : null}
          </div>

          {submitError ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Falha ao atualizar Gabarito</AlertTitle>
              <AlertDescription>{submitError}</AlertDescription>
            </Alert>
          ) : null}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={mutation.isPending}
              onClick={() => onOpenChange(false)}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                  Atualizando...
                </>
              ) : (
                "Atualizar Gabarito"
              )}
            </Button>
          </DialogFooter>
        </form>
      )}
    </>
  );
}

export function AtualizarGabaritoDialog({
  open,
  onOpenChange,
  prova,
}: AtualizarGabaritoDialogProps) {
  return (
    <Dialog open={open && prova !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        {open && prova ? (
          <AtualizarGabaritoDialogBody key={prova.id} prova={prova} onOpenChange={onOpenChange} />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
