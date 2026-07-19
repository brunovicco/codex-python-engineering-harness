# Atualizando projetos gerados

*[English](UPGRADING.md)*

Projetos gerados são snapshots e nunca são modificados automaticamente.

## Fluxo recomendado

1. Leia o `CHANGELOG.md` e confirme a versão-alvo do harness.
2. Faça commit ou preserve de outra forma o estado atual do projeto gerado.
3. Rode uma prévia a partir do checkout do novo harness:

   ```bash
   python /caminho/para/harness/bootstrap.py --target . --dry-run --merge
   ```

4. Aplique a atualização não destrutiva:

   ```bash
   python /caminho/para/harness/bootstrap.py --target . --merge
   ```

5. Revise cada arquivo de conflito `*.harness-new`. O harness preserva arquivos customizados
   localmente e nunca trata a cópia de conflito como substituição automática.
6. Rode o gate do projeto gerado e a verificação de metadados:

   ```bash
   uv sync --all-groups
   uv run python scripts/quality_gate.py
   python /caminho/para/harness/bootstrap.py --target . --check
   ```

7. Revise e confie (trust) nos hooks do Codex alterados antes de usá-los.

## Atualizações do plugin

Releases do plugin são independentes das releases do gerador. Atualize a instalação do
marketplace, reinicie o Codex quando necessário, revise hooks e permissões alterados e valide o
plugin antes de adotá-lo. Uma atualização de plugin não reescreve projetos gerados.

Não copie hashes do manifesto, não apague arquivos de conflito sem revisão e não substitua
arquivos customizados do projeto apenas para fazer o `--check` passar.
