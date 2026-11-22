"""Adaptador Pillow que valida uploads PNG/JPEG e os normaliza para PNG."""

from __future__ import annotations

import io

from PIL import Image, UnidentifiedImageError

from domain.exceptions import ErroValidacaoDominio

FORMATOS_ACEITOS = frozenset({"PNG", "JPEG"})


class NormalizadorImagemPillow:
    def normalizar_para_png(self, conteudo: bytes) -> bytes:
        if not conteudo:
            raise ErroValidacaoDominio("O arquivo de imagem não pode estar vazio.")
        try:
            with Image.open(io.BytesIO(conteudo)) as img:
                formato = img.format
                img.verify()
            if formato not in FORMATOS_ACEITOS:
                raise ErroValidacaoDominio(f"Formato de imagem não suportado: {formato!r}. Envie PNG ou JPEG.")
            if formato == "PNG":
                return conteudo
            with Image.open(io.BytesIO(conteudo)) as img:
                convertida = img.convert("RGBA" if "A" in img.getbands() else "RGB")
                saida = io.BytesIO()
                convertida.save(saida, format="PNG")
                return saida.getvalue()
        except ErroValidacaoDominio:
            raise
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError) as err:
            raise ErroValidacaoDominio("O arquivo enviado não é uma imagem PNG ou JPEG válida.") from err
