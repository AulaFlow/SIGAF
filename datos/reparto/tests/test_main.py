"""Pruebas de la línea de comandos (sin base de datos)."""

import pytest

from reparto import __main__ as cli
from reparto.repartidor import Conteo, RepartoError


def test_dsn_por_default_usa_haproxy_con_tls(monkeypatch):
    monkeypatch.delenv("SIGAF_DSN_B", raising=False)
    assert "port=5434" in cli._dsn("B") and "sslmode=verify-ca" in cli._dsn("B")
    monkeypatch.setenv("SIGAF_DSN_A", "host=x")
    assert cli._dsn("A") == "host=x"


def test_nodos_desde_variable(monkeypatch):
    monkeypatch.setenv("SIGAF_NODOS_A", "laptop1:5432, laptop3:5432")
    assert cli._nodos("SIGAF_NODOS_A", "") == cli.Nodos("laptop1:5432", "laptop3:5432")


def test_toma_la_contrasena_de_sigaf_pass_admin(monkeypatch):
    monkeypatch.delenv("PGPASSWORD", raising=False)
    monkeypatch.setenv("SIGAF_PASS_ADMIN", "secreta-de-prueba")
    monkeypatch.setattr(cli, "verificar", lambda: 0)
    assert cli.main(["verificar"]) == 0
    assert cli.os.environ["PGPASSWORD"] == "secreta-de-prueba"


def test_todo_corre_los_tres_pasos(monkeypatch):
    pasos = []
    monkeypatch.setattr(cli, "generar", lambda: pasos.append("generar") or 0)
    monkeypatch.setattr(cli, "repartir", lambda: pasos.append("repartir") or 0)
    monkeypatch.setattr(cli, "verificar", lambda: pasos.append("verificar") or 0)
    assert cli.main(["todo"]) == 0
    assert pasos == ["generar", "repartir", "verificar"]


def test_si_falla_el_generador_no_reparte(monkeypatch):
    monkeypatch.setattr(cli, "generar", lambda: 1)
    monkeypatch.setattr(cli, "repartir", lambda: pytest.fail("no debía repartir"))
    assert cli.main(["todo"]) == 1


def test_error_de_reparto_regresa_1(monkeypatch, capsys):
    def falla():
        raise RepartoError("no cuadra")
    monkeypatch.setattr(cli, "repartir", falla)
    assert cli.main(["repartir"]) == 1
    assert "no cuadra" in capsys.readouterr().err


def test_repartir_imprime_el_reporte(monkeypatch, capsys):
    class ConexionNula:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class RepartidorFalso:
        def __init__(self, *args, **kwargs):
            pass

        def repartir(self):
            return [Conteo("grupo", False, 10, 0, 10), Conteo("rol", True, 3, 3, 3)]

    monkeypatch.setattr(cli, "conectar", lambda _f: ConexionNula())
    monkeypatch.setattr(cli, "Repartidor", RepartidorFalso)
    assert cli.repartir() == 0
    salida = capsys.readouterr().out
    assert "grupo" in salida and "en los dos" in salida and "nada se perdió" in salida


def test_generador_existe():
    assert cli.GENERADOR.is_file()
