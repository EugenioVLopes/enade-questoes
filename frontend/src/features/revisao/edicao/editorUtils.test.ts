import { describe, expect, it } from "vitest";

import type { AtivoVisualResponse, LetraAlternativa } from "@/api/edicaoQuestao";
import {
  LIMITE_ALTERNATIVA,
  LIMITE_ENUNCIADO,
  TAMANHO_MAXIMO_IMAGEM_BYTES,
  calcularReordenacaoAtivos,
  ehAlertaInspecao,
  normalizarGabaritoEdicao,
  paginasOrdenadasUnicas,
  urlAtivoComRevisao,
  validarArquivoImagem,
  validarEdicaoConteudo,
} from "@/features/revisao/edicao/editorUtils";

function ativo(id: string, ordem: number): AtivoVisualResponse {
  return {
    id,
    origem: "picture_docling",
    alternativa_letra: null,
    ordem,
    pagina: 1,
    url_arquivo: `/api/v1/ativos-visuais/${id}/arquivo`,
  };
}

function alternativasCompletas() {
  return (["A", "B", "C", "D", "E"] as const).map((letra) => ({
    letra,
    texto: `Texto da alternativa ${letra}`,
  }));
}

describe("validarEdicaoConteudo", () => {
  it("aceita conteúdo válido completo e Gabarito válido", () => {
    expect(
      validarEdicaoConteudo({
        enunciado: "Enunciado válido da questão.",
        alternativas: alternativasCompletas(),
        gabarito: { situacao_gabarito: "valida", alternativa_correta: "C" },
      }),
    ).toBeNull();
  });

  it("aceita enunciado e alternativas exatamente nos limites máximos", () => {
    expect(
      validarEdicaoConteudo({
        enunciado: "a".repeat(LIMITE_ENUNCIADO),
        alternativas: [{ letra: "A", texto: "b".repeat(LIMITE_ALTERNATIVA) }],
        gabarito: { situacao_gabarito: "pendente", alternativa_correta: null },
      }),
    ).toBeNull();
  });

  it("rejeita enunciado vazio ou só com espaços", () => {
    expect(
      validarEdicaoConteudo({
        enunciado: "   \n\t ",
        alternativas: alternativasCompletas(),
        gabarito: { situacao_gabarito: "valida", alternativa_correta: "A" },
      }),
    ).toBe("O enunciado não pode ficar vazio.");
  });

  it("rejeita enunciado acima do limite de 20.000 caracteres", () => {
    expect(
      validarEdicaoConteudo({
        enunciado: "x".repeat(LIMITE_ENUNCIADO + 1),
        alternativas: alternativasCompletas(),
        gabarito: { situacao_gabarito: "valida", alternativa_correta: "A" },
      }),
    ).toBe("O enunciado excede o limite de 20.000 caracteres.");
  });

  it("exige ao menos uma Alternativa por padrão e permite lista vazia quando exigirAlternativa=false", () => {
    expect(
      validarEdicaoConteudo({
        enunciado: "Questão objetiva",
        alternativas: [],
        gabarito: { situacao_gabarito: "pendente", alternativa_correta: null },
      }),
    ).toBe("Informe ao menos uma Alternativa.");

    expect(
      validarEdicaoConteudo({
        enunciado: "Questão discursiva",
        alternativas: [],
        gabarito: { situacao_gabarito: "pendente", alternativa_correta: null },
        exigirAlternativa: false,
      }),
    ).toBeNull();
  });

  it("rejeita letra inválida, duplicada ou texto acima de 5.000 caracteres", () => {
    expect(
      validarEdicaoConteudo({
        enunciado: "Enunciado",
        alternativas: [{ letra: "F" as LetraAlternativa, texto: "Inválida" }],
        gabarito: { situacao_gabarito: "pendente", alternativa_correta: null },
      }),
    ).toBe("Letra de Alternativa inválida: F.");

    expect(
      validarEdicaoConteudo({
        enunciado: "Enunciado",
        alternativas: [
          { letra: "B", texto: "Primeira" },
          { letra: "B", texto: "Segunda" },
        ],
        gabarito: { situacao_gabarito: "pendente", alternativa_correta: null },
      }),
    ).toBe("Letra de Alternativa duplicada: B.");

    expect(
      validarEdicaoConteudo({
        enunciado: "Enunciado",
        alternativas: [{ letra: "D", texto: "z".repeat(LIMITE_ALTERNATIVA + 1) }],
        gabarito: { situacao_gabarito: "pendente", alternativa_correta: null },
      }),
    ).toBe("A Alternativa D excede o limite de 5.000 caracteres.");
  });

  it("valida consistência entre situação do Gabarito e alternativa_correta", () => {
    expect(
      validarEdicaoConteudo({
        enunciado: "Enunciado",
        alternativas: alternativasCompletas(),
        gabarito: { situacao_gabarito: "valida", alternativa_correta: null },
      }),
    ).toBe("Selecione a Alternativa correta para um Gabarito válido.");

    expect(
      validarEdicaoConteudo({
        enunciado: "Enunciado",
        alternativas: alternativasCompletas(),
        gabarito: { situacao_gabarito: "anulada", alternativa_correta: "A" },
      }),
    ).toBe("Gabarito anulado ou pendente não deve ter Alternativa correta.");

    expect(
      validarEdicaoConteudo({
        enunciado: "Enunciado",
        alternativas: alternativasCompletas(),
        gabarito: { situacao_gabarito: "pendente", alternativa_correta: "E" },
      }),
    ).toBe("Gabarito anulado ou pendente não deve ter Alternativa correta.");
  });
});

