import { useId, useState, type FormEvent } from "react";
import { AlertCircle, ChevronDown, ChevronRight, Loader2 } from "lucide-react";

import { isProvaConflictError, getErrorMessage, type ConflitoProvaResponse } from "@/api/errors";
import { useCriarProvaMutation } from "@/api/provas";
import { findDefaultPerfil, usePerfisClassificacaoQuery } from "@/api/taxonomias";
import { useTaxonomia } from "@/components/layout/useTaxonomia";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { resolverFaixaPadraoPorAno } from "@/features/provas/faixasEnade";
import {
  parseIngestaoFormValues,
  type IngestaoFieldErrors,
} from "@/features/provas/ingestaoSchema";

export interface IngestaoFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelectAtualizarGabarito: (conflito: ConflitoProvaResponse) => void;
  onSelectReprocessarProva: (conflito: ConflitoProvaResponse) => void;
}

function IngestaoFormContent({
  onOpenChange,
  onSelectAtualizarGabarito,
  onSelectReprocessarProva,
}: Omit<IngestaoFormDialogProps, "open">) {
  const avancadasPanelId = useId();
  const { activeTaxonomiaId, activeTaxonomia } = useTaxonomia();
  const perfisQuery = usePerfisClassificacaoQuery({ enabled: true });
  const criarProvaMutation = useCriarProvaMutation();

  const [exame, setExame] = useState("ENADE");
  const [curso, setCurso] = useState("Engenharia de Computação");
  const [ano, setAno] = useState("");
  const [questaoInicio, setQuestaoInicio] = useState("");
  const [questaoFim, setQuestaoFim] = useState("");
  const [faixaEditadaManualmente, setFaixaEditadaManualmente] = useState(false);
  const [opcoesAvancadasAbertas, setOpcoesAvancadasAbertas] = useState(false);
  const [classificarAutomaticamente, setClassificarAutomaticamente] = useState(true);
  const [arquivoProva, setArquivoProva] = useState<File | null>(null);
  const [arquivoGabarito, setArquivoGabarito] = useState<File | null>(null);
  const [fieldErrors, setFieldErrors] = useState<IngestaoFieldErrors>({});
  const [conflito, setConflito] = useState<ConflitoProvaResponse | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const defaultPerfil = findDefaultPerfil(perfisQuery.data?.itens ?? []);
  const anoTrimmed = ano.trim();
  const parsedAno = /^\d{4}$/.test(anoTrimmed) ? Number(anoTrimmed) : null;
  const faixaPadraoAtual = parsedAno !== null ? resolverFaixaPadraoPorAno(parsedAno) : null;
  const anoSemFaixaPadrao = parsedAno !== null && parsedAno >= 1900 && faixaPadraoAtual === null;

  function clearError(field: keyof IngestaoFieldErrors) {
    setFieldErrors((prev) => {
      if (!prev[field]) {
        return prev;
      }
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }

  function handleAnoChange(nextAno: string) {
    setAno(nextAno);
    clearError("ano");
    clearError("questao_inicio");
    clearError("questao_fim");
    setConflito(null);
    setSubmitError(null);

    const trimmed = nextAno.trim();
    if (!/^\d{4}$/.test(trimmed)) {
      if (!faixaEditadaManualmente) {
        setQuestaoInicio("");
        setQuestaoFim("");
      }
      return;
    }

    const numericAno = Number(trimmed);
    if (numericAno < 1900) {
      return;
    }

    const faixa = resolverFaixaPadraoPorAno(numericAno);
    if (faixa !== null) {
      if (!faixaEditadaManualmente) {
        setQuestaoInicio(String(faixa.inicio));
        setQuestaoFim(String(faixa.fim));
      }
    } else {
      if (!faixaEditadaManualmente) {
        setQuestaoInicio("");
        setQuestaoFim("");
      }
      setOpcoesAvancadasAbertas(true);
    }
  }

  function handleQuestaoInicioChange(value: string) {
    setQuestaoInicio(value);
    setFaixaEditadaManualmente(true);
    clearError("questao_inicio");
    clearError("questao_fim");
  }

  function handleQuestaoFimChange(value: string) {
    setQuestaoFim(value);
    setFaixaEditadaManualmente(true);
    clearError("questao_inicio");
    clearError("questao_fim");
  }

  function handleRestaurarFaixaPadrao() {
    if (!faixaPadraoAtual) {
      return;
    }
    setFaixaEditadaManualmente(false);
    setQuestaoInicio(String(faixaPadraoAtual.inicio));
    setQuestaoFim(String(faixaPadraoAtual.fim));
    clearError("questao_inicio");
    clearError("questao_fim");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setConflito(null);
    setSubmitError(null);

    const parsed = parseIngestaoFormValues({
      exame,
      curso,
      ano,
      questao_inicio: questaoInicio,
      questao_fim: questaoFim,
      classificar_automaticamente: classificarAutomaticamente && Boolean(activeTaxonomiaId),
      arquivo_prova: arquivoProva,
      arquivo_gabarito: arquivoGabarito,
    });

    if (!parsed.success) {
      setFieldErrors(parsed.fieldErrors);
      if (parsed.fieldErrors.questao_inicio || parsed.fieldErrors.questao_fim) {
        setOpcoesAvancadasAbertas(true);
      }
      return;
    }

    setFieldErrors({});

    try {
      await criarProvaMutation.mutateAsync({
        arquivo_prova: parsed.data.arquivo_prova,
        arquivo_gabarito: parsed.data.arquivo_gabarito ?? null,
        exame: parsed.data.exame,
        curso: parsed.data.curso,
        ano: parsed.data.ano,
        questao_inicio: parsed.data.questao_inicio,
        questao_fim: parsed.data.questao_fim,
        taxonomia_id:
          parsed.data.classificar_automaticamente && activeTaxonomiaId ? activeTaxonomiaId : null,
        perfil_id:
          parsed.data.classificar_automaticamente && activeTaxonomiaId && defaultPerfil
            ? defaultPerfil.id
            : null,
      });

      onOpenChange(false);
    } catch (error) {
      if (isProvaConflictError(error)) {
        setConflito(error.conflito);
        return;
      }

      setSubmitError(getErrorMessage(error, "Não foi possível iniciar a Ingestão da Prova."));
    }
  }

  const podeClassificarAutomaticamente = Boolean(activeTaxonomiaId);

  return (
    <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-5">
      <div className="space-y-2">
        <Label htmlFor="ingestao-prova-pdf">PDF da Prova</Label>
        <Input
          id="ingestao-prova-pdf"
          type="file"
          accept=".pdf,application/pdf"
          aria-invalid={Boolean(fieldErrors.arquivo_prova)}
          onChange={(event) => {
            setArquivoProva(event.target.files?.[0] ?? null);
            clearError("arquivo_prova");
          }}
        />
        {fieldErrors.arquivo_prova ? (
          <p className="text-xs text-destructive" role="alert">
            {fieldErrors.arquivo_prova}
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Label htmlFor="ingestao-gabarito-pdf">PDF do Gabarito (opcional)</Label>
        <Input
          id="ingestao-gabarito-pdf"
          type="file"
          accept=".pdf,application/pdf"
          aria-invalid={Boolean(fieldErrors.arquivo_gabarito)}
          onChange={(event) => {
            setArquivoGabarito(event.target.files?.[0] ?? null);
            clearError("arquivo_gabarito");
          }}
        />
        {fieldErrors.arquivo_gabarito ? (
          <p className="text-xs text-destructive" role="alert">
            {fieldErrors.arquivo_gabarito}
          </p>
        ) : null}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="ingestao-exame">Exame</Label>
          <Input
            id="ingestao-exame"
            value={exame}
            aria-invalid={Boolean(fieldErrors.exame)}
            onChange={(event) => {
              setExame(event.target.value);
              clearError("exame");
              setConflito(null);
            }}
          />
          {fieldErrors.exame ? (
            <p className="text-xs text-destructive" role="alert">
              {fieldErrors.exame}
            </p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="ingestao-ano">Ano</Label>
          <Input
            id="ingestao-ano"
            type="number"
            inputMode="numeric"
            placeholder="Ex.: 2023"
            value={ano}
            aria-invalid={Boolean(fieldErrors.ano)}
            onChange={(event) => handleAnoChange(event.target.value)}
          />
          {fieldErrors.ano ? (
            <p className="text-xs text-destructive" role="alert">
              {fieldErrors.ano}
            </p>
          ) : null}
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="ingestao-curso">Curso</Label>
        <Input
          id="ingestao-curso"
          value={curso}
          aria-invalid={Boolean(fieldErrors.curso)}
          onChange={(event) => {
            setCurso(event.target.value);
            clearError("curso");
            setConflito(null);
          }}
        />
        {fieldErrors.curso ? (
          <p className="text-xs text-destructive" role="alert">
            {fieldErrors.curso}
          </p>
        ) : null}
      </div>

      <div className="rounded-md border p-3">
        <button
          type="button"
          aria-expanded={opcoesAvancadasAbertas}
          aria-controls={avancadasPanelId}
          onClick={() => setOpcoesAvancadasAbertas((prev) => !prev)}
          className="flex w-full items-center justify-between text-left text-sm font-medium text-foreground"
        >
          <span>Opções avançadas</span>
          {opcoesAvancadasAbertas ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          )}
        </button>

        {opcoesAvancadasAbertas ? (
          <div id={avancadasPanelId} className="mt-3 space-y-3 border-t pt-3">
            {anoSemFaixaPadrao ? (
              <p className="text-xs text-amber-700 dark:text-amber-300">
                Ano {parsedAno} não possui faixa padrão de Componente Específico. Informe início e
                fim manualmente.
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">
                Faixa numérica das Questões de Componente Específico (preenchida automaticamente
                conforme o ano do ENADE).
              </p>
            )}

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="ingestao-questao-inicio">Questão inicial (CE)</Label>
                <Input
                  id="ingestao-questao-inicio"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  value={questaoInicio}
                  aria-invalid={Boolean(fieldErrors.questao_inicio)}
                  onChange={(event) => handleQuestaoInicioChange(event.target.value)}
                />
                {fieldErrors.questao_inicio ? (
                  <p className="text-xs text-destructive" role="alert">
                    {fieldErrors.questao_inicio}
                  </p>
                ) : null}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="ingestao-questao-fim">Questão final (CE)</Label>
                <Input
                  id="ingestao-questao-fim"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  value={questaoFim}
                  aria-invalid={Boolean(fieldErrors.questao_fim)}
                  onChange={(event) => handleQuestaoFimChange(event.target.value)}
                />
                {fieldErrors.questao_fim ? (
                  <p className="text-xs text-destructive" role="alert">
                    {fieldErrors.questao_fim}
                  </p>
                ) : null}
              </div>
            </div>

            {faixaEditadaManualmente && faixaPadraoAtual !== null ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleRestaurarFaixaPadrao}
                className="h-auto px-2 py-1 text-xs"
              >
                Usar padrão do ano ({faixaPadraoAtual.inicio}–{faixaPadraoAtual.fim})
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="space-y-1.5 rounded-md border p-3">
        <div className="flex items-start gap-2.5">
          <Checkbox
            id="ingestao-classificar-auto"
            checked={classificarAutomaticamente && podeClassificarAutomaticamente}
            disabled={!podeClassificarAutomaticamente}
            onCheckedChange={(checked) => setClassificarAutomaticamente(checked === true)}
          />
          <div className="space-y-1 leading-none">
            <Label htmlFor="ingestao-classificar-auto" className="cursor-pointer">
              Classificar automaticamente ao concluir
            </Label>
            <p className="text-xs text-muted-foreground">
              {activeTaxonomia
                ? `Taxonomia: ${activeTaxonomia.nome} · Perfil de Classificação: ${
                    defaultPerfil ? `${defaultPerfil.codigo} (${defaultPerfil.versao})` : "padrão"
                  }`
                : "Selecione uma Taxonomia ativa no cabeçalho para habilitar a Classificação automática."}
            </p>
          </div>
        </div>
      </div>

      {conflito ? (
        <Alert className="border-amber-500/50 bg-amber-500/10">
          <AlertCircle className="h-4 w-4 text-amber-700 dark:text-amber-300" />
          <AlertTitle>Prova já cadastrada</AlertTitle>
          <AlertDescription className="space-y-3">
            <p>{conflito.detail}</p>
            <p className="font-medium text-foreground">
              {conflito.exame} · {conflito.curso} · {conflito.ano}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onSelectAtualizarGabarito(conflito)}
              >
                Atualizar Gabarito
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={() => onSelectReprocessarProva(conflito)}
              >
                Reprocessar Prova
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      ) : null}

      {submitError ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Não foi possível iniciar a Ingestão</AlertTitle>
          <AlertDescription>{submitError}</AlertDescription>
        </Alert>
      ) : null}

      <SheetFooter>
        <Button
          type="button"
          variant="outline"
          disabled={criarProvaMutation.isPending}
          onClick={() => onOpenChange(false)}
        >
          Cancelar
        </Button>
        <Button type="submit" disabled={criarProvaMutation.isPending}>
          {criarProvaMutation.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              Iniciando Ingestão...
            </>
          ) : (
            "Iniciar Ingestão"
          )}
        </Button>
      </SheetFooter>
    </form>
  );
}

export function IngestaoFormDialog({
  open,
  onOpenChange,
  onSelectAtualizarGabarito,
  onSelectReprocessarProva,
}: IngestaoFormDialogProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Nova Ingestão</SheetTitle>
          <SheetDescription>
            Envie o PDF da Prova e, opcionalmente, o Gabarito para extração de Questões,
            Alternativas e Ativos Visuais.
          </SheetDescription>
        </SheetHeader>

        {open ? (
          <IngestaoFormContent
            onOpenChange={onOpenChange}
            onSelectAtualizarGabarito={onSelectAtualizarGabarito}
            onSelectReprocessarProva={onSelectReprocessarProva}
          />
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
