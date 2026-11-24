import type {
  AlertaExtracaoResponse,
  AlternativaEdicaoRequest,
  AtivoVisualResponse,
  GabaritoEdicaoRequest,
  LetraAlternativa,
  OrigemAtivoVisual,
  SituacaoGabarito,
} from "@/api/edicaoQuestao";

export const LETRAS_ALTERNATIVA: readonly LetraAlternativa[] = ["A", "B", "C", "D", "E"];
export const LIMITE_ENUNCIADO = 20_000;
export const LIMITE_ALTERNATIVA = 5_000;
export const TAMANHO_MAXIMO_IMAGEM_BYTES = 10 * 1024 * 1024;

export const ROTULOS_ALERTA: Record<AlertaExtracaoResponse["codigo"], string> = {
  formula_nao_decodificada: "Fórmula não decodificada",
  alternativas_incompletas: "Alternativas incompletas",
  pdf_via_ocr: "PDF lido via OCR",
  enunciado_suspeito: "Enunciado suspeito",
  fonte_symbol_detectada: "Fonte Symbol detectada",
  gabarito_ausente_na_prova: "Gabarito ausente na Prova",
};

export const ROTULOS_ORIGEM_ATIVO: Record<OrigemAtivoVisual, string> = {
  picture_docling: "Docling",
  formula_recorte: "Recorte de fórmula",
  upload_manual: "Upload manual",
};

const MIME_IMAGEM_ACEITOS = new Set(["image/png", "image/jpeg", "image/jpg"]);
const EXTENSOES_IMAGEM_ACEITAS = [".png", ".jpg", ".jpeg"];

export function ehAlertaInspecao(codigo: AlertaExtracaoResponse["codigo"]): boolean {
  return codigo === "pdf_via_ocr" || codigo === "fonte_symbol_detectada";
}

export function urlAtivoComRevisao(urlArquivo: string, revisao?: number): string {
  if (!revisao || revisao <= 0) {
    return urlArquivo;
  }
  const separador = urlArquivo.includes("?") ? "&" : "?";
  return `${urlArquivo}${separador}v=${revisao}`;
}

export function validarArquivoImagem(arquivo: File | null): string | null {
  if (!arquivo) {
    return "Selecione uma imagem no formato PNG ou JPEG.";
  }
  if (arquivo.size === 0) {
    return "O arquivo selecionado está vazio.";
  }
  if (arquivo.size > TAMANHO_MAXIMO_IMAGEM_BYTES) {
    return "A imagem excede o limite de 10 MB.";
  }

  const tipo = arquivo.type.trim().toLowerCase();
  if (tipo === "") {
    const nome = arquivo.name.trim().toLowerCase();
    const extensaoValida = EXTENSOES_IMAGEM_ACEITAS.some((extensao) => nome.endsWith(extensao));
    if (!extensaoValida) {
      return "Envie uma imagem no formato PNG ou JPEG.";
    }
  } else if (!MIME_IMAGEM_ACEITOS.has(tipo)) {
    return "Envie uma imagem no formato PNG ou JPEG.";
  }

  return null;
}

export function normalizarGabaritoEdicao(
  situacao: SituacaoGabarito,
  alternativaCorreta: LetraAlternativa | null,
): GabaritoEdicaoRequest {
  return {
    situacao_gabarito: situacao,
    alternativa_correta: situacao === "valida" ? alternativaCorreta : null,
  };
}

export function validarEdicaoConteudo(entrada: {
  enunciado: string;
  alternativas: readonly AlternativaEdicaoRequest[];
  gabarito: GabaritoEdicaoRequest;
  exigirAlternativa?: boolean;
}): string | null {
  if (entrada.enunciado.trim().length === 0) {
    return "O enunciado não pode ficar vazio.";
  }
  if (entrada.enunciado.length > LIMITE_ENUNCIADO) {
    return "O enunciado excede o limite de 20.000 caracteres.";
  }
  if ((entrada.exigirAlternativa ?? true) && entrada.alternativas.length === 0) {
    return "Informe ao menos uma Alternativa.";
  }

  const letrasVistas = new Set<LetraAlternativa>();
  for (const alternativa of entrada.alternativas) {
    if (!LETRAS_ALTERNATIVA.includes(alternativa.letra)) {
      return `Letra de Alternativa inválida: ${alternativa.letra}.`;
    }
    if (letrasVistas.has(alternativa.letra)) {
      return `Letra de Alternativa duplicada: ${alternativa.letra}.`;
    }
    letrasVistas.add(alternativa.letra);
    if (alternativa.texto.length > LIMITE_ALTERNATIVA) {
      return `A Alternativa ${alternativa.letra} excede o limite de 5.000 caracteres.`;
    }
  }

  if (entrada.gabarito.situacao_gabarito === "valida" && !entrada.gabarito.alternativa_correta) {
    return "Selecione a Alternativa correta para um Gabarito válido.";
  }
  if (entrada.gabarito.situacao_gabarito !== "valida" && entrada.gabarito.alternativa_correta != null) {
    return "Gabarito anulado ou pendente não deve ter Alternativa correta.";
  }

  return null;
}

export function calcularReordenacaoAtivos(
  ativos: readonly AtivoVisualResponse[],
  ativoId: string,
  direcao: "subir" | "descer",
): { ativoId: string; ordem: number }[] {
  const indice = ativos.findIndex((item) => item.id === ativoId);
  const destino = direcao === "subir" ? indice - 1 : indice + 1;
  if (indice < 0 || destino < 0 || destino >= ativos.length) {
    return [];
  }

  const reordenados = [...ativos];
  const atual = reordenados[indice];
  reordenados[indice] = reordenados[destino];
  reordenados[destino] = atual;

  const atualizacoes: { ativoId: string; ordem: number }[] = [];
  for (let pos = 0; pos < reordenados.length; pos += 1) {
    const item = reordenados[pos];
    if (item.ordem !== pos) {
      atualizacoes.push({ ativoId: item.id, ordem: pos });
    }
  }
  return atualizacoes;
}

export function paginasOrdenadasUnicas(paginas: readonly number[]): number[] {
  const unicas = new Set<number>();
  for (const pagina of paginas) {
    if (Number.isInteger(pagina) && pagina >= 1) {
      unicas.add(pagina);
    }
  }
  return [...unicas].sort((a, b) => a - b);
}
