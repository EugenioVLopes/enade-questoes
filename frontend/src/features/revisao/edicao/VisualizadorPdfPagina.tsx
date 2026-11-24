import { useEffect, useState } from "react";
import { AlertCircle, ChevronLeft, ChevronRight, ExternalLink, ZoomIn, ZoomOut } from "lucide-react";

import { urlPaginaProvaImagem, type DetalheQuestaoResponse } from "@/api/edicaoQuestao";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { paginasOrdenadasUnicas } from "@/features/revisao/edicao/editorUtils";

export interface VisualizadorPdfPaginaProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  prova: DetalheQuestaoResponse["prova"];
  numeroQuestao: number;
  paginas: readonly number[];
}

type EstadoImagem = "carregando" | "carregada" | "erro";

export function VisualizadorPdfPagina({
  open,
  onOpenChange,
  prova,
  numeroQuestao,
  paginas,
}: VisualizadorPdfPaginaProps) {
  const paginasLista = paginasOrdenadasUnicas(paginas);
  const chavePaginas = paginasLista.join(",");
  const primeiraPagina = paginasLista[0] ?? 1;

  const [paginaAtual, setPaginaAtual] = useState<number>(primeiraPagina);
  const [estadoImagem, setEstadoImagem] = useState<EstadoImagem>("carregando");
  const [tentativa, setTentativa] = useState(0);
  const [ampliada, setAmpliada] = useState(false);

  useEffect(() => {
    setPaginaAtual(primeiraPagina);
    setEstadoImagem("carregando");
    setTentativa(0);
    setAmpliada(false);
  }, [open, prova.id, chavePaginas, primeiraPagina]);

  const paginaAtiva = paginasLista.includes(paginaAtual) ? paginaAtual : primeiraPagina;
  const indiceAtual = paginasLista.indexOf(paginaAtiva);
  const urlBase = urlPaginaProvaImagem(prova.id, paginaAtiva);
  const src = tentativa > 0 ? `${urlBase}?r=${tentativa}` : urlBase;

  function trocarPagina(novaPagina: number) {
    if (novaPagina === paginaAtiva) {
      return;
    }
    setPaginaAtual(novaPagina);
    setEstadoImagem("carregando");
    setTentativa(0);
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex w-full flex-col gap-4 sm:max-w-2xl lg:max-w-3xl"
      >
        <SheetHeader className="pr-8">
          <SheetTitle>Página original do PDF — Questão Nº {numeroQuestao}</SheetTitle>
          <SheetDescription>
            {prova.exame} · {prova.curso} · {prova.ano}
          </SheetDescription>
        </SheetHeader>

        {paginasLista.length > 1 ? (
          <div
            role="group"
            aria-label="Páginas da Questão"
            className="flex flex-wrap items-center gap-1.5"
          >
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={indiceAtual <= 0}
              onClick={() => {
                if (indiceAtual > 0) {
                  trocarPagina(paginasLista[indiceAtual - 1]);
                }
              }}
            >
              <ChevronLeft className="h-3.5 w-3.5" aria-hidden="true" />
              Página anterior
            </Button>

            {paginasLista.map((p) => (
              <Button
                key={p}
                type="button"
                size="sm"
                variant={p === paginaAtiva ? "default" : "outline"}
                aria-pressed={p === paginaAtiva}
                onClick={() => trocarPagina(p)}
              >
                Página {p}
              </Button>
            ))}

            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={indiceAtual >= paginasLista.length - 1}
              onClick={() => {
                if (indiceAtual >= 0 && indiceAtual < paginasLista.length - 1) {
                  trocarPagina(paginasLista[indiceAtual + 1]);
                }
              }}
            >
              Próxima página
              <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Button>
          </div>
        ) : null}

        {paginasLista.length > 0 ? (
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
            <span className="font-mono text-xs text-muted-foreground">
              {paginasLista.length > 1
                ? `Página ${paginaAtiva} (${indiceAtual + 1}/${paginasLista.length})`
                : `Página ${paginaAtiva}`}
            </span>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                aria-pressed={ampliada}
                onClick={() => setAmpliada((atual) => !atual)}
              >
                {ampliada ? (
                  <ZoomOut className="h-3.5 w-3.5" aria-hidden="true" />
                ) : (
                  <ZoomIn className="h-3.5 w-3.5" aria-hidden="true" />
                )}
                {ampliada ? "Ajustar à largura" : "Ampliar 150%"}
              </Button>
              <Button asChild variant="outline" size="sm">
                <a href={urlBase} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                  Abrir imagem em nova aba
                </a>
              </Button>
            </div>
          </div>
        ) : null}

        <div className="flex-1 overflow-auto rounded-md border border-border bg-surface/40 p-3">
          {paginasLista.length === 0 ? (
            <Alert>
              <AlertDescription>Nenhuma página de PDF associada a esta Questão.</AlertDescription>
            </Alert>
          ) : (
            <>
              {estadoImagem === "carregando" ? (
                <p role="status" className="mb-2 text-xs text-muted-foreground">
                  Carregando página do PDF...
                </p>
              ) : null}
              {estadoImagem === "erro" ? (
                <Alert variant="destructive" role="alert">
                  <AlertCircle className="h-4 w-4" aria-hidden="true" />
                  <AlertDescription className="space-y-3">
                    <p>Não foi possível carregar a imagem desta página do PDF.</p>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setEstadoImagem("carregando");
                        setTentativa((t) => t + 1);
                      }}
                    >
                      Tentar novamente
                    </Button>
                  </AlertDescription>
                </Alert>
              ) : null}
              {estadoImagem !== "erro" ? (
                <img
                  key={`${prova.id}-${paginaAtiva}-${tentativa}`}
                  src={src}
                  alt={`Página ${paginaAtiva} do PDF original da Prova ${prova.exame} ${prova.ano}`}
                  className={
                    ampliada
                      ? "w-[150%] max-w-none rounded border border-border bg-white"
                      : "h-auto w-full rounded border border-border bg-white"
                  }
                  onLoad={() => setEstadoImagem("carregada")}
                  onError={() => setEstadoImagem("erro")}
                />
              ) : null}
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
