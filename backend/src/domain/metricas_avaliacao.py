"""Calculador determinístico das 3 camadas de métricas e avaliador de gate de regressão."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from domain.avaliacao import (
    AvaliacaoClassificacao,
    ChaveQuestaoOuro,
    ConjuntoOuro,
    DivergenciaAvaliacao,
    ItemDiffGate,
    MetricasCamada1,
    MetricasCamada2,
    MetricasCamada3,
    ParConfusao,
    PredicaoClassificacao,
    ResultadoGate,
    ResultadoItemAvaliacao,
)
from domain.exceptions import ErroInvarianteDominio, ErroValidacaoDominio

TOLERANCIA_FLOAT_GATE = 1e-9
LIMIAR_ALTA_CONFIANCA = 0.85
LIMIAR_PISO_CONCLUSAO_VALIDA = 1.0
LIMIAR_PISO_PRIMEIRA_TENTATIVA = 0.95
QUEDA_MAX_MACRO_F1_PADRAO = 0.02
QUEDA_MAX_JACCARD_PADRAO = 0.03
QUEDA_MAX_ACURACIA_MIGRACAO = 0.02
QUEDA_MAX_JACCARD_MIGRACAO = 0.05
ROTULO_PREDICAO_INVALIDA = "<invalida>"


def _metricas_secundarias(esperadas: set[str], preditas: set[str]) -> tuple[float, float]:
    if not esperadas and not preditas:
        return 1.0, 1.0
    intersecao = len(esperadas & preditas)
    uniao = len(esperadas | preditas)
    jaccard = intersecao / uniao if uniao > 0 else 0.0
    denom_f1 = len(esperadas) + len(preditas)
    f1 = (2.0 * intersecao) / denom_f1 if denom_f1 > 0 else 0.0
    return jaccard, f1


def _percentil_95(valores: Sequence[float]) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    indice = max(0, math.ceil(0.95 * len(ordenados)) - 1)
    return ordenados[indice]


def calcular_avaliacao_classificacao(
    conjunto_ouro: ConjuntoOuro,
    predicoes: Sequence[PredicaoClassificacao],
    *,
    perfil_codigo: str,
    perfil_versao: str,
    modelo_identidade: str,
    executado_em: datetime,
    max_chars_justificativa: int = 160,
) -> AvaliacaoClassificacao:
    """Calcula as 3 camadas determinísticas de métricas sobre o Conjunto-Ouro."""
    if conjunto_ouro.total_itens == 0:
        raise ErroValidacaoDominio("ConjuntoOuro vazio não pode ser avaliado.")

    pred_por_chave: dict[ChaveQuestaoOuro, PredicaoClassificacao] = {}
    for pred in predicoes:
        if pred.chave in pred_por_chave:
            raise ErroValidacaoDominio(f"Predição duplicada para chave {pred.chave.as_tuple()}.")
        pred_por_chave[pred.chave] = pred

    chaves_ouro = {item.chave for item in conjunto_ouro.itens}
    if set(pred_por_chave) != chaves_ouro:
        faltantes = sorted(c.as_tuple() for c in (chaves_ouro - set(pred_por_chave)))
        extras = sorted(c.as_tuple() for c in (set(pred_por_chave) - chaves_ouro))
        raise ErroValidacaoDominio(
            f"Predições incompatíveis com ConjuntoOuro (faltantes={faltantes}, extras={extras})."
        )

    resultados_itens: list[ResultadoItemAvaliacao] = []
    divergencias: list[DivergenciaAvaliacao] = []
    matriz: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    acertos_principal = 0
    soma_jaccard = 0.0
    soma_f1_sec = 0.0
    acertos_exact = 0

    total_validas = 0
    validas_primeira_tentativa = 0
    total_revisao_prioritaria = 0
    total_alta_confianca = 0
    erros_alta_confianca = 0
    prompt_tokens = 0
    completion_tokens = 0
    cache_hits = 0
    latencias: list[float] = []
    itens_multipass = 0
    itens_multipass_estaveis = 0

    for item in conjunto_ouro.itens:
        pred = pred_por_chave[item.chave]
        sec_gold = set(item.disciplinas_secundarias)

        if pred.conclusao_valida and pred.disciplina_principal is not None:
            total_validas += 1
            pred_principal_rotulo = pred.disciplina_principal
            principal_correta = pred.disciplina_principal == item.disciplina_principal
            sec_pred = set(pred.disciplinas_secundarias)
            jaccard, f1_sec = _metricas_secundarias(sec_gold, sec_pred)
            exact_match = principal_correta and (sec_gold == sec_pred)

            if pred.tentativas == 1 and not pred.houve_saneamento:
                validas_primeira_tentativa += 1
            if pred.revisao_prioritaria:
                total_revisao_prioritaria += 1
            if pred.confianca >= LIMIAR_ALTA_CONFIANCA:
                total_alta_confianca += 1
                if not principal_correta:
                    erros_alta_confianca += 1
        else:
            pred_principal_rotulo = ROTULO_PREDICAO_INVALIDA
            principal_correta = False
            jaccard = 0.0
            f1_sec = 0.0
            exact_match = False

        if principal_correta:
            acertos_principal += 1
        if exact_match:
            acertos_exact += 1
        soma_jaccard += jaccard
        soma_f1_sec += f1_sec

        matriz[item.disciplina_principal][pred_principal_rotulo] += 1

        if not exact_match:
            justificativa_limpa = pred.justificativa.strip()
            if max_chars_justificativa <= 0:
                trecho = ""
            elif len(justificativa_limpa) <= max_chars_justificativa:
                trecho = justificativa_limpa
            elif max_chars_justificativa < 3:
                trecho = justificativa_limpa[:max_chars_justificativa]
            else:
                trecho = f"{justificativa_limpa[: max_chars_justificativa - 3]}..."
            divergencias.append(
                DivergenciaAvaliacao(
                    chave=item.chave,
                    esperada_principal=item.disciplina_principal,
                    esperadas_secundarias=item.disciplinas_secundarias,
                    predita_principal=pred.disciplina_principal,
                    preditas_secundarias=pred.disciplinas_secundarias,
                    confianca=pred.confianca,
                    revisao_prioritaria=pred.revisao_prioritaria,
                    trecho_justificativa=trecho,
                )
            )

        prompt_tokens += pred.prompt_tokens
        completion_tokens += pred.completion_tokens
        if pred.from_cache:
            cache_hits += 1
        latencias.append(pred.latencia_ms)

        if len(pred.passes) > 1:
            itens_multipass += 1
            normalizados = {(p_princ, frozenset(p_secs)) for p_princ, p_secs in pred.passes}
            if len(normalizados) == 1:
                itens_multipass_estaveis += 1

        resultados_itens.append(
            ResultadoItemAvaliacao(
                chave=item.chave,
                esperada_principal=item.disciplina_principal,
                esperadas_secundarias=item.disciplinas_secundarias,
                predita_principal=pred.disciplina_principal,
                preditas_secundarias=pred.disciplinas_secundarias,
                conclusao_valida=pred.conclusao_valida,
                principal_correta=principal_correta,
                jaccard_secundarias=jaccard,
                f1_secundarias=f1_sec,
                exact_match=exact_match,
                confianca=pred.confianca,
                revisao_prioritaria=pred.revisao_prioritaria,
                justificativa=pred.justificativa,
            )
        )

    total = conjunto_ouro.total_itens
    classes_ouro = sorted({item.disciplina_principal for item in conjunto_ouro.itens})
    f1_por_classe: list[float] = []
    for classe in classes_ouro:
        tp = sum(
            1
            for res in resultados_itens
            if res.esperada_principal == classe and res.conclusao_valida and res.predita_principal == classe
        )
        fp = sum(
            1
            for res in resultados_itens
            if res.esperada_principal != classe and res.conclusao_valida and res.predita_principal == classe
        )
        fn = sum(
            1
            for res in resultados_itens
            if res.esperada_principal == classe and (not res.conclusao_valida or res.predita_principal != classe)
        )
        denom = 2 * tp + fp + fn
        f1_por_classe.append((2.0 * tp / denom) if denom > 0 else 0.0)

    camada1 = MetricasCamada1(
        total_itens=total,
        acuracia_principal=acertos_principal / total,
        macro_f1_principal=sum(f1_por_classe) / len(classes_ouro),
        jaccard_secundarias=soma_jaccard / total,
        f1_secundarias=soma_f1_sec / total,
        exact_match=acertos_exact / total,
    )

    pares_fora_diagonal: list[ParConfusao] = []
    for esperada, preditas in matriz.items():
        for predita, contagem in preditas.items():
            if esperada != predita and contagem > 0:
                pares_fora_diagonal.append(ParConfusao(esperada=esperada, predita=predita, contagem=contagem))
    pares_fora_diagonal.sort(key=lambda par: (-par.contagem, par.esperada, par.predita))

    camada2 = MetricasCamada2(
        matriz_confusao={k: dict(v) for k, v in sorted(matriz.items())},
        pares_confusao_ranqueados=tuple(pares_fora_diagonal),
        divergencias=tuple(divergencias),
    )

    camada3 = MetricasCamada3(
        conclusao_valida=total_validas / total,
        validade_primeira_tentativa=validas_primeira_tentativa / total,
        taxa_revisao_prioritaria=(total_revisao_prioritaria / total_validas) if total_validas > 0 else 0.0,
        taxa_erro_alta_confianca=(erros_alta_confianca / total_alta_confianca) if total_alta_confianca > 0 else 0.0,
        total_alta_confianca=total_alta_confianca,
        erros_alta_confianca=erros_alta_confianca,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cache_hits=cache_hits,
        cache_hit_rate=cache_hits / total,
        latencia_media_ms=sum(latencias) / len(latencias),
        latencia_p95_ms=_percentil_95(latencias),
        estabilidade_multipass=(itens_multipass_estaveis / itens_multipass) if itens_multipass > 0 else None,
    )

    return AvaliacaoClassificacao(
        taxonomia_codigo=conjunto_ouro.taxonomia_codigo,
        conjunto_ouro_digest=conjunto_ouro.digest(),
        perfil_codigo=perfil_codigo.strip(),
        perfil_versao=perfil_versao.strip(),
        modelo_identidade=modelo_identidade.strip(),
        executado_em=executado_em,
        camada1=camada1,
        camada2=camada2,
        camada3=camada3,
        itens=tuple(resultados_itens),
    )


def avaliar_gate_regressao(
    baseline: AvaliacaoClassificacao,
    candidato: AvaliacaoClassificacao,
    *,
    modo_migracao: bool = False,
) -> ResultadoGate:
    """Compara baseline e candidato no mesmo Conjunto-Ouro aplicando o gate de promoção."""
    if baseline.taxonomia_codigo != candidato.taxonomia_codigo:
        raise ErroInvarianteDominio(
            f"Taxonomia incompatível no gate: baseline='{baseline.taxonomia_codigo}', "
            f"candidato='{candidato.taxonomia_codigo}'."
        )
    if baseline.conjunto_ouro_digest != candidato.conjunto_ouro_digest:
        raise ErroInvarianteDominio(
            "Snapshots de Conjunto-Ouro distintos não podem ser comparados no gate de regressão."
        )

    base_por_chave = {item.chave: item for item in baseline.itens}
    cand_por_chave = {item.chave: item for item in candidato.itens}
    if set(base_por_chave) != set(cand_por_chave):
        raise ErroInvarianteDominio("Itens de baseline e candidato divergem no conjunto de chaves.")

    motivos: list[str] = []

    if candidato.camada3.conclusao_valida + TOLERANCIA_FLOAT_GATE < LIMIAR_PISO_CONCLUSAO_VALIDA:
        motivos.append(f"Piso estrutural violado: conclusao_valida={candidato.camada3.conclusao_valida:.4f} < 1.0000.")
    if candidato.camada3.validade_primeira_tentativa + TOLERANCIA_FLOAT_GATE < LIMIAR_PISO_PRIMEIRA_TENTATIVA:
        taxa_primeira = candidato.camada3.validade_primeira_tentativa
        motivos.append(f"Piso estrutural violado: validade_primeira_tentativa={taxa_primeira:.4f} < 0.9500.")

    delta_acuracia = candidato.camada1.acuracia_principal - baseline.camada1.acuracia_principal
    delta_macro_f1 = candidato.camada1.macro_f1_principal - baseline.camada1.macro_f1_principal
    delta_jaccard = candidato.camada1.jaccard_secundarias - baseline.camada1.jaccard_secundarias
    delta_exact_match = candidato.camada1.exact_match - baseline.camada1.exact_match

    if modo_migracao:
        if delta_acuracia + TOLERANCIA_FLOAT_GATE < -QUEDA_MAX_ACURACIA_MIGRACAO:
            motivos.append(f"Modo migração: acuracia_principal caiu {delta_acuracia:.4f} (< -0.0200).")
        if delta_jaccard + TOLERANCIA_FLOAT_GATE < -QUEDA_MAX_JACCARD_MIGRACAO:
            motivos.append(f"Modo migração: jaccard_secundarias caiu {delta_jaccard:.4f} (< -0.0500).")
    else:
        if delta_acuracia + TOLERANCIA_FLOAT_GATE < 0.0:
            motivos.append(f"Modo padrão: acuracia_principal regrediu ({delta_acuracia:.4f} < 0.0000).")
        if delta_macro_f1 + TOLERANCIA_FLOAT_GATE < -QUEDA_MAX_MACRO_F1_PADRAO:
            motivos.append(f"Modo padrão: macro_f1_principal caiu {delta_macro_f1:.4f} (< -0.0200).")
        if delta_jaccard + TOLERANCIA_FLOAT_GATE < -QUEDA_MAX_JACCARD_PADRAO:
            motivos.append(f"Modo padrão: jaccard_secundarias caiu {delta_jaccard:.4f} (< -0.0300).")

    ganhos: list[ItemDiffGate] = []
    regressoes: list[ItemDiffGate] = []
    for chave in sorted(base_por_chave, key=lambda c: c.as_tuple()):
        b_item = base_por_chave[chave]
        c_item = cand_por_chave[chave]
        eh_ganho = (not b_item.exact_match and c_item.exact_match) or (
            not b_item.principal_correta and c_item.principal_correta
        )
        eh_regressao = (b_item.exact_match and not c_item.exact_match) or (
            b_item.principal_correta and not c_item.principal_correta
        )
        if not eh_ganho and not eh_regressao:
            continue
        diff = ItemDiffGate(
            chave=chave,
            baseline_principal=b_item.predita_principal,
            baseline_secundarias=b_item.preditas_secundarias,
            candidato_principal=c_item.predita_principal,
            candidato_secundarias=c_item.preditas_secundarias,
            baseline_exact_match=b_item.exact_match,
            candidato_exact_match=c_item.exact_match,
            baseline_principal_correta=b_item.principal_correta,
            candidato_principal_correta=c_item.principal_correta,
        )
        if eh_ganho:
            ganhos.append(diff)
        if eh_regressao:
            regressoes.append(diff)

    return ResultadoGate(
        aprovado=not motivos,
        modo_migracao=modo_migracao,
        motivos_reprovacao=tuple(motivos),
        delta_acuracia=delta_acuracia,
        delta_macro_f1=delta_macro_f1,
        delta_jaccard=delta_jaccard,
        delta_exact_match=delta_exact_match,
        ganhos=tuple(ganhos),
        regressoes=tuple(regressoes),
    )
