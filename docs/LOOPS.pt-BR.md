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
- A camada de loop é **opcional (opt-in)**. Um projeto renderizado com
  `bootstrap.py --loop` recebe os schemas vendorizados e as verificações
  `loop-schema-vendor` e `loop-contracts`; uma renderização padrão não recebe
  nenhum deles. A escolha fica registrada como `loop` no `.harness.json`, e um
  upgrade mantém a camada de um projeto que já a tinha (veja "Habilitando a
  camada de loop").
- Com a camada habilitada, a verificação `loop-contracts` do
  `scripts/quality_gate.py` valida qualquer contrato encontrado em
  `.loop/contracts/**` contra os schemas acima; sem contratos presentes, ela é
  um no-op documentado. Sem a camada, um contrato em `.loop/contracts/` falha
  tanto o quality gate quanto o `bootstrap.py --check`, para que nenhum
  contrato fique sem validação silenciosamente.
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
   hash, saída com hash, repositório, algoritmo de OID e
   `baseline_oid`/`candidate_oid` completos), e um
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
  Quando a camada de loop está habilitada, verificações obrigatórias de
  infraestrutura, `loop-schema-vendor` e `loop-contracts`, protegem
  proveniência, integridade e validação contratual em todas as execuções; elas
  não são comandos arbitrários selecionáveis pelo builder.
- A evidência é vinculada ao repositório, a object IDs completos do Git
  (`baseline_oid`, `candidate_oid`), aos hashes do contrato, da política e da
  árvore candidata, ao `argv` de comando sem shell e a um ambiente de execução
  com hash, de modo que um veredito sempre possa ser rastreado até exatamente
  o que rodou contra exatamente qual código (formato de evidência `2.0.0`).
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
`engineering-loop-schemas v0.3.0`, fixado no commit completo
`5340d491b46f4fabc967c81bb3e5204104b6b5d8`, com o `scripts/render_vendor_bundle.py` daquele
repositório. Seu `manifest.json` (formato de manifesto `2.0.0`) registra repositório de origem,
versão, commit e o tamanho e o hash SHA-256 de cada fonte Python e dos quatro JSON Schemas
canônicos, além de cada adaptação de import declarada. O `loop-schema-vendor` também rejeita
qualquer arquivo no bundle que o manifesto não declare.

O bundle não é uma cópia byte a byte. Durante a renderização, os imports de pacote em
`validate_contract.py` mudam de `loop_schemas` para `_vendor_loop_schemas`; isso isola o pacote
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

## Habilitando a camada de loop

Renderize um projeto novo com a camada:

```bash
python3 bootstrap.py --name payments-api --package payments_api \
  --target ../payments-api --loop
```

Adicione-a a um projeto existente com `--merge --loop`, ou remova-a com `--merge --no-loop`. Sem
nenhuma das flags, o `--merge` mantém a escolha anterior; um projeto renderizado antes de a camada
se tornar opcional, cujo `.harness.json` não tem a chave `loop` mas rastreia o bundle vendorizado,
mantém a camada. Desabilitar nunca apaga arquivos: o bootstrap lista os arquivos de loop gerados
anteriormente que foram mantidos, e o quality gate continua executando suas verificações até que
um humano os remova.

A camada apenas valida contratos; ela não executa um loop. A denylist de escrita em `.loop/**` e
`scripts/loop_*` dos hooks vale com ou sem a camada habilitada.

## Fora do escopo desta integração

Conforme o plano aprovado, esta fase **não** adiciona um executor de loop,
um executor de gates, uma máquina de estados, um avaliador, ou qualquer
autonomia acima de `report`. Também não cria o futuro harness unificado
nem uma CLI `alicerce`. Isso é trabalho subsequente, uma vez que o Sprint 0
e esta fundação sejam revisados.
