import type { DetalheQuestaoResponse } from "@/api/revisao";

export function rotuloGabarito(gabarito: DetalheQuestaoResponse["gabarito"]): string {
  if (gabarito.situacao_gabarito === "anulada") {
    return "ANULADA";
  }
  if (gabarito.situacao_gabarito === "valida" && gabarito.alternativa_correta) {
    return gabarito.alternativa_correta;
  }
  return "pendente";
}

/** Formato do "Copiar questão em Markdown": cabeçalho, enunciado, alternativas e linha de Gabarito. */
export function montarQuestaoMarkdown(questao: DetalheQuestaoResponse): string {
  const { prova } = questao;
  const alternativas = questao.alternativas.map((alt) => `**${alt.letra})** ${alt.texto}`);
  return [
    `## Questão ${questao.numero} — ${prova.exame} ${prova.curso} ${prova.ano}`,
    questao.enunciado,
    ...(alternativas.length > 0 ? [alternativas.join("\n\n")] : []),
    `Gabarito: ${rotuloGabarito(questao.gabarito)}`,
  ].join("\n\n");
}
