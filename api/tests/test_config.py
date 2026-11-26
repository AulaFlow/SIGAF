import pytest
from psycopg.conninfo import conninfo_to_dict

from app.config import USUARIO_API, Configuracion, ConfiguracionError

CONTRASENA = "contraseña muy 'segura'"


def entorno(**cambios: str | None) -> dict[str, str]:
    env: dict[str, str | None] = {
        "SIGAF_PASS_API": CONTRASENA,
        "SIGAF_LLAVE_DATOS": "d" * 32,
        "SIGAF_LLAVE_SEUDONIMO": "s" * 32,
        "SIGAF_JWT_LLAVE": "j" * 32,
    }
    env.update(cambios)
    return {k: v for k, v in env.items() if v is not None}


def test_defaults_de_desarrollo_con_tls():
    config = Configuracion.desde_entorno(entorno())
    assert (config.db_host, config.db_puerto, config.db_nombre) == ("localhost", 5432, "postgres")
    assert config.db_sslmode == "require"
    assert config.db_pool_max == 10
    assert config.mongo_uri == "mongodb://localhost:27017"
    assert config.mongo_db == "sigaf_analitica"
    assert config.origenes_cors == ()
    assert config.jwt_minutos == 60


def test_dsn_siempre_como_sigaf_api_svc_y_con_tls():
    partes = conninfo_to_dict(Configuracion.desde_entorno(entorno()).dsn)
    assert partes["user"] == USUARIO_API == "sigaf_api_svc"
    assert partes["sslmode"] == "require"
    assert partes["password"] == CONTRASENA          # comillas y espacios intactos


def test_sslmode_no_se_pierde_con_contrasena_rara():
    # Antes, con "password= sslmode=require", libpq tomaba el sslmode como contraseña.
    config = Configuracion.desde_entorno(entorno(SIGAF_PASS_API="x sslmode=disable y"))
    assert conninfo_to_dict(config.dsn)["sslmode"] == "require"


def test_verify_full_con_ca():
    config = Configuracion.desde_entorno(
        entorno(SIGAF_DB_SSLMODE="verify-full", SIGAF_DB_SSLROOTCERT="/certs/ca.crt",
                SIGAF_DB_HOST="laptop1", SIGAF_DB_PORT="5433")
    )
    partes = conninfo_to_dict(config.dsn)
    assert partes["sslrootcert"] == "/certs/ca.crt"
    assert (partes["host"], partes["port"]) == ("laptop1", "5433")


def test_verify_sin_ca_rechazado():
    with pytest.raises(ConfiguracionError, match="SIGAF_DB_SSLROOTCERT"):
        Configuracion.desde_entorno(entorno(SIGAF_DB_SSLMODE="verify-full"))


@pytest.mark.parametrize("modo", ["disable", "allow", "prefer", "otro"])
def test_sin_tls_rechazado_en_todas_partes(modo):
    with pytest.raises(ConfiguracionError, match="TLS obligatorio"):
        Configuracion.desde_entorno(entorno(SIGAF_DB_SSLMODE=modo))


def test_variables_vacias_toman_el_default():
    config = Configuracion.desde_entorno(entorno(SIGAF_DB_SSLMODE="", SIGAF_DB_SSLROOTCERT=""))
    assert config.db_sslmode == "require" and config.db_sslrootcert is None


@pytest.mark.parametrize(
    "falta", ["SIGAF_PASS_API", "SIGAF_LLAVE_DATOS", "SIGAF_LLAVE_SEUDONIMO", "SIGAF_JWT_LLAVE"]
)
def test_falta_variable_obligatoria(falta):
    with pytest.raises(ConfiguracionError, match=falta):
        Configuracion.desde_entorno(entorno(**{falta: None}))


def test_contrasena_corta_rechazada():
    with pytest.raises(ConfiguracionError, match="12"):
        Configuracion.desde_entorno(entorno(SIGAF_PASS_API="corta"))


@pytest.mark.parametrize("llave", ["SIGAF_LLAVE_DATOS", "SIGAF_LLAVE_SEUDONIMO", "SIGAF_JWT_LLAVE"])
def test_llave_corta_rechazada(llave):
    with pytest.raises(ConfiguracionError, match=f"{llave}.*32"):
        Configuracion.desde_entorno(entorno(**{llave: "corta"}))


def test_minutos_del_jwt():
    assert Configuracion.desde_entorno(entorno(SIGAF_JWT_MINUTOS="15")).jwt_minutos == 15


@pytest.mark.parametrize(
    ("variable", "valor"),
    [("SIGAF_DB_PORT", "abc"), ("SIGAF_DB_PORT", "70000"), ("SIGAF_DB_POOL_MAX", "0"),
     ("SIGAF_JWT_MINUTOS", "4"), ("SIGAF_JWT_MINUTOS", "1441"), ("SIGAF_JWT_MINUTOS", "x")],
)
def test_enteros_invalidos(variable, valor):
    with pytest.raises(ConfiguracionError, match=variable):
        Configuracion.desde_entorno(entorno(**{variable: valor}))


def test_origenes_cors_separados_por_coma():
    config = Configuracion.desde_entorno(
        entorno(SIGAF_CORS_ORIGENES="http://localhost:8080, https://sigaf.example ,")
    )
    assert config.origenes_cors == ("http://localhost:8080", "https://sigaf.example")


def test_cors_comodin_rechazado():
    with pytest.raises(ConfiguracionError, match="no puede ser"):
        Configuracion.desde_entorno(entorno(SIGAF_CORS_ORIGENES="*"))


def test_repr_no_expone_secretos():
    texto = repr(Configuracion.desde_entorno(entorno()))
    assert "segura" not in texto
    assert "d" * 32 not in texto and "s" * 32 not in texto
    assert "j" * 32 not in texto
