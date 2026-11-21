"""Utilitários HTTP para cache condicional (ETag / If-None-Match / Cache-Control)."""

from __future__ import annotations

from fastapi import Response, status

from application.midia import ImagemPngResultado

CACHE_CONTROL_MIDIA = "private, max-age=3600, must-revalidate"


def etag_corresponde(if_none_match: str | None, etag: str) -> bool:
    if not if_none_match:
        return False
    valor = if_none_match.strip()
    if valor == "*":
        return True
    for candidato in valor.split(","):
        tag = candidato.strip()
        if tag.startswith("W/"):
            tag = tag[2:].strip()
        if tag == etag:
            return True
    return False


def responder_png_com_cache(
    resultado: ImagemPngResultado,
    if_none_match: str | None,
) -> Response:
    headers = {
        "ETag": resultado.etag,
        "Cache-Control": CACHE_CONTROL_MIDIA,
    }
    if etag_corresponde(if_none_match, resultado.etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(
        content=resultado.conteudo_png,
        media_type="image/png",
        headers=headers,
    )
