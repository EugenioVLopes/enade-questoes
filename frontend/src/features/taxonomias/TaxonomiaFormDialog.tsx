import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Loader2 } from "lucide-react";

import { getErrorMessage } from "@/api/errors";
import { queryKeys } from "@/api/queryKeys";
import {
  useAtualizarTaxonomiaMutation,
  useCriarTaxonomiaMutation,
  type TaxonomiaResponse,
} from "@/api/taxonomias";
import { useTaxonomia } from "@/components/layout/useTaxonomia";
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
import {
  collectFieldErrors,
  taxonomiaCriarSchema,
  taxonomiaEditarSchema,
  type FieldErrors,
} from "@/features/taxonomias/taxonomiasSchema";

export interface TaxonomiaFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** null = criar; objeto = editar. */
  taxonomia: TaxonomiaResponse | null;
}

function Body({
  taxonomia,
  onOpenChange,
}: {
  taxonomia: TaxonomiaResponse | null;
  onOpenChange: (open: boolean) => void;
}) {
  const editando = taxonomia !== null;
  const { setActiveTaxonomiaId } = useTaxonomia();
  const criar = useCriarTaxonomiaMutation();
  const atualizar = useAtualizarTaxonomiaMutation();
  const queryClient = useQueryClient();
  const pending = criar.isPending || atualizar.isPending;

  const [codigo, setCodigo] = useState("");
  const [nome, setNome] = useState(taxonomia?.nome ?? "");
  const [curso, setCurso] = useState(taxonomia?.curso_referencia ?? "");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  // Salvou, mas o refetch da lista falhou: o diálogo fica aberto com o aviso (sem reenvio,
  // para não duplicar a criação) até o usuário fechar.
  const [avisoLista, setAvisoLista] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);

    const parsed = editando
      ? taxonomiaEditarSchema.safeParse({ nome, curso_referencia: curso })
      : taxonomiaCriarSchema.safeParse({ codigo, nome, curso_referencia: curso });
    if (!parsed.success) {
      setErrors(collectFieldErrors(parsed.error));
      return;
    }
    setErrors({});

    try {
      if (taxonomia) {
        await atualizar.mutateAsync({
          taxonomiaId: taxonomia.id,
          nome: parsed.data.nome,
          curso_referencia: parsed.data.curso_referencia,
        });
      } else {
        const criada = await criar.mutateAsync({
          codigo: codigo.trim(),
          nome: parsed.data.nome,
          curso_referencia: parsed.data.curso_referencia,
        });
        // A mutation só resolve após o refetch de taxonomias; do contrário o provider
        // não conheceria o id e voltaria ao fallback.
        setActiveTaxonomiaId(criada.id);
      }
      const refetch = queryClient.getQueryState(queryKeys.taxonomias.all);
      if (refetch?.status === "error") {
        setAvisoLista(
          getErrorMessage(
            refetch.error,
            "Não foi possível atualizar a lista de Taxonomias.",
          ),
        );
        return;
      }
      onOpenChange(false);
    } catch (error) {
      setSubmitError(getErrorMessage(error, "Não foi possível salvar a Taxonomia."));
    }
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>{editando ? "Editar Taxonomia" : "Nova Taxonomia"}</DialogTitle>
        <DialogDescription>
          {editando
            ? "Altere o nome e o curso de referência. O código não pode ser alterado."
            : "Informe o código único, o nome e o curso de referência."}
        </DialogDescription>
      </DialogHeader>

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="taxonomia-codigo">Código</Label>
          <Input
            id="taxonomia-codigo"
            value={editando ? taxonomia.codigo : codigo}
            readOnly={editando}
            disabled={pending}
            aria-invalid={Boolean(errors.codigo)}
            onChange={(event) => setCodigo(event.target.value)}
          />
          {errors.codigo ? <p className="text-xs text-destructive">{errors.codigo}</p> : null}
        </div>
        <div className="space-y-2">
          <Label htmlFor="taxonomia-nome">Nome</Label>
          <Input
            id="taxonomia-nome"
            value={nome}
            disabled={pending}
            aria-invalid={Boolean(errors.nome)}
            onChange={(event) => setNome(event.target.value)}
          />
          {errors.nome ? <p className="text-xs text-destructive">{errors.nome}</p> : null}
        </div>
        <div className="space-y-2">
          <Label htmlFor="taxonomia-curso">Curso de referência</Label>
          <Input
            id="taxonomia-curso"
            value={curso}
            disabled={pending}
            onChange={(event) => setCurso(event.target.value)}
          />
        </div>

        {avisoLista ? (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Taxonomia salva, mas a lista não foi atualizada</AlertTitle>
            <AlertDescription>{avisoLista}</AlertDescription>
          </Alert>
        ) : null}

        {submitError ? (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Falha ao salvar Taxonomia</AlertTitle>
            <AlertDescription>{submitError}</AlertDescription>
          </Alert>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="outline" disabled={pending} onClick={() => onOpenChange(false)}>
            {avisoLista ? "Fechar" : "Cancelar"}
          </Button>
          <Button type="submit" disabled={pending || avisoLista !== null}>
            {pending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : null}
            Salvar
          </Button>
        </DialogFooter>
      </form>
    </>
  );
}

export function TaxonomiaFormDialog({ open, onOpenChange, taxonomia }: TaxonomiaFormDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        {open ? (
          <Body key={taxonomia?.id ?? "nova"} taxonomia={taxonomia} onOpenChange={onOpenChange} />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
