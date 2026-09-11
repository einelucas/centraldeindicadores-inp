"""Parsers de arquivo (Excel/CSV/PDF) executados no servidor.

Cada módulo de indicador (RDO/RNC/5S/IDP) expõe um `parse_<modulo>_file`
que recebe os bytes crus do arquivo enviado via `multipart/form-data` e
devolve um `FileParseResult` (ver `base.py`) já pronto para
`to_incremental_records()` do módulo correspondente.
"""