describe("normalizarGabaritoEdicao", () => {
  it("preserva alternativa_correta quando situação é valida e zera em anulada/pendente", () => {
    expect(normalizarGabaritoEdicao("valida", "E")).toEqual({
      situacao_gabarito: "valida",
      alternativa_correta: "E",
    });
    expect(normalizarGabaritoEdicao("valida", null)).toEqual({
      situacao_gabarito: "valida",
      alternativa_correta: null,
    });
    expect(normalizarGabaritoEdicao("anulada", "B")).toEqual({
      situacao_gabarito: "anulada",
      alternativa_correta: null,
    });
    expect(normalizarGabaritoEdicao("pendente", "C")).toEqual({
      situacao_gabarito: "pendente",
      alternativa_correta: null,
    });
  });
});

describe("validarArquivoImagem", () => {
  it("aceita PNG e JPEG válidos inclusive exatamente no limite de 10 MB", () => {
    const png = new File(["png"], "diagrama.png", { type: "image/png" });
    const jpeg = new File(["jpg"], "foto.jpeg", { type: "image/jpeg" });
    const jpg = new File(["jpg"], "foto.jpg", { type: "image/jpg" });
    const limiteExato = new File([new Uint8Array(TAMANHO_MAXIMO_IMAGEM_BYTES)], "grande.png", {
      type: "image/png",
    });

    expect(validarArquivoImagem(png)).toBeNull();
    expect(validarArquivoImagem(jpeg)).toBeNull();
    expect(validarArquivoImagem(jpg)).toBeNull();
    expect(validarArquivoImagem(limiteExato)).toBeNull();
  });

  it("faz fallback por extensão quando type está vazio", () => {
    expect(validarArquivoImagem(new File(["ok"], "figura.png", { type: "" }))).toBeNull();
    expect(validarArquivoImagem(new File(["ok"], "figura.jpg", { type: "" }))).toBeNull();
    expect(validarArquivoImagem(new File(["ok"], "FIGURA.JPEG", { type: "" }))).toBeNull();
    expect(validarArquivoImagem(new File(["ok"], "notas.txt", { type: "" }))).toBe(
      "Envie uma imagem no formato PNG ou JPEG.",
    );
    expect(validarArquivoImagem(new File(["ok"], "animado.gif", { type: "" }))).toBe(
      "Envie uma imagem no formato PNG ou JPEG.",
    );
  });

  it("rejeita ausência de arquivo, arquivo vazio, arquivo acima de 10 MB e formatos .txt/.gif", () => {
    expect(validarArquivoImagem(null)).toBe("Selecione uma imagem no formato PNG ou JPEG.");
    expect(validarArquivoImagem(new File([], "vazio.png", { type: "image/png" }))).toBe(
      "O arquivo selecionado está vazio.",
    );
    expect(
      validarArquivoImagem(
        new File([new Uint8Array(TAMANHO_MAXIMO_IMAGEM_BYTES + 1)], "enorme.jpg", {
          type: "image/jpeg",
        }),
      ),
    ).toBe("A imagem excede o limite de 10 MB.");
    expect(validarArquivoImagem(new File(["texto"], "doc.txt", { type: "text/plain" }))).toBe(
      "Envie uma imagem no formato PNG ou JPEG.",
    );
    expect(validarArquivoImagem(new File(["gif"], "anim.gif", { type: "image/gif" }))).toBe(
      "Envie uma imagem no formato PNG ou JPEG.",
    );
  });
});

