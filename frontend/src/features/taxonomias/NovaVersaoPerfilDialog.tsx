import { useState, type FormEvent } from "react";
import { AlertCircle, Loader2 } from "lucide-react";

import { getErrorMessage } from "@/api/errors";
import { useCriarPerfilMutation, type PerfilClassificacaoResponse } from "@/api/taxonomias";
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
  perfilNovaVersaoSchema,
  type FieldErrors,
} from "@/features/taxonomias/taxonomiasSchema";

export interface NovaVersaoPerfilDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  base: PerfilClassificacaoResponse | null;
}

function Body({
  base,
  onOpenChange,
}: {
  base: PerfilClassificacaoResponse;
  onOpenChange: (open: boolean) => void;
}) {
  const mutation = useCriarPerfilMutation();
  const [versao, setVersao] = useState("");
  const [descricao, setDescricao] = useState(base.descricao);
  const [diretrizes, setDiretrizes] = useState(base.diretrizes_gerais);
  const [fronteiras, setFronteiras] = useState(base.guia_fronteiras);
  const [template, setTemplate] = useState(base.template_prompt);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);

    const parsed = perfilNovaVersaoSchema.safeParse({
      versao,
      descricao,
      diretrizes_gerais: diretrizes,
      guia_fronteiras: fronteiras,
      template_prompt: template,
    });
    if (!parsed.success) {
      setErrors(collectFieldErrors(parsed.error));
      return;
    }
    setErrors({});

    try {
      await mutation.mutateAsync({
        perfil_base_id: base.id,
        codigo: base.codigo,
        ...parsed.data,
      });
      onOpenChange(false);
    } catch (error) {
      setSubmitError(getErrorMessage(error, "Não foi possível criar a nova versão do Perfil."));
    }
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Criar nova versão</DialogTitle>
        <DialogDescription>
          Base: {base.codigo} {base.versao}. A nova versão é imutável depois de criada; a versão
          base permanece inalterada.
        </DialogDescription>
      </DialogHeader>

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="perfil-versao">Versão</Label>
          <Input
            id="perfil-versao"
            value={versao}
            placeholder="ex.: v2"
            disabled={mutation.isPending}
            aria-invalid={Boolean(errors.versao)}
            onChange={(event) => setVersao(event.target.value)}
          />
          {errors.versao ? <p className="text-xs text-destructive">{errors.versao}</p> : null}
        </div>
        <div className="space-y-2">
          <Label htmlFor="perfil-descricao">Descrição</Label>
          <Input
            id="perfil-descricao"
            value={descricao}
            disabled={mutation.isPending}
            onChange={(event) => setDescricao(event.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="perfil-diretrizes">Diretrizes gerais</Label>
          <Textarea
            id="perfil-diretrizes"
            value={diretrizes}
            disabled={mutation.isPending}
            aria-invalid={Boolean(errors.diretrizes_gerais)}
            onChange={(event) => setDiretrizes(event.target.value)}
          />
          {errors.diretrizes_gerais ? (
            <p className="text-xs text-destructive">{errors.diretrizes_gerais}</p>
          ) : null}
        </div>
        <div className="space-y-2">
          <Label htmlFor="perfil-fronteiras">Guia de fronteiras</Label>
          <Textarea
            id="perfil-fronteiras"
            value={fronteiras}
            disabled={mutation.isPending}
            onChange={(event) => setFronteiras(event.target.value)}
          />
        </div>

        <details className="rounded-md border p-3" open={Boolean(errors.template_prompt) || undefined}>
          <summary className="cursor-pointer text-sm font-medium">Avançado</summary>
          <div className="mt-3 space-y-2">
            <Label htmlFor="perfil-template">Template do prompt</Label>
            <Textarea
              id="perfil-template"
              className="font-mono text-xs"
              rows={8}
              value={template}
              disabled={mutation.isPending}
              aria-invalid={Boolean(errors.template_prompt)}
              onChange={(event) => setTemplate(event.target.value)}
            />
            {errors.template_prompt ? (
              <p className="text-xs text-destructive">{errors.template_prompt}</p>
            ) : null}
          </div>
        </details>

        {submitError ? (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Falha ao criar versão</AlertTitle>
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
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
            ) : null}
            Criar versão
          </Button>
        </DialogFooter>
      </form>
    </>
  );
}

export function NovaVersaoPerfilDialog({ open, onOpenChange, base }: NovaVersaoPerfilDialogProps) {
  return (
    <Dialog open={open && base !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        {open && base ? <Body key={base.id} base={base} onOpenChange={onOpenChange} /> : null}
      </DialogContent>
    </Dialog>
  );
}
