import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DetalheQuestaoResponse } from "@/api/revisao";
import type { TaxonomiaResponse } from "@/api/taxonomias";
import { PainelVeredito } from "@/features/revisao/PainelVeredito";

function taxonomia(id: string): TaxonomiaResponse {
  return {
    id,
    codigo: id,
    nome: id,
    curso_referencia: "Computação",
    disciplinas: [{ id: `d-${id}`, taxonomia_id: id, codigo: "redes", nome: "Redes", ementa: "", ativa: true, classificacoes_vigentes_impactadas: 0 }],
  } as TaxonomiaResponse;
}

const questao = {
  id: "q1",
  classificacao_vigente: {
    id: "c1",
    disciplina_principal: "redes",
    disciplinas_secundarias: [],
    topicos: [],
    justificativa: "Original.",
    confianca: 0.5,
    origem: "automatica",
    status: "pendente_revisao",
    vigente: true,
    revisao_prioritaria: false,
  },
  divergencia_aberta: null,
  disciplinas_arquivadas_em_uso: [],
  historico: [],
  outras_taxonomias: [],
} as unknown as DetalheQuestaoResponse;

function painel(tax: TaxonomiaResponse) {
  return (
    <PainelVeredito
      questao={questao}
      taxonomia={tax}
      nomes={new Map([["redes", "Redes"]])}
      editando
      onEditandoChange={vi.fn()}
      ocupado={false}
      erro={null}
      onAprovar={vi.fn()}
      onCorrigir={vi.fn()}
      onResolver={vi.fn()}
      onExecutarClassificacao={vi.fn()}
      execucao={{ enviando: false, erro: null, criadaId: null, semPerfil: false }}
    />
  );
}

describe("PainelVeredito", () => {
  it("G4: o formulário de edição reinicia ao trocar de Taxonomia", async () => {
    const user = userEvent.setup();
    const { rerender } = render(painel(taxonomia("tax-a")));
    const justificativa = screen.getByLabelText("Justificativa");
    await user.clear(justificativa);
    await user.type(justificativa, "Digitado na Taxonomia A");
    expect(screen.getByLabelText("Justificativa")).toHaveValue("Digitado na Taxonomia A");

    rerender(painel(taxonomia("tax-b")));
    expect(screen.getByLabelText("Justificativa")).toHaveValue("Original.");
  });
});