describe("calcularReordenacaoAtivos", () => {
  it("calcula atualizações ao subir e descer itens contíguos", () => {
    const lista = [ativo("a", 0), ativo("b", 1), ativo("c", 2)];

    expect(calcularReordenacaoAtivos(lista, "b", "subir")).toEqual([
      { ativoId: "b", ordem: 0 },
      { ativoId: "a", ordem: 1 },
    ]);
    expect(calcularReordenacaoAtivos(lista, "b", "descer")).toEqual([
      { ativoId: "c", ordem: 1 },
      { ativoId: "b", ordem: 2 },
    ]);
  });

  it("retorna lista vazia nos extremos ou quando o ativo não existe", () => {
    const lista = [ativo("a", 0), ativo("b", 1)];

    expect(calcularReordenacaoAtivos(lista, "a", "subir")).toEqual([]);
    expect(calcularReordenacaoAtivos(lista, "b", "descer")).toEqual([]);
    expect(calcularReordenacaoAtivos(lista, "inexistente", "subir")).toEqual([]);
    expect(calcularReordenacaoAtivos([ativo("unico", 0)], "unico", "descer")).toEqual([]);
  });

  it("normaliza ordens quando há empates [0, 0] ou saltos [0, 5, 9]", () => {
    const empates = [ativo("a", 0), ativo("b", 0)];
    expect(calcularReordenacaoAtivos(empates, "b", "subir")).toEqual([{ ativoId: "a", ordem: 1 }]);
    expect(calcularReordenacaoAtivos(empates, "a", "descer")).toEqual([{ ativoId: "a", ordem: 1 }]);

    const saltos = [ativo("a", 0), ativo("b", 5), ativo("c", 9)];
    expect(calcularReordenacaoAtivos(saltos, "b", "subir")).toEqual([
      { ativoId: "b", ordem: 0 },
      { ativoId: "a", ordem: 1 },
      { ativoId: "c", ordem: 2 },
    ]);
    expect(calcularReordenacaoAtivos(saltos, "c", "subir")).toEqual([
      { ativoId: "c", ordem: 1 },
      { ativoId: "b", ordem: 2 },
    ]);
  });
});

describe("urlAtivoComRevisao", () => {
  it("mantém a URL sem revisão positiva e acrescenta ?v= ou &v= quando houver revisão", () => {
    expect(urlAtivoComRevisao("/api/v1/ativos-visuais/1/arquivo")).toBe(
      "/api/v1/ativos-visuais/1/arquivo",
    );
    expect(urlAtivoComRevisao("/api/v1/ativos-visuais/1/arquivo", 0)).toBe(
      "/api/v1/ativos-visuais/1/arquivo",
    );
    expect(urlAtivoComRevisao("/api/v1/ativos-visuais/1/arquivo", -2)).toBe(
      "/api/v1/ativos-visuais/1/arquivo",
    );
    expect(urlAtivoComRevisao("/api/v1/ativos-visuais/1/arquivo", 3)).toBe(
      "/api/v1/ativos-visuais/1/arquivo?v=3",
    );
    expect(urlAtivoComRevisao("/api/v1/ativos-visuais/1/arquivo?token=xyz", 4)).toBe(
      "/api/v1/ativos-visuais/1/arquivo?token=xyz&v=4",
    );
  });
});

describe("ehAlertaInspecao", () => {
  it("retorna true apenas para alertas de inspeção visual", () => {
    expect(ehAlertaInspecao("pdf_via_ocr")).toBe(true);
    expect(ehAlertaInspecao("fonte_symbol_detectada")).toBe(true);
    expect(ehAlertaInspecao("formula_nao_decodificada")).toBe(false);
    expect(ehAlertaInspecao("alternativas_incompletas")).toBe(false);
    expect(ehAlertaInspecao("enunciado_suspeito")).toBe(false);
    expect(ehAlertaInspecao("gabarito_ausente_na_prova")).toBe(false);
  });
});

describe("paginasOrdenadasUnicas", () => {
  it("remove duplicatas e inválidos e ordena numericamente em ordem crescente", () => {
    expect(paginasOrdenadasUnicas([29, 2, 28, 2, 0, -1, 1.5, Number.NaN, 10])).toEqual([
      2, 10, 28, 29,
    ]);
    expect(paginasOrdenadasUnicas([])).toEqual([]);
  });
});
