import { useState, type FormEvent } from "react";
import { AlertCircle, Loader2 } from "lucide-react";

import { useCriarExecucaoMutation, type EscopoExecucao } from "@/api/execucoes";
import { getErrorMessage } from "@/api/errors";
import { useProvasQuery } from "@/api/provas";
import { findDefaultPerfil, usePerfisClassificacaoQuery } from "@/api/taxonomias";
import { useTaxonomia } from "@/components/layout/useTaxonomia";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  collectFieldErrors,
  execucaoSchema,
  type FieldErrors,
} from "@/features/taxonomias/taxonomiasSchema";

type EscopoUi = Exclude<EscopoExecucao, "questao_ids">;

const ESCOPOS: { valor: EscopoUi; rotulo: string }[] = [
  { valor: "todas", rotulo: "Todas as questões" },
  { valor: "prova_id", rotulo: "Por Prova" },
  { valor: "pendentes", rotulo: "Apenas não classificadas (pendentes)" },
  { valor: "disciplina_arquivada", rotulo: "Com Disciplina arquivada" },
];

export interface NovaExecucaoDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function Body({ onOpenChange }: { onOpenChange: (open: boolean) => void }) {
  const { taxonomias, activeTaxonomiaId } = useTaxonomia();
  const perfisQuery = usePerfisClassificacaoQuery();
  const provasQuery = useProvasQuery();
  const mutation = useCriarExecucaoMutation();

  const perfis = perfisQuery.data?.itens ?? [];
  const provas = provasQuery.data?.itens ?? [];

  // Sem escolha explícita, segue a Taxonomia ativa (que pode chegar depois da abertura).
  const [taxonomiaEscolhida, setTaxonomiaEscolhida] = useState("");
  const [perfilEscolhido, setPerfilEscolhido] = useState("");
  const [escopo, setEscopo] = useState<EscopoUi>("todas");
  const [provaId, setProvaId] = useState("");
  const [incluirRevisadas, setIncluirRevisadas] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  const taxonomiaId = taxonomiaEscolhida || activeTaxonomiaId || "";
  const perfilId = perfilEscolhido || findDefaultPerfil(perfis)?.id || "";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);

    const parsed = execucaoSchema.safeParse({
      taxonomia_id: taxonomiaId,
      perfil_id: perfilId,
      escopo,
      prova_id: provaId,
      incluir_revisadas: incluirRevisadas,
    });
    if (!parsed.success) {
      setErrors(collectFieldErrors(parsed.error));
      return;
    }
    setErrors({});

    try {
      await mutation.mutateAsync({
        taxonomia_id: parsed.data.taxonomia_id,
        perfil_id: parsed.data.perfil_id,
        escopo: parsed.data.escopo,
        incluir_revisadas: parsed.data.incluir_revisadas,
        ...(parsed.data.escopo === "prova_id" ? { prova_id: parsed.data.prova_id } : {}),
      });
      onOpenChange(false);
    } catch (error) {
      setSubmitError(getErrorMessage(error, "Não foi possível iniciar a Execução."));
    }
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Nova Execução de Classificação</DialogTitle>
        <DialogDescription>
          Escolha a Taxonomia, o Perfil e o escopo das Questões a classificar.
        </DialogDescription>
      </DialogHeader>

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="execucao-taxonomia">Taxonomia</Label>
          <Select value={taxonomiaId} onValueChange={setTaxonomiaEscolhida} disabled={mutation.isPending}>
            <SelectTrigger id="execucao-taxonomia">
              <SelectValue placeholder="Selecione..." />
            </SelectTrigger>
            <SelectContent>
              {taxonomias.map((item) => (
                <SelectItem key={item.id} value={item.id}>
                  {item.nome}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {errors.taxonomia_id ? (
            <p className="text-xs text-destructive">{errors.taxonomia_id}</p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="execucao-perfil">Perfil de Classificação</Label>
          <Select value={perfilId} onValueChange={setPerfilEscolhido} disabled={mutation.isPending}>
            <SelectTrigger id="execucao-perfil">
              <SelectValue placeholder="Selecione..." />
            </SelectTrigger>
            <SelectContent>
              {perfis.map((item) => (
                <SelectItem key={item.id} value={item.id}>
                  {item.codigo} · {item.versao}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {errors.perfil_id ? <p className="text-xs text-destructive">{errors.perfil_id}</p> : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="execucao-escopo">Escopo</Label>
          <Select value={escopo} onValueChange={(valor) => setEscopo(valor as EscopoUi)} disabled={mutation.isPending}>
            <SelectTrigger id="execucao-escopo">
              <SelectValue placeholder="Selecione..." />
            </SelectTrigger>
            <SelectContent>
              {ESCOPOS.map((item) => (
                <SelectItem key={item.valor} value={item.valor}>
                  {item.rotulo}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {escopo === "prova_id" ? (
          <div className="space-y-2">
            <Label htmlFor="execucao-prova">Prova</Label>
            <Select value={provaId} onValueChange={setProvaId} disabled={mutation.isPending}>
              <SelectTrigger id="execucao-prova">
                <SelectValue placeholder="Selecione..." />
              </SelectTrigger>
              <SelectContent>
                  {provas.map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {item.exame} {item.ano} · {item.curso}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
            {errors.prova_id ? <p className="text-xs text-destructive">{errors.prova_id}</p> : null}
          </div>
        ) : null}

        <div className="flex items-start gap-2.5 rounded-md border p-3">
          <Checkbox
            id="execucao-incluir-revisadas"
            checked={incluirRevisadas}
            disabled={mutation.isPending}
            onCheckedChange={(checked) => setIncluirRevisadas(checked === true)}
          />
          <div className="space-y-1 leading-none">
            <Label htmlFor="execucao-incluir-revisadas" className="cursor-pointer">
              Incluir questões já revisadas por humano
            </Label>
            <p className="text-xs text-muted-foreground">
              Revisões humanas nunca são sobrescritas automaticamente: uma nova sugestão só gera
              divergência para você decidir.
            </p>
          </div>
        </div>

        {submitError ? (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Falha ao iniciar Execução</AlertTitle>
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
            Iniciar Execução
          </Button>
        </DialogFooter>
      </form>
    </>
  );
}

export function NovaExecucaoDialog({ open, onOpenChange }: NovaExecucaoDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        {open ? <Body onOpenChange={onOpenChange} /> : null}
      </DialogContent>
    </Dialog>
  );
}
