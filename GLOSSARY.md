# Enade Questões

Plataforma de ingestão, curadoria e classificação curricular de questões de provas acadêmicas, desacoplando o conteúdo oficial das provas de múltiplas taxonomias e revisões humanas.

## Language

### Conteúdo de Prova

**Prova**:
Caderno oficial de um exame acadêmico, identificado de forma única pela combinação de exame, curso e ano da edição.
_Avoid_: Caderno, arquivo, PDF

**Ingestão**:
Processo registrado de carga, extração e estruturação de uma Prova (e opcionalmente de seu Gabarito) em Questões, Alternativas, Ativos Visuais e Alertas de Extração.
_Avoid_: Upload, importação, job de PDF

**Questão**:
Item individual extraído de uma Prova, com número oficial, enunciado, alternativas, ativos visuais e vínculo de gabarito, totalmente desacoplado de qualquer classificação curricular.
_Avoid_: Pergunta, exercício, item

**Alternativa**:
Uma das opções de resposta identificadas por letra (`A` a `E`) pertencentes a uma Questão objetiva.
_Avoid_: Opção, resposta

**Ativo Visual**:
Elemento gráfico extraído de uma Prova ou anexado durante a curadoria (como circuito, diagrama, gráfico, fórmula ou figura) associado a uma Questão ou a uma Alternativa específica.
_Avoid_: Figura, imagem, anexo, mídia

**Gabarito**:
Registro oficial da alternativa correta ou da condição de anulação das Questões de uma Prova, atualizável de forma independente do caderno de prova.
_Avoid_: Chave, folha de respostas

**Alerta de Extração**:
Sinalização determinística registrada em uma Questão quando a extração do PDF detecta alguma anomalia (como fórmula não decodificada, alternativas incompletas ou uso de OCR de página inteira), resolvível após correção ou verificação humana.
_Avoid_: Erro, aviso, warning

### Taxonomia Curricular

**Taxonomia**:
Catálogo nomeado e editável de Disciplinas usado para classificar questões (como a matriz oficial do ENADE ou o PPC de uma universidade), aplicável a questões de qualquer Prova.
_Avoid_: Grade, matriz, currículo

**Disciplina**:
Unidade curricular pertencente a uma Taxonomia, definida por código, nome e ementa; pode ser arquivada sem invalidar classificações históricas.
_Avoid_: Matéria, área, categoria

**Tópico**:
Rótulo livre opcional associado a uma Classificação para capturar temas granulares sem expandir a Taxonomia fechada.
_Avoid_: Tag, subtema, assunto, palavra-chave

### Classificação e Revisão

**Perfil de Classificação**:
Conjunto versionado de diretrizes editoriais e critérios de desambiguação combinado ao prompt e ao modelo utilizados para classificar Questões sob uma Taxonomia.
_Avoid_: Regra, configuração

**Execução de Classificação**:
Rodada registrada de classificação automática sobre um conjunto de Questões que preserva o snapshot da Taxonomia e do Perfil de Classificação aplicados.
_Avoid_: Lote, job, processamento

**Classificação**:
Veredito associado a um par `(Questão, Taxonomia)` que define exatamente uma Disciplina principal, de zero a duas Disciplinas secundárias, Tópicos opcionais, justificativa e grau de confiança.
_Avoid_: Categorização, resultado

**Divergência de Reclassificação**:
Sugestão candidata gerada por uma Execução de Classificação que difere na Disciplina principal ou nas Disciplinas secundárias de uma Classificação já revisada por humano para o mesmo par `(Questão, Taxonomia)`.
_Avoid_: Conflito de merge, sobrescrita, erro de classificação

**Conjunto-Ouro**:
Conjunto versionado de vereditos curriculares aprovados por humano para uma Taxonomia, usado como referência estável para avaliar a qualidade de classificações automáticas.
_Avoid_: Gabarito de classificação, dataset de teste, ground truth

**Avaliação de Classificação**:
Medição isolada que compara a saída de um Perfil de Classificação e modelo contra um Conjunto-Ouro ou contra o histórico de revisões humanas para aferir acurácia e regressões sem gerar Classificações vigentes nem Divergências de Reclassificação.
_Avoid_: Benchmark, teste de prompt, execução de teste
