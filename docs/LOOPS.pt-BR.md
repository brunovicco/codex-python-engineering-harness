# Evidence-Gated Engineering Loops

*[English](LOOPS.md)*

Os schemas compartilhados de contrato, evidência, veredito e resultado do
builder deste harness vivem em um repositório separado,
[`engineering-loop-schemas`](https://github.com/brunovicco/engineering-loop-schemas),
para que tanto este harness quanto seu irmão
(`claude-python-engineering-harness`) validem contratos de loop contra uma
única fonte canônica, em vez de manterem cópias divergentes. Esse
repositório também é o embrião da futura camada de loop do harness
unificado ("alicerce").

## Estado atual: Fase 1, somente relatório (report-only)

A autonomia de loop neste harness é atualmente **`report`** e nada além
disso. Concretamente, a partir desta integração:

- Nenhum agente neste repositório, ou em um projeto gerado a partir dele,
  pode promover uma mudança candidata, executar um loop de ponta a ponta
  ou certificar o próprio trabalho.
- `loop_runner.py`, `loop_gate.py`, `loop_state.py`, um avaliador
  (evaluator) ou qualquer tipo de máquina de estados não existem. Construí-los
  está explicitamente fora do escopo desta fase.
- `.loop/**` e `scripts/loop_*` estão na denylist de escrita por agentes em
  `protect_sensitive_files.py` (veja `.codex/hooks/protect_sensitive_files.py`
  em um projeto gerado). Espera-se que apenas um humano, editando fora de
  uma chamada de ferramenta do agente, coloque um contrato real em
  `.loop/contracts/`.
- A verificação `loop-contracts` do `scripts/quality_gate.py` valida
  qualquer contrato encontrado em `.loop/contracts/**` contra os schemas
  acima. Sem contratos presentes -- o estado esperado hoje -- ela é um
  no-op documentado.
- O workflow de CI de autoavaliação (veja `.github/workflows/` do
  repositório), que renderiza cada perfil e reporta os resultados dos
  gates, é ele próprio somente-relatório: nunca modifica código do
  repositório, e sua etapa opcional de interpretação por agente fica
  desabilitada por padrão atrás de uma flag, sem credenciais no repositório.

## O modelo de três níveis

Toda execução de loop pertence a um dos três níveis de escrutínio,
espelhando o README do `engineering-loop-schemas`:

1. **Nível do agente (agent-level)** -- uma única tentativa do builder
   contra um contrato. Sua saída é um documento `builder-result`: o
   próprio relato do builder sobre o que tentou, explicitamente marcado
   como não-autoritativo.
2. **Nível de conclusão (completion-level)** -- uma execução completa:
   tentativa(s) do builder, coleta mecânica de `evidence` (comandos com
   hash, saída com hash, `baseline_sha`/`candidate_sha` exatos), e um
   `verdict` derivado ao avaliar essa evidência contra os
   `acceptance.hard_gates` do contrato.
3. **Nível operacional (operational-level)** -- a saúde do próprio loop ao
   longo de muitas execuções: consumo de budget, taxa de escalonamento, e
   divergência entre o que um contrato declara e o que de fato acontece.

## Princípios não negociáveis

- Um builder nunca certifica o próprio resultado. Apenas um `verdict`
  derivado mecanicamente pode fazê-lo.
- Um hard gate é default-FAIL e precisa se reduzir a um comando com código
  de saída. Os hard gates referenciáveis pelo contrato
  (`acceptance.hard_gates`) são exatamente as verificações
  nomeadas que o `quality_gate.py` deste harness já implementa: `lock`,
  `lint`, `format`, `typing`, `tests`, `security`, `dependencies`,
  `architecture`, `mcp`, `governance`.
  Verificações obrigatórias de infraestrutura, incluindo `loop-schema-vendor` e
  `loop-contracts`, protegem proveniência, integridade e validação contratual em todas as
  execuções; elas não são comandos arbitrários selecionáveis pelo builder.
- A evidência é vinculada a commits exatos (`baseline_sha`,
  `candidate_sha`) e a um ambiente com hash (`uv_lock_sha256`), de modo que
  um veredito sempre possa ser rastreado até exatamente o que rodou contra
  exatamente qual código.
- Os hooks (`protect_sensitive_files.py`, `validate_bash.py`,
  `guard_mcp.py`) são defesa em profundidade, não orquestração. Eles
  impedem que um agente exceda silenciosamente o escopo declarado desta
  fase; eles não executam, agendam ou promovem nada.

## Estados finais

Toda execução concluída se resolve em exatamente um estado final
(`verdict.final_state`):

| Estado | Significado |
| --- | --- |
| `SUCCEEDED` | Todos os hard gates passaram; candidato é promovível, pendente de revisão humana. |
| `NO_OP` | O builder determinou corretamente que não havia nada a fazer. |
| `NO_PROGRESS` | O builder produziu um candidato, mas ele não melhora em relação ao baseline. |
| `VERIFY_FAILED` | Um ou mais hard gates falharam contra o candidato. |
| `POLICY_BLOCKED` | O candidato tocou `scope.denylist` ou uma entrada de `actions.denied`. |
| `BUDGET_EXCEEDED` | `budgets` (tokens, custo, tempo de parede ou contagem de comandos) foi excedido. |
| `ESCALATED` | A execução não conseguiu resolver PASS/FAIL e precisa de uma decisão humana. |
| `INFRA_FAILED` | A execução falhou por razões não relacionadas ao candidato (ferramental, rede, ambiente). |

## Vendoring

`template/scripts/_vendor_loop_schemas/` é um bundle determinístico renderizado a partir do
`engineering-loop-schemas v0.1.2`, fixado no commit completo
`0459d61b7b1d4e7b46709e6d3895770553e6fab0`. Seu `manifest.json` registra repositório de origem,
versão, commit, tamanhos, hashes SHA-256 e a adaptação de import declarada.

O bundle não é uma cópia byte a byte. Durante a renderização, o import de pacote em
`validate_contract.py` muda de `loop_schemas` para `_vendor_loop_schemas`; isso isola o pacote
vendorizado e evita colisão com o namespace protegido `scripts/loop_*`. A adaptação está explícita
no manifesto e coberta por testes de renderização determinística, integridade e adulteração. O
gate `loop-schema-vendor` verifica o bundle offline em cada quality gate de projeto gerado.
Corrija o repositório canônico de schemas e renderize uma nova versão, em vez de editar o bundle
manualmente.

`validate_contract.py` é somente-stdlib. Ler um contrato YAML requer que o
PyYAML seja importável no ambiente em que `scripts/quality_gate.py`
executa; contratos JSON sempre funcionam sem dependência extra. O PyYAML
deliberadamente **não** foi adicionado como dependência do harness por
esta integração (o núcleo compartilhado está em congelamento de features --
veja `CONTRIBUTING.md`); se um humano quiser validar contratos YAML
localmente, deve adicionar o PyYAML ao próprio projeto.

## Fora do escopo desta integração

Conforme o plano aprovado, esta fase **não** adiciona um executor de loop,
um executor de gates, uma máquina de estados, um avaliador, ou qualquer
autonomia acima de `report`. Também não cria o futuro harness unificado
nem uma CLI `alicerce`. Isso é trabalho subsequente, uma vez que o Sprint 0
e esta fundação sejam revisados.
