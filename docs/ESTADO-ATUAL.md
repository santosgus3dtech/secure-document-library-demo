# Estado atual — Secure Document Library Demo

Revisão documental: 13/10/2026. Nenhum PDF gerado, carregado, excluído ou recuperado.

## Arquitetura observada

`app/main.py` compõe FastAPI e registra `/api/health`, listagem/download/upload/exclusão/recuperação de documentos e auditoria. `app/security.py` contém `validate_pdf_name` e `safe_document_path`; `app/store.py` usa SQLite e `add_document`. ReportLab e python-multipart aparecem nas dependências para PDF/upload. A interface está em `app/static/`.

## Regras documentadas

[README](../README.md) descreve papéis viewer/editor/admin, teto de upload de dois MB, validação de PDF/caminho e recuperação isolada. O mecanismo por header é explicitamente demo, sem equivalência com autenticação de produção. A presença de funções defensivas não comprova todos os cenários sem testes.

## Operação

README identifica `python -m uvicorn app.main:app --reload` e `pytest -q`. Ambos não executados nesta tarefa. `.data/` e arquivos binários não foram abertos; o comportamento de gerar três PDFs no primeiro uso é relato do README, não resultado desta revisão.

## Retomada

Última etapa comprovada: documentação de navegação conferida. Sugestões: revisar o cenário de arquivos/autorizações afetado pela próxima mudança; usar apenas dados sintéticos; manter explícita a diferença entre papel demonstrativo e autenticação real. Não há roadmap adicional aprovado ou decisões históricas inferidas.

[Índice](INDEX.md)
