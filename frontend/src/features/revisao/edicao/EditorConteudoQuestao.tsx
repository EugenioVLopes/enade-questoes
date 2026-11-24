import { useState, type FormEvent, type ReactNode } from "react";
import { AlertCircle, Loader2 } from "lucide-react";

import {
  useEditarConteudoQuestaoMutation,
  type AlternativaEdicaoRequest,
  type DetalheQuestaoResponse,
  type LetraAlternativa,
  type SituacaoGabarito,
} from "@/api/edicaoQuestao";
import { getErrorMessage, isApiError } from "@/api/errors";
import { MarkdownContent } from "@/components/markdown/MarkdownContent";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { BadgesAlertaExtracao } from "@/features/revisao/edicao/BadgesAlertaExtracao";
import { GerenciadorAtivosVisuais } from "@/features/revisao/edicao/GerenciadorAtivosVisuais";
import {
  LETRAS_ALTERNATIVA,
  normalizarGabaritoEdicao,
  validarEdicaoConteudo,
} from "@/features/revisao/edicao/editorUtils";
import { cn } from "@/lib/utils";

type AbaEnunciado = "editar" | "preview";

const VALOR_ALTERNATIVA_NENHUMA = "__nenhuma__";

const OPCOES_SITUACAO_GABARITO: readonly { valor: SituacaoGabarito; rotulo: string }[] = [
  { valor: "valida", rotulo: "Válida" },
  { valor: "anulada", rotulo: "Anulada" },
  { valor: "pendente", rotulo: "Pendente" },
];

function ordenarAlternativas(alternativas: readonly AlternativaEdicaoRequest[]): AlternativaEdicaoRequest[] {
  const ordem = new Map<LetraAlternativa, number>(
    LETRAS_ALTERNATIVA.map((letra, indice) => [letra, indice]),
  );
  return [...alternativas]
    .map((alt) => ({ letra: alt.letra, texto: alt.texto }))
    .sort(
      (a, b) =>
        (ordem.get(a.letra) ?? Number.MAX_SAFE_INTEGER) -
        (ordem.get(b.letra) ?? Number.MAX_SAFE_INTEGER),
    );
}

export interface EditorConteudoQuestaoProps {
  questao: DetalheQuestaoResponse;
  taxonomiaId: string;
  acoesExtras?: ReactNode;
  revisoesAtivos?: Readonly<Record<string, number>>;
  onVerificarAlerta?: (alertaId: string) => void;
  verificandoAlertaId?: string | null;
  erroAlerta?: string | null;
  onSalvarSucesso: (atualizada: DetalheQuestaoResponse) => void;
  onMidiaAlterada: (opcoes?: { ativoSubstituidoId?: string }) => void;
  onCancelar: () => void;
  onRecarregarQuestao?: () => Promise<DetalheQuestaoResponse | undefined>;
}

