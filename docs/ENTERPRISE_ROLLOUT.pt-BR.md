# Rollout corporativo

*[English](ENTERPRISE_ROLLOUT.md)*

Use o scaffold do repositório para políticas específicas do projeto e o marketplace de plugins
para capacidades reutilizáveis.

## Ownership recomendado

- Engenharia de plataforma é dona do plugin, do runtime de hooks, da configuração aprovada e da
  baseline de CI.
- Segurança é dona dos caminhos bloqueados, padrões de comandos perigosos, padrões de secrets e
  da governança de exceções.
- Arquitetura é dona dos contratos de dependência e do template padrão de ADR.
- Cada time de produto é dono do seu `AGENTS.md`, configuração do projeto, inventário de dados e
  critérios de aceite.

## Modelo de distribuição

1. Publique este repositório em um Git host interno controlado.
2. Adicione-o como marketplace interno
   (`codex plugin marketplace add <git-interno-ou-caminho>`).
3. Valide e versione o plugin antes da promoção.
4. Fixe ou aprove versões pela sua baseline de gestão de configuração, quando disponível.
5. Faça o rollout primeiro para um grupo piloto e inspecione negações, falsos positivos, latência
   e overrides de desenvolvedores.
6. Promova apenas depois que o projeto gerado e o plugin passarem no checklist de validação.

## Separação de responsabilidades

- Mantenha fatos e comandos do projeto no repositório (`AGENTS.md`, `.codex/config.toml`).
- Mantenha procedimentos e skills reutilizáveis no plugin.
- Mantenha controles obrigatórios em hooks, sandboxing, CI, identidade, rede e proteção de
  repositório.
- Exija trust explícito de `.codex/config.toml` e `.codex/hooks.json`; revise hooks novos ou
  alterados com `/hooks` antes de confiar neles.
- Não coloque credenciais em configurações de plugin ou de MCP.
- Trate servidores MCP e integrações externas como caminhos de saída de dados que exigem um
  threat model explícito.

## Modelo de rollout de MCP

Trate MCP como uma plataforma de integração, não como uma conveniência de desenvolvedor.
Progressão recomendada:

1. Inventarie o sistema externo, dono, classes de dados, operações, autenticação e retenção.
2. Pilote com uma identidade somente-leitura e dados não produtivos.
3. Revise a implementação do servidor, processo de release, pinning de dependências, exposição a
   prompt injection e destinos de rede.
4. Publique servidores aprovados do projeto via `[mcp_servers.*]` em `.codex/config.toml`; o
   validador do projeto exige TLS, indireção de credenciais por nome de variável de ambiente,
   versões exatas de runners efêmeros, comandos STDIO diretos e timeouts limitados.
5. Mantenha credenciais por usuário via indireção de ambiente ou credential helper. Nunca coloque
   secrets em configuração compartilhada.
6. Monitore uso de servidores e ferramentas pelo export nativo de OpenTelemetry da plataforma,
   sem coletar entradas ou saídas completas.
7. Reaprove integrações periodicamente e revogue servidores, escopos e credenciais sem uso.

Para ambientes regulados estritos, prefira um conjunto fixo de servidores aprovados ou desabilite
MCP inteiramente até que cada integração tenha um threat model aprovado.

## Governança de mudanças

Cada release do harness deve incluir:

- versão semântica;
- release notes e notas de migração;
- evidência de teste para casos permitidos e negados dos hooks;
- evidência de validação do plugin;
- declaração de compatibilidade com as versões suportadas de Codex e Python;
- instruções de rollback;
- dono nomeado e processo de exceção.

## Métricas

Acompanhe adoção e efetividade dos controles sem coletar código-fonte ou prompts:

- repositórios e desenvolvedores em cada versão do harness;
- negações de hooks por categoria, a partir do `.codex/logs/hooks-audit.jsonl` local de cada
  projeto (escrito por `log_event` em `.codex/hooks/_common.py`; uma linha JSON por decisão de
  negação/bloqueio com timestamp, nome do hook, categoria, decisão e nome da ferramenta - nunca
  texto de comando, conteúdo de arquivo ou valores identificados). Agregue esse arquivo
  centralmente pela sua pipeline de logs existente; ele não é coletado automaticamente;
- taxas de falso positivo e de override;
- duração do quality gate e categoria de falha;
- tempo para remediar secrets e dependências vulneráveis;
- percentual de projetos com lock files atualizados e tratamento de dados documentado;
- servidores MCP por dono, versão, escopo e expiração de revisão;
- métricas de uso de agente e ferramentas derivadas de OpenTelemetry, restritas a metadados.
