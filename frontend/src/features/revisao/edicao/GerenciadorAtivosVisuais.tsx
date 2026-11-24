import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { ArrowDown, ArrowUp, Trash2, Upload } from "lucide-react";

import {
  useAdicionarAtivoVisualMutation,
  useAtualizarAtivoVisualMutation,
  useRemoverAtivoVisualMutation,
  useReordenarAtivosVisuaisMutation,
  type AtivoVisualResponse,
  type LetraAlternativa,
} from "@/api/edicaoQuestao";
import { getErrorMessage } from "@/api/errors";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button-variants";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

import {
  LETRAS_ALTERNATIVA,
  ROTULOS_ORIGEM_ATIVO,
  calcularReordenacaoAtivos,
  urlAtivoComRevisao,
  validarArquivoImagem,
} from "./editorUtils";

const VINCULO_ENUNCIADO = "__enunciado__";
const ACCEPT_IMAGENS = "image/png,image/jpeg,.png,.jpg,.jpeg";

export interface GerenciadorAtivosVisuaisProps {
  questaoId: string;
  ativos: readonly AtivoVisualResponse[];
  revisoesAtivos?: Readonly<Record<string, number>>;
  onMidiaAlterada: (opcoes?: { ativoSubstituidoId?: string }) => void;
}