export function EditorConteudoQuestao({
  questao,
  taxonomiaId,
  acoesExtras,
  revisoesAtivos,
  onVerificarAlerta,
  verificandoAlertaId,
  erroAlerta,
  onSalvarSucesso,
  onMidiaAlterada,
  onCancelar,
  onRecarregarQuestao,
}: EditorConteudoQuestaoProps) {
  const [questaoSincronizadaId, setQuestaoSincronizadaId] = useState(questao.id);
  const [abaEnunciado, setAbaEnunciado] = useState<AbaEnunciado>("editar");
  const [enunciado, setEnunciado] = useState(questao.enunciado);
  const [alternativas, setAlternativas] = useState<AlternativaEdicaoRequest[]>(() =>
    ordenarAlternativas(questao.alternativas),
  );
  const [situacaoGabarito, setSituacaoGabarito] = useState<SituacaoGabarito>(
    questao.gabarito.situacao_gabarito,
  );
  const [alternativaCorreta, setAlternativaCorreta] = useState<LetraAlternativa | null>(
    questao.gabarito.alternativa_correta ?? null,
  );
  const [mensagemErro, setMensagemErro] = useState<string | null>(null);
  const [conflitoVersao, setConflitoVersao] = useState(false);
  const [recarregando, setRecarregando] = useState(false);

  const editarMutation = useEditarConteudoQuestaoMutation();
  const salvando = editarMutation.isPending;

  function sincronizarComQuestao(alvo: DetalheQuestaoResponse) {
    setQuestaoSincronizadaId(alvo.id);
    setEnunciado(alvo.enunciado);
    setAlternativas(ordenarAlternativas(alvo.alternativas));
    setSituacaoGabarito(alvo.gabarito.situacao_gabarito);
    setAlternativaCorreta(alvo.gabarito.alternativa_correta ?? null);
    setMensagemErro(null);
    setConflitoVersao(false);
  }

  // Reinicia o rascunho somente ao trocar de Questão, preservando o texto digitado
  // quando apenas os Ativos Visuais ou Alertas de Extração são atualizados.
  if (questao.id !== questaoSincronizadaId) {
    sincronizarComQuestao(questao);
    setAbaEnunciado("editar");
  }

  const letrasPresentes = new Set(alternativas.map((alt) => alt.letra));
  const letrasFaltantes = LETRAS_ALTERNATIVA.filter((letra) => !letrasPresentes.has(letra));

  function atualizarTextoAlternativa(letra: LetraAlternativa, texto: string) {
    setAlternativas((atuais) =>
      atuais.map((alt) => (alt.letra === letra ? { ...alt, texto } : alt)),
    );
  }

  function removerAlternativa(letra: LetraAlternativa) {
    setAlternativas((atuais) => {
      if (atuais.length <= 1) {
        return atuais;
      }
      return atuais.filter((alt) => alt.letra !== letra);
    });
  }

  function adicionarLetra(letra: LetraAlternativa) {
    setAlternativas((atuais) => {
      if (atuais.some((alt) => alt.letra === letra)) {
        return atuais;
      }
      return ordenarAlternativas([...atuais, { letra, texto: "" }]);
    });
  }

  function completarLetras() {
    setAlternativas((atuais) => {
      const existentes = new Set(atuais.map((alt) => alt.letra));
      const faltantes = LETRAS_ALTERNATIVA.filter((letra) => !existentes.has(letra)).map(
        (letra): AlternativaEdicaoRequest => ({ letra, texto: "" }),
      );
      if (faltantes.length === 0) {
        return atuais;
      }
      return ordenarAlternativas([...atuais, ...faltantes]);
    });
  }

  function aoMudarSituacao(valor: string) {
    const proxima = valor as SituacaoGabarito;
    setSituacaoGabarito(proxima);
    if (proxima !== "valida") {
      setAlternativaCorreta(null);
    }
  }

  async function salvar() {
    const gabarito = normalizarGabaritoEdicao(situacaoGabarito, alternativaCorreta);
    const erroValidacao = validarEdicaoConteudo({
      enunciado,
      alternativas,
      gabarito,
    });
    if (erroValidacao) {
      setMensagemErro(erroValidacao);
      setConflitoVersao(false);
      return;
    }

    setMensagemErro(null);
    setConflitoVersao(false);

    try {
      const atualizada = await editarMutation.mutateAsync({
        questaoId: questao.id,
        taxonomiaId,
        payload: {
          enunciado,
          alternativas,
          gabarito,
          versao: questao.versao,
        },
      });
      onSalvarSucesso(atualizada);
    } catch (err) {
      setMensagemErro(getErrorMessage(err));
      setConflitoVersao(isApiError(err) && err.status === 409);
    }
  }

  function handleSubmit(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (salvando) {
      return;
    }
    void salvar();
  }

  async function recarregar() {
    if (!onRecarregarQuestao || recarregando) {
      return;
    }
    setRecarregando(true);
    try {
      const atualizada = await onRecarregarQuestao();
      if (atualizada) {
        sincronizarComQuestao(atualizada);
      }
    } catch (err) {
      setMensagemErro(getErrorMessage(err));
    } finally {
      setRecarregando(false);
    }
  }

  return (
    <article
      className="overflow-hidden rounded-lg border border-border bg-card"
      aria-label={`Edição da Questão ${questao.numero}`}
    >
      <header className="space-y-3 border-b border-border bg-surface/40 px-5 py-4 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <p className="font-mono text-xs text-muted-foreground">
              {questao.prova.exame} · {questao.prova.curso} · {questao.prova.ano}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-semibold tracking-[-0.02em] text-foreground">
                Questão Nº {questao.numero}
              </h2>
              <Badge variant="secondary">Modo edição</Badge>
            </div>
          </div>
          {acoesExtras ? <div className="flex flex-wrap items-center gap-2">{acoesExtras}</div> : null}
        </div>
        <BadgesAlertaExtracao
          alertas={questao.alertas_extracao}
          onVerificarAlerta={onVerificarAlerta}
          verificandoAlertaId={verificandoAlertaId}
          erroAlerta={erroAlerta}
        />
      </header>

      <div className="space-y-6 px-5 py-5 sm:px-6 sm:py-6">
        <form onSubmit={handleSubmit} noValidate aria-label="Formulário de edição de conteúdo" className="space-y-6">
          <section className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              {abaEnunciado === "editar" ? (
                <Label htmlFor="editor-enunciado">Enunciado</Label>
              ) : (
                <span className="text-sm font-medium leading-none">Enunciado</span>
              )}
              <div role="tablist" aria-label="Modo do enunciado" className="flex gap-1 border-b border-border">
                <button
                  type="button"
                  role="tab"
                  aria-selected={abaEnunciado === "editar"}
                  className={cn(
                    "-mb-px border-b-2 px-3 py-1.5 text-sm font-medium transition-colors",
                    abaEnunciado === "editar"
                      ? "border-primary text-primary"
                      : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
                  )}
                  onClick={() => setAbaEnunciado("editar")}
                >
                  Editar
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={abaEnunciado === "preview"}
                  className={cn(
                    "-mb-px border-b-2 px-3 py-1.5 text-sm font-medium transition-colors",
                    abaEnunciado === "preview"
                      ? "border-primary text-primary"
                      : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
                  )}
                  onClick={() => setAbaEnunciado("preview")}
                >
                  Preview
                </button>
              </div>
            </div>

            {abaEnunciado === "editar" ? (
              <div className="space-y-1.5">
                <Textarea
                  id="editor-enunciado"
                  aria-label="Enunciado"
                  value={enunciado}
                  onChange={(evento) => setEnunciado(evento.target.value)}
                  rows={8}
                  className="font-mono text-sm"
                />
                <p className="text-xs text-muted-foreground">
                  Suporta Markdown GFM (tabelas, código) e fórmulas KaTeX ($...$ / $$...$$).
                </p>
              </div>
            ) : (
              <div
                data-testid="preview-enunciado"
                className="min-h-[12rem] rounded-md border border-border bg-background/60 p-4"
              >
                {enunciado.trim() === "" ? (
                  <p className="text-sm italic text-muted-foreground">Enunciado vazio.</p>
                ) : (
                  <MarkdownContent source={enunciado} />
                )}
              </div>
            )}
          </section>

          <section className="space-y-3 border-t border-border/70 pt-5">
            <h3 className="text-sm font-semibold text-foreground">Alternativas</h3>
            {alternativas.length > 0 ? (
              <div className="space-y-3">
                {alternativas.map((alt) => (
                  <div key={alt.letra} className="space-y-1.5 rounded-md border border-border bg-background/55 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <Label htmlFor={`editor-alt-${alt.letra}`}>Alternativa {alt.letra}</Label>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-label={`Remover alternativa ${alt.letra}`}
                        disabled={alternativas.length <= 1 || salvando}
                        onClick={() => removerAlternativa(alt.letra)}
                      >
                        Remover
                      </Button>
                    </div>
                    <Textarea
                      id={`editor-alt-${alt.letra}`}
                      aria-label={`Alternativa ${alt.letra}`}
                      value={alt.texto}
                      onChange={(evento) => atualizarTextoAlternativa(alt.letra, evento.target.value)}
                      rows={2}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Nenhuma Alternativa cadastrada.</p>
            )}

            {letrasFaltantes.length > 0 ? (
              <div className="flex flex-wrap items-center gap-2">
                {letrasFaltantes.map((letra) => (
                  <Button
                    key={letra}
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={salvando}
                    onClick={() => adicionarLetra(letra)}
                  >
                    Adicionar alternativa {letra}
                  </Button>
                ))}
                {letrasFaltantes.length >= 2 ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={salvando}
                    onClick={completarLetras}
                  >
                    Completar A–E
                  </Button>
                ) : null}
              </div>
            ) : null}
          </section>

          <section className="space-y-3 border-t border-border/70 pt-5">
            <h3 className="text-sm font-semibold text-foreground">Gabarito</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="editor-situacao-gabarito">Situação do Gabarito</Label>
                <Select value={situacaoGabarito} onValueChange={aoMudarSituacao} disabled={salvando}>
                  <SelectTrigger id="editor-situacao-gabarito" aria-label="Situação do Gabarito">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {OPCOES_SITUACAO_GABARITO.map((opcao) => (
                      <SelectItem key={opcao.valor} value={opcao.valor}>
                        {opcao.rotulo}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="editor-alt-correta">Alternativa correta</Label>
                <Select
                  value={alternativaCorreta ?? VALOR_ALTERNATIVA_NENHUMA}
                  onValueChange={(v) =>
                    setAlternativaCorreta(v === VALOR_ALTERNATIVA_NENHUMA ? null : (v as LetraAlternativa))
                  }
                  disabled={situacaoGabarito !== "valida" || salvando}
                >
                  <SelectTrigger id="editor-alt-correta" aria-label="Alternativa correta">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={VALOR_ALTERNATIVA_NENHUMA}>Selecione</SelectItem>
                    {LETRAS_ALTERNATIVA.map((letra) => (
                      <SelectItem key={letra} value={letra}>
                        {letra}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </section>

          {mensagemErro ? (
            <Alert variant="destructive" role="alert">
              <AlertCircle className="h-4 w-4" aria-hidden="true" />
              <AlertDescription className="space-y-2">
                <p>{mensagemErro}</p>
                {conflitoVersao && onRecarregarQuestao ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={recarregando || salvando}
                    onClick={() => void recarregar()}
                  >
                    {recarregando ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : null}
                    Recarregar dados atuais
                  </Button>
                ) : null}
              </AlertDescription>
            </Alert>
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" disabled={salvando}>
              {salvando ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
              Salvar alterações
            </Button>
            <Button type="button" variant="outline" disabled={salvando} onClick={onCancelar}>
              Cancelar
            </Button>
          </div>
        </form>

        <Separator />

        <section aria-label="Ativos Visuais" className="space-y-3">
          <h3 className="text-sm font-semibold text-foreground">Ativos Visuais</h3>
          <GerenciadorAtivosVisuais
            questaoId={questao.id}
            ativos={questao.ativos_visuais}
            revisoesAtivos={revisoesAtivos}
            onMidiaAlterada={onMidiaAlterada}
          />
        </section>
      </div>
    </article>
  );
}
