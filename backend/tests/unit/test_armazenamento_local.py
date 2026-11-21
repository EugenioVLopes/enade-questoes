from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from application.ports import ArmazenamentoArquivos
from domain.exceptions import ErroValidacaoDominio
from infrastructure.storage import ArmazenamentoArquivosLocal


def test_armazenamento_local_satisfaz_protocolo_e_opera_arvore_data_dir(tmp_path: Path) -> None:
    base_dir = tmp_path / "data_app"
    storage = ArmazenamentoArquivosLocal(base_dir)
    assert isinstance(storage, ArmazenamentoArquivos)

    prova_id = uuid4()
    ativo_id = uuid4()
    chaves_e_conteudos = {
        f"storage/provas/{prova_id}/prova.pdf": b"%PDF-1.7 prova",
        f"storage/provas/{prova_id}/gabarito.pdf": b"%PDF-1.7 gabarito",
        f"storage/provas/{prova_id}/extracao_bruta.json": b'{"questoes": []}',
        f"storage/provas/{prova_id}/ativos/{ativo_id}.png": b"\x89PNG\r\n\x1a\n",
        "cache/llm/abc123def456.json": b'{"disciplina_principal": "redes-e-comunicacoes"}',
    }

    for chave, conteudo in chaves_e_conteudos.items():
        chave_retornada = storage.salvar(chave, conteudo)
        assert chave_retornada == chave
        assert storage.existe(chave) is True
        assert storage.ler(chave) == conteudo
        caminho = storage.resolver_caminho(chave)
        assert caminho == (base_dir.resolve() / chave)
        assert caminho.is_file()

    # Sobrescrita atômica não deixa arquivos temporários residuais
    chave_pdf = f"storage/provas/{prova_id}/prova.pdf"
    storage.salvar(chave_pdf, b"%PDF-1.7 atualizado")
    assert storage.ler(chave_pdf) == b"%PDF-1.7 atualizado"
    arquivos_no_dir = [p.name for p in (base_dir / "storage" / "provas" / str(prova_id)).iterdir()]
    assert all(not nome.startswith(".tmp-") for nome in arquivos_no_dir)

    # Remoção e idempotência
    storage.remover(chave_pdf)
    assert storage.existe(chave_pdf) is False
    storage.remover(chave_pdf)
    with pytest.raises(FileNotFoundError):
        storage.ler(chave_pdf)


@pytest.mark.parametrize(
    "chave_invalida",
    [
        "",
        "   ",
        "../etc/passwd",
        "storage/provas/../../segredo.txt",
        "./prova.pdf",
        "storage/./prova.pdf",
        "/etc/passwd",
        "C:\\temp\\prova.pdf",
        "C:/temp/prova.pdf",
        "storage\\provas\\prova.pdf",
        "storage/provas//prova.pdf",
        "storage/provas/",
        "storage/provas/prova\x00.pdf",
    ],
)
def test_armazenamento_local_rejeita_path_traversal_e_chaves_invalidas(
    tmp_path: Path,
    chave_invalida: str,
) -> None:
    storage = ArmazenamentoArquivosLocal(tmp_path / "data_app")

    for acao in (
        lambda: storage.resolver_caminho(chave_invalida),
        lambda: storage.salvar(chave_invalida, b"dados"),
        lambda: storage.ler(chave_invalida),
        lambda: storage.remover(chave_invalida),
        lambda: storage.existe(chave_invalida),
    ):
        with pytest.raises(ErroValidacaoDominio):
            acao()


def test_armazenamento_local_rejeita_escape_por_symlink(tmp_path: Path) -> None:
    base_dir = tmp_path / "data_app"
    externo = tmp_path / "fora_de_data_dir"
    externo.mkdir(parents=True)
    (externo / "alvo.txt").write_bytes(b"secreto")

    provas_dir = base_dir / "storage" / "provas"
    provas_dir.mkdir(parents=True)
    (provas_dir / "link_externo").symlink_to(externo, target_is_directory=True)
    (provas_dir / "link_quebrado").symlink_to(externo / "inexistente.txt")

    storage = ArmazenamentoArquivosLocal(base_dir)

    for chave_symlink in (
        "storage/provas/link_externo/alvo.txt",
        "storage/provas/link_externo/novo/arquivo.txt",
        "storage/provas/link_quebrado",
    ):
        with pytest.raises(ErroValidacaoDominio):
            storage.resolver_caminho(chave_symlink)
        with pytest.raises(ErroValidacaoDominio):
            storage.salvar(chave_symlink, b"nao deveria gravar")
        with pytest.raises(ErroValidacaoDominio):
            storage.ler(chave_symlink)
        with pytest.raises(ErroValidacaoDominio):
            storage.existe(chave_symlink)
        with pytest.raises(ErroValidacaoDominio):
            storage.remover(chave_symlink)

    assert not (externo / "novo").exists()
    assert (externo / "alvo.txt").read_bytes() == b"secreto"


def test_armazenamento_local_rejeita_leitura_ou_remocao_de_diretorio(tmp_path: Path) -> None:
    storage = ArmazenamentoArquivosLocal(tmp_path / "data_app")
    storage.salvar("cache/llm/item.json", b"{}")

    with pytest.raises(IsADirectoryError):
        storage.ler("cache/llm")
    with pytest.raises(IsADirectoryError):
        storage.remover("cache/llm")
