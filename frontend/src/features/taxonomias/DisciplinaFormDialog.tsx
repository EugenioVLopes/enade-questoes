import { useState, type FormEvent } from "react";
import { AlertCircle, Loader2 } from "lucide-react";

import { getErrorMessage } from "@/api/errors";
import {
  useAtualizarDisciplinaMutation,
  useCriarDisciplinaMutation,
  type DisciplinaResponse,
} from "@/api/taxonomias";
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
import { Textarea } from "@/components/ui/textarea";
import {
  collectFieldErrors,
  disciplinaCriarSchema,
  disciplinaEditarSchema,
  type FieldErrors,
} from "@/features/taxonomias/taxonomiasSchema";

export interface DisciplinaFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  taxonomiaId: string;
  /** null = criar; objeto = editar. */
  disciplina: DisciplinaResponse | null;
}

function Body({
  taxonomiaId,
  disciplina,
  onOpenChange,
}: {
  taxonomiaId: string;
  disciplina: DisciplinaResponse | null;
  onOpenChange: (open: boolean) => void;
}) {
  const editando = disciplina !== null;
  const criar = useCriarDisciplinaMutation();
  const atualizar = useAtualizarDisciplinaMutation();
  const pending = criar.isPending || atualizar.isPending;

  const [codigo, setCodigo] = useState("");
  const [nome, setNome] = useState(disciplina?.nome ?? "");
  const [ementa, setEmenta] = useState(disciplina?.ementa ?? "");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);

    const parsed = editando
      ? disciplinaEditarSchema.safeParse({ nome, ementa })
      : disciplinaCriarSchema.safeParse({ codigo, nome, ementa });
    if (!parsed.success) {
      setErrors(collectFieldErrors(parsed.error));
      return;
    }
    setErrors({});

    try {
      if (disciplina) {
        await atualizar.mutateAsync({
          disciplinaId: disciplina.id,
          nome: parsed.data.nome,
          ementa: parsed.data.ementa,
        });
      } else {
        await criar.mutateAsync({
          taxonomiaId,
          codigo: codigo.trim(),
          nome: parsed.data.nome,
          ementa: parsed.data.ementa,
          ativa: true,
        });
      }
      onOpenChange(false);
    } catch (error) {
      setSubmitError(getErrorMessage(error, "Não foi possível salvar a Disciplina."));
    }
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>{editando ? "Editar Disciplina" : "Nova Disciplina"}</DialogTitle>
        <DialogDescription>
          {editando
            ? "Altere o nome e a ementa. O código não pode ser alterado."
            : "Informe o código único, o nome e a ementa."}
        </DialogDescription>
      </DialogHeader>

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="disciplina-codigo">Código</Label>
          <Input
            id="disciplina-codigo"
            value={editando ? disciplina.codigo : codigo}
            readOnly={editando}
            disabled={pending}
            aria-invalid={Boolean(errors.codigo)}
            onChange={(event) => setCodigo(event.target.value)}
          />
          {errors.codigo ? <p className="text-xs text-destructive">{errors.codigo}</p> : null}
        </div>
        <div className="space-y-2">
          <Label htmlFor="disciplina-nome">Nome</Label>
          <Input
            id="disciplina-nome"
            value={nome}
            disabled={pending}
            aria-invalid={Boolean(errors.nome)}
            onChange={(event) => setNome(event.target.value)}
          />
          {errors.nome ? <p className="text-xs text-destructive">{errors.nome}</p> : null}
        </div>
        <div className="space-y-2">
          <Label htmlFor="disciplina-ementa">Ementa</Label>
          <Textarea
            id="disciplina-ementa"
            value={ementa}
            disabled={pending}
            onChange={(event) => setEmenta(event.target.value)}
          />
        </div>

        {submitError ? (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Falha ao salvar Disciplina</AlertTitle>
            <AlertDescription>{submitError}</AlertDescription>
          </Alert>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="outline" disabled={pending} onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" disabled={pending}>
            {pending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : null}
            Salvar
          </Button>
        </DialogFooter>
      </form>
    </>
  );
}

export function DisciplinaFormDialog({
  open,
  onOpenChange,
  taxonomiaId,
  disciplina,
}: DisciplinaFormDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        {open ? (
          <Body
            key={`${taxonomiaId}:${disciplina?.id ?? "nova"}`}
            taxonomiaId={taxonomiaId}
            disciplina={disciplina}
            onOpenChange={onOpenChange}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
