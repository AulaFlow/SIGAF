-- =====================================================================
-- SIGAF · db/05_seguridad.sql  (issue #6)
-- Aplica las decisiones de seguridad del equipo:
--   * Cifrado en reposo de nombre y apellidos del alumno (AES-256, pgcrypto)
--   * Seudonimización de la matrícula con HMAC-SHA256 y llave secreta
--   * Roles con mínimo privilegio: admin, API, ETL (solo lectura)
--   * Datos personales visibles solo para el profesor (de sus grupos), el
--     administrador y el propio alumno (solo los suyos; ajuste del 23 nov)
-- Las LLAVES nunca están en la base ni en el código: la aplicación las lee
-- de variables de entorno y las pone en la sesión con set_config(). Si una
-- sesión no trae la llave, no puede cifrar, descifrar ni seudonimizar.
-- Las CONTRASEÑAS de los roles se ponen aparte (06_credenciales.sql).
-- Orden: 01 -> 02 -> 03 -> 05 (este) -> 06 -> pruebas
-- =====================================================================
SET search_path TO sigaf, public;

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;

-- =====================================================================
-- 1. Llaves, cifrado y seudonimización
-- =====================================================================

-- Lee una llave de la sesión (sigaf.llave_datos o sigaf.llave_seudonimo).
CREATE OR REPLACE FUNCTION fn_llave(p_nombre TEXT)
RETURNS TEXT
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    v_llave TEXT := current_setting('sigaf.' || p_nombre, true);
BEGIN
    IF v_llave IS NULL OR length(v_llave) < 32 THEN
        RAISE EXCEPTION 'Falta la llave sigaf.% en la sesión (mínimo 32 caracteres)', p_nombre
            USING ERRCODE = '28000';
    END IF;
    RETURN v_llave;
END;
$$;

-- Cifra un texto con AES-256 (llave de datos).
CREATE OR REPLACE FUNCTION fn_cifrar(p_texto TEXT)
RETURNS BYTEA
LANGUAGE sql VOLATILE
SET search_path = sigaf, public, pg_temp
AS $$
    SELECT pgp_sym_encrypt(p_texto, fn_llave('llave_datos'), 'cipher-algo=aes256');
$$;

-- Descifra. Solo la usan las funciones autorizadas de abajo.
CREATE OR REPLACE FUNCTION fn_descifrar(p_dato BYTEA)
RETURNS TEXT
LANGUAGE sql STABLE
SET search_path = sigaf, public, pg_temp
AS $$
    SELECT pgp_sym_decrypt(p_dato, fn_llave('llave_datos'));
$$;

-- Seudónimo de una matrícula real: HMAC-SHA256 en hexadecimal (64 caracteres).
-- No se puede revertir; la misma matrícula siempre da el mismo seudónimo,
-- así el inicio de sesión puede buscar al alumno sin guardar la matrícula.
CREATE OR REPLACE FUNCTION fn_seudonimizar(p_matricula TEXT)
RETURNS CHAR(64)
LANGUAGE sql STABLE
SET search_path = sigaf, public, pg_temp
AS $$
    SELECT encode(hmac(upper(trim(p_matricula)), fn_llave('llave_seudonimo'), 'sha256'), 'hex');
$$;

-- =====================================================================
-- 2. Acceso a datos personales (SECURITY DEFINER: corren con permisos del
--    dueño, así los roles no necesitan leer la tabla directamente)
-- =====================================================================

-- Profesor: nombres de los alumnos de SUS grupos activos. La API manda el
-- profesor_id del usuario autenticado.
CREATE OR REPLACE FUNCTION fn_alumnos_de_profesor(p_profesor_id BIGINT)
RETURNS TABLE (grupo_id BIGINT, alumno_id BIGINT, matricula CHAR(64),
               nombre TEXT, apellidos TEXT)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = sigaf, public, pg_temp
AS $$
    SELECT g.grupo_id, a.alumno_id, a.matricula,
           fn_descifrar(dp.nombre_cifrado), fn_descifrar(dp.apellidos_cifrado)
    FROM grupo g
    JOIN inscripcion i              ON i.grupo_id = g.grupo_id AND i.estado = 'activa'
    JOIN alumno a                   ON a.alumno_id = i.alumno_id
    JOIN alumno_datos_personales dp ON dp.alumno_id = a.alumno_id
    WHERE g.profesor_id = p_profesor_id
    ORDER BY g.grupo_id, 5, 4;
$$;

-- Alumno: SUS propios datos personales, y de nadie más. No recibe
-- parámetro: la API pone en la sesión el alumno_id del usuario autenticado
-- (tomado del token, nunca de la petición) con
--   SELECT set_config('sigaf.alumno_sesion', <alumno_id>, true);
CREATE OR REPLACE FUNCTION fn_mis_datos()
RETURNS TABLE (alumno_id BIGINT, nombre TEXT, apellidos TEXT)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = sigaf, public, pg_temp
AS $$
DECLARE
    v_alumno BIGINT := nullif(current_setting('sigaf.alumno_sesion', true), '')::BIGINT;
BEGIN
    IF v_alumno IS NULL THEN
        RAISE EXCEPTION 'No hay un alumno autenticado en la sesión' USING ERRCODE = '28000';
    END IF;
    RETURN QUERY
        SELECT dp.alumno_id, fn_descifrar(dp.nombre_cifrado), fn_descifrar(dp.apellidos_cifrado)
        FROM alumno_datos_personales dp
        WHERE dp.alumno_id = v_alumno;
END;
$$;

-- Administrador: datos personales de cualquier alumno.
CREATE OR REPLACE FUNCTION fn_datos_alumno(p_alumno_id BIGINT)
RETURNS TABLE (alumno_id BIGINT, matricula CHAR(64), nombre TEXT, apellidos TEXT)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = sigaf, public, pg_temp
AS $$
    SELECT a.alumno_id, a.matricula,
           fn_descifrar(dp.nombre_cifrado), fn_descifrar(dp.apellidos_cifrado)
    FROM alumno a JOIN alumno_datos_personales dp USING (alumno_id)
    WHERE a.alumno_id = p_alumno_id;
$$;

-- Alta de los datos personales (los cifra al guardarlos).
CREATE OR REPLACE PROCEDURE sp_guardar_datos_personales(p_alumno_id BIGINT, p_nombre TEXT, p_apellidos TEXT)
LANGUAGE sql SECURITY DEFINER
SET search_path = sigaf, public, pg_temp
AS $$
    INSERT INTO alumno_datos_personales (alumno_id, nombre_cifrado, apellidos_cifrado)
    VALUES (p_alumno_id, fn_cifrar(p_nombre), fn_cifrar(p_apellidos))
    ON CONFLICT (alumno_id) DO UPDATE
        SET nombre_cifrado = EXCLUDED.nombre_cifrado,
            apellidos_cifrado = EXCLUDED.apellidos_cifrado;
$$;

-- La bitácora de calificaciones la escribe el trigger con permisos del
-- dueño: así la API puede calificar, pero NO puede tocar la bitácora.
ALTER FUNCTION fn_bitacora_calificacion() SECURITY DEFINER;
ALTER FUNCTION fn_bitacora_calificacion() SET search_path = sigaf, pg_temp;

-- =====================================================================
-- 3. Roles (grupos sin login; los usuarios con login van en 06)
-- =====================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sigaf_admin') THEN
        CREATE ROLE sigaf_admin NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sigaf_api') THEN
        CREATE ROLE sigaf_api NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sigaf_etl') THEN
        CREATE ROLE sigaf_etl NOLOGIN;
    END IF;
END $$;

-- Nadie tiene nada por defecto
REVOKE ALL ON SCHEMA sigaf FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA sigaf FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA sigaf FROM PUBLIC;
REVOKE ALL ON ALL PROCEDURES IN SCHEMA sigaf FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

GRANT USAGE ON SCHEMA sigaf TO sigaf_admin, sigaf_api, sigaf_etl;

-- 3.1 Administrador: todo el esquema y los datos personales de cualquier alumno
GRANT ALL ON ALL TABLES IN SCHEMA sigaf TO sigaf_admin;
GRANT ALL ON ALL SEQUENCES IN SCHEMA sigaf TO sigaf_admin;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA sigaf TO sigaf_admin;
GRANT EXECUTE ON ALL PROCEDURES IN SCHEMA sigaf TO sigaf_admin;

-- 3.2 API: lee y escribe lo operativo, pero
--   * NO lee alumno_datos_personales (solo por fn_alumnos_de_profesor)
--   * NO escribe en la bitácora ni en el directorio de fragmentos
--   * NO borra nada (las bajas son estado = 'baja')
GRANT SELECT, INSERT, UPDATE ON
    usuario, alumno, profesor, grupo, horario, inscripcion, tarea, entrega,
    examen, pregunta, opcion, intento_examen, respuesta, calificacion,
    asistencia, aviso, conversacion, participante_conversacion, mensaje, notificacion
TO sigaf_api;
GRANT SELECT ON rol, centro_academico, carrera, periodo, materia, directorio_fragmento,
    v_situacion_academica, v_pendientes_alumno, v_boleta
TO sigaf_api;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA sigaf TO sigaf_api;
GRANT EXECUTE ON FUNCTION
    fn_seudonimizar(TEXT), fn_alumnos_de_profesor(BIGINT), fn_mis_datos(),
    fn_estado_entrega(TIMESTAMPTZ, TIMESTAMPTZ), fn_porcentaje_asistencia(BIGINT),
    fn_calificar_intento(BIGINT), fn_llave(TEXT)
TO sigaf_api;
-- (los triggers no necesitan EXECUTE: corren con los permisos de las tablas
--  que toca quien escribe, que la API ya tiene)
GRANT EXECUTE ON PROCEDURE
    sp_inscribir_alumno(BIGINT, BIGINT, BIGINT), sp_enviar_intento(BIGINT, NUMERIC),
    sp_guardar_datos_personales(BIGINT, TEXT, TEXT)
TO sigaf_api;

-- 3.3 ETL hacia MongoDB: SOLO LECTURA de lo académico. No ve usuarios,
--     contraseñas, datos personales, mensajes ni la bitácora.
GRANT SELECT ON
    centro_academico, directorio_fragmento, carrera, periodo, materia, alumno,
    grupo, inscripcion, tarea, entrega, calificacion, asistencia,
    v_situacion_academica, v_boleta
TO sigaf_etl;
GRANT SELECT (profesor_id, centro_academico_id) ON profesor TO sigaf_etl;  -- sin nombres
-- (el ETL no recibe EXECUTE de ninguna función de llaves)