function SeletorVinculo({
  id,
  ariaLabel,
  value,
  disabled,
  triggerClassName,
  onValueChange,
}: {
  id?: string;
  ariaLabel: string;
  value: string;
  disabled: boolean;
  triggerClassName?: string;
  onValueChange: (valor: string) => void;
}) {
  return (
    <Select value={value} onValueChange={onValueChange} disabled={disabled}>
      <SelectTrigger id={id} aria-label={ariaLabel} className={triggerClassName}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={VINCULO_ENUNCIADO}>Enunciado</SelectItem>
        {LETRAS_ALTERNATIVA.map((letra) => (
          <SelectItem key={letra} value={letra}>
            Alternativa {letra}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function GerenciadorAtivosVisuais({
  questaoId,
  ativos,
  revisoesAtivos,
  onMidiaAlterada,
}: GerenciadorAtivosVisuaisProps) {
  const adicionar = useAdicionarAtivoVisualMutation();
  const atualizar = useAtualizarAtivoVisualMutation();
  const reordenar = useReordenarAtivosVisuaisMutation();
  const remover = useRemoverAtivoVisualMutation();

  const [novoArquivo, setNovoArquivo] = useState<File | null>(null);
  const [novoVinculo, setNovoVinculo] = useState<string>(VINCULO_ENUNCIADO);
  const [inputKey, setInputKey] = useState(0);
  const [erro, setErro] = useState<string | null>(null);
  const [ativoParaExcluir, setAtivoParaExcluir] = useState<AtivoVisualResponse | null>(null);

  const questaoAnteriorRef = useRef(questaoId);
  useEffect(() => {
    if (questaoAnteriorRef.current === questaoId) {
      return;
    }
    questaoAnteriorRef.current = questaoId;
    setNovoArquivo(null);
    setNovoVinculo(VINCULO_ENUNCIADO);
    setInputKey((atual) => atual + 1);
    setErro(null);
    setAtivoParaExcluir(null);
  }, [questaoId]);

  const ocupado =
    adicionar.isPending || atualizar.isPending || reordenar.isPending || remover.isPending;

  async function mover(ativoId: string, direcao: "subir" | "descer") {
    const atualizacoes = calcularReordenacaoAtivos(ativos, ativoId, direcao);
    if (atualizacoes.length === 0) {
      return;
    }
    setErro(null);
    try {
      await reordenar.mutateAsync(atualizacoes);
      onMidiaAlterada();
    } catch (error) {
      setErro(getErrorMessage(error, "Não foi possível reordenar os Ativos Visuais."));
    }
  }

  async function alterarVinculo(ativo: AtivoVisualResponse, valor: string) {
    const atual = ativo.alternativa_letra ?? VINCULO_ENUNCIADO;
    if (valor === atual) {
      return;
    }
    setErro(null);
    try {
      if (valor === VINCULO_ENUNCIADO) {
        await atualizar.mutateAsync({
          ativoId: ativo.id,
          removerAlternativaLetra: true,
        });
      } else {
        await atualizar.mutateAsync({
          ativoId: ativo.id,
          alternativaLetra: valor as LetraAlternativa,
        });
      }
      onMidiaAlterada();
    } catch (error) {
      setErro(getErrorMessage(error, "Não foi possível atualizar o vínculo do Ativo Visual."));
    }
  }

  async function substituir(ativoId: string, evento: ChangeEvent<HTMLInputElement>) {
    const arquivo = evento.target.files?.[0] ?? null;
    evento.target.value = "";
    if (!arquivo) {
      return;
    }

    const erroValidacao = validarArquivoImagem(arquivo);
    if (erroValidacao) {
      setErro(erroValidacao);
      return;
    }

    setErro(null);
    try {
      await atualizar.mutateAsync({ ativoId, arquivo });
      onMidiaAlterada({ ativoSubstituidoId: ativoId });
    } catch (error) {
      setErro(getErrorMessage(error, "Não foi possível substituir o arquivo do Ativo Visual."));
    }
  }

  async function enviarNovo() {
    const erroValidacao = validarArquivoImagem(novoArquivo);
    if (erroValidacao || !novoArquivo) {
      setErro(erroValidacao ?? "Selecione uma imagem no formato PNG ou JPEG.");
      return;
    }

    setErro(null);
    try {
      await adicionar.mutateAsync({
        questaoId,
        arquivo: novoArquivo,
        alternativaLetra:
          novoVinculo === VINCULO_ENUNCIADO ? null : (novoVinculo as LetraAlternativa),
      });
      setNovoArquivo(null);
      setInputKey((atual) => atual + 1);
      onMidiaAlterada();
    } catch (error) {
      setErro(getErrorMessage(error, "Não foi possível enviar o Ativo Visual."));
    }
  }

  async function confirmarExclusao() {
    if (!ativoParaExcluir) {
      return;
    }
    const alvo = ativoParaExcluir;
    setAtivoParaExcluir(null);
    setErro(null);
    try {
      await remover.mutateAsync(alvo.id);
      onMidiaAlterada();
    } catch (error) {
      setErro(getErrorMessage(error, "Não foi possível excluir o Ativo Visual."));
    }
  }

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        <h4 className="text-xs font-semibold text-muted-foreground">Ativos Visuais</h4>
        {ativos.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhum Ativo Visual vinculado a esta Questão.
          </p>
        ) : (
          <ul className="space-y-3" aria-label="Ativos Visuais da Questão">
            {ativos.map((ativo, indice) => (
              <li
                key={ativo.id}
                className="flex flex-col gap-3 rounded-md border border-border bg-background/60 p-3 sm:flex-row sm:items-start"
              >
                <img
                  src={urlAtivoComRevisao(ativo.url_arquivo, revisoesAtivos?.[ativo.id])}
                  alt={`Ativo Visual ${indice + 1}`}
                  className="h-20 w-24 shrink-0 rounded border border-border bg-white object-contain p-1"
                />
                <div className="min-w-0 flex-1 space-y-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs font-medium text-foreground">
                      #{indice + 1}
                    </span>
                    <Badge variant="secondary" data-origem={ativo.origem} title={ativo.origem}>
                      {ROTULOS_ORIGEM_ATIVO[ativo.origem]}
                    </Badge>
                    {ativo.pagina != null ? (
                      <span className="font-mono text-xs text-muted-foreground">
                        p. {ativo.pagina}
                      </span>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      aria-label={`Mover Ativo Visual ${indice + 1} para cima`}
                      disabled={indice === 0 || ocupado}
                      onClick={() => void mover(ativo.id, "subir")}
                    >
                      <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      aria-label={`Mover Ativo Visual ${indice + 1} para baixo`}
                      disabled={indice === ativos.length - 1 || ocupado}
                      onClick={() => void mover(ativo.id, "descer")}
                    >
                      <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
                    </Button>
                    <SeletorVinculo
                      ariaLabel={`Vínculo do Ativo Visual ${indice + 1}`}
                      value={ativo.alternativa_letra ?? VINCULO_ENUNCIADO}
                      disabled={ocupado}
                      triggerClassName="h-8 w-40 text-[13px]"
                      onValueChange={(valor) => void alterarVinculo(ativo, valor)}
                    />
                    <label
                      className={cn(
                        buttonVariants({ variant: "outline", size: "sm" }),
                        "cursor-pointer focus-within:outline-none focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2",
                        ocupado && "pointer-events-none opacity-50",
                      )}
                    >
                      <Upload className="h-3.5 w-3.5" aria-hidden="true" />
                      Substituir arquivo
                      <input
                        type="file"
                        accept={ACCEPT_IMAGENS}
                        className="sr-only"
                        aria-label={`Substituir arquivo do Ativo Visual ${indice + 1}`}
                        disabled={ocupado}
                        onChange={(evento) => void substituir(ativo.id, evento)}
                      />
                    </label>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="text-destructive hover:border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
                      aria-label={`Excluir Ativo Visual ${indice + 1}`}
                      disabled={ocupado}
                      onClick={() => setAtivoParaExcluir(ativo)}
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                      Excluir
                    </Button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {erro ? (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{erro}</AlertDescription>
        </Alert>
      ) : null}

      <div className="space-y-3 rounded-md border border-border bg-surface/40 p-3.5">
        <div className="grid gap-3 sm:grid-cols-[1fr_12rem] sm:items-end">
          <div className="space-y-1.5">
            <Label htmlFor="novo-ativo-arquivo">Novo Ativo Visual (PNG ou JPEG)</Label>
            <Input
              key={inputKey}
              id="novo-ativo-arquivo"
              type="file"
              accept={ACCEPT_IMAGENS}
              disabled={ocupado}
              onChange={(evento) => {
                setNovoArquivo(evento.target.files?.[0] ?? null);
                setErro(null);
              }}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="novo-ativo-vinculo">Vincular a</Label>
            <SeletorVinculo
              id="novo-ativo-vinculo"
              ariaLabel="Vincular novo Ativo Visual a"
              value={novoVinculo}
              disabled={ocupado}
              onValueChange={setNovoVinculo}
            />
          </div>
        </div>
        <Button
          type="button"
          disabled={ocupado || !novoArquivo}
          onClick={() => void enviarNovo()}
        >
          Enviar Ativo Visual
        </Button>
      </div>

      <AlertDialog
        open={ativoParaExcluir !== null}
        onOpenChange={(aberto) => {
          if (!aberto) {
            setAtivoParaExcluir(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir Ativo Visual?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta ação remove permanentemente o Ativo Visual da Questão e não pode ser desfeita.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={ocupado}>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              disabled={ocupado}
              className={buttonVariants({ variant: "destructive" })}
              onClick={() => void confirmarExclusao()}
            >
              Confirmar exclusão
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
