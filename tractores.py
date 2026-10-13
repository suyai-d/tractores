import streamlit as st
import pandas as pd
import requests
import base64

from io import StringIO
from datetime import datetime


# =====================================================
# CONFIGURACIÓN DE PÁGINA
# =====================================================

st.set_page_config(
    page_title="Reporte de Tractores",
    page_icon="🚜",
    layout="wide"
)


# =====================================================
# CONFIGURACIÓN DE GITHUB
# =====================================================

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]

REPO_OWNER = "suyai-d"
REPO_NAME = "reportes-seguridad-db"
BRANCH = "main"


# =====================================================
# CONSTANTES DEL REPORTE
# =====================================================

CLIENTE_VACIO = "Seleccionar Cliente..."

COLUMNAS_TECNOLOGIAS = {
    "AutoTrac": "AutoTrac™",
    "AutoPath": "AutoPath™",
    "Implement Guidance": "AutoTrac™ Implement Guidance",
    "AutoTrac Turn Automation": "AutoTrac™ Turn Automation",
    "Efficiency Manager": "Tiempo de activación de Efficiency Manager™",
    "FieldCruise": "FieldCruise™",
}

# Estas columnas no representan una razón concreta declarada
# por el operador, por eso no participan como motivo registrado.

MOTIVOS_EXCLUIDOS = {
    "Sin definir Período",
    "Cancelada Período",
    "Ignorada Período",
}


# =====================================================
# FUNCIONES GENERALES
# =====================================================

def normalizar_texto(valor):
    """
    Convierte un valor a texto, elimina espacios laterales
    y reduce espacios dobles.
    """

    if pd.isna(valor):
        return ""

    return " ".join(str(valor).strip().split())


def convertir_numerico(serie):
    """
    Convierte una serie a valores numéricos.
    Admite números con coma o punto decimal.
    """

    return pd.to_numeric(
        serie.astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip(),
        errors="coerce",
    )


def limitar_porcentaje(valor):
    """
    Limita cualquier porcentaje al rango 0-100.
    """

    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, min(valor, 100.0))


def obtener_primera_columna(df, nombres_posibles):
    """
    Devuelve el primer nombre de columna disponible
    entre las alternativas indicadas.
    """

    for nombre in nombres_posibles:
        if nombre in df.columns:
            return nombre

    return None


# =====================================================
# AUTENTICACIÓN
# =====================================================

def verificar_usuario(legajo_ingresado):
    """
    Verifica el legajo contra usuarios_permitidos.csv
    almacenado en GitHub.
    """

    url_api_usuarios = (
        f"https://api.github.com/repos/"
        f"{REPO_OWNER}/{REPO_NAME}/contents/"
        f"usuarios_permitidos.csv"
    )

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    legajo_limpio = normalizar_texto(legajo_ingresado).upper()

    if not legajo_limpio:
        return False

    try:
        response = requests.get(
            url_api_usuarios,
            headers=headers,
            timeout=10,
        )

        if response.status_code != 200:
            st.error(
                "No se pudo leer el listado de usuarios autorizados. "
                f"Código de GitHub: {response.status_code}"
            )
            return False

        file_data = response.json()

        contenido = base64.b64decode(
            file_data["content"]
        ).decode("utf-8-sig")

        df_usuarios = pd.read_csv(
            StringIO(contenido)
        )

        df_usuarios.columns = (
            df_usuarios.columns
            .astype(str)
            .str.strip()
        )

        if "usuarios" not in df_usuarios.columns:
            st.error(
                "El archivo usuarios_permitidos.csv "
                "no contiene la columna 'usuarios'."
            )
            return False

        usuarios_autorizados = (
            df_usuarios["usuarios"]
            .astype(str)
            .str.replace(r"\r|\n", "", regex=True)
            .str.strip()
            .str.upper()
        )

        return legajo_limpio in usuarios_autorizados.values

    except requests.exceptions.Timeout:
        st.error(
            "GitHub tardó demasiado en responder al validar el usuario."
        )
        return False

    except requests.exceptions.ConnectionError:
        st.error(
            "No se pudo establecer conexión con GitHub."
        )
        return False

    except Exception as e:
        st.error(
            f"Error verificando el usuario: {e}"
        )
        return False


# =====================================================
# REGISTRO DE ACTIVIDAD
# =====================================================

def registrar_evento_github(
    usuario,
    accion,
    cliente="N/A",
    max_intentos=2,
):
    """
    Agrega un evento a registro_actividad.csv.

    Incluye un reintento si GitHub devuelve conflicto de SHA
    por una escritura simultánea.
    """

    url_registro = (
        f"https://api.github.com/repos/"
        f"{REPO_OWNER}/{REPO_NAME}/contents/"
        f"registro_actividad.csv"
    )

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    nueva_fila = {
        "fecha_hora": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "usuario": normalizar_texto(usuario).upper(),
        "accion": normalizar_texto(accion),
        "cliente": (
            normalizar_texto(cliente)
            if cliente
            else "No especificado"
        ),
    }

    for intento in range(max_intentos):
        try:
            respuesta_get = requests.get(
                url_registro,
                headers=headers,
                timeout=10,
            )

            if respuesta_get.status_code != 200:
                st.error(
                    "No se pudo leer registro_actividad.csv. "
                    f"Código de GitHub: "
                    f"{respuesta_get.status_code}"
                )
                return False

            file_data = respuesta_get.json()
            sha_actual = file_data["sha"]

            contenido = base64.b64decode(
                file_data["content"]
            ).decode("utf-8-sig")

            try:
                df_log = pd.read_csv(
                    StringIO(contenido)
                )
            except pd.errors.EmptyDataError:
                df_log = pd.DataFrame(
                    columns=[
                        "fecha_hora",
                        "usuario",
                        "accion",
                        "cliente",
                    ]
                )

            columnas_log = [
                "fecha_hora",
                "usuario",
                "accion",
                "cliente",
            ]

            for columna in columnas_log:
                if columna not in df_log.columns:
                    df_log[columna] = ""

            df_log = df_log[columnas_log]

            df_log = pd.concat(
                [
                    df_log,
                    pd.DataFrame([nueva_fila]),
                ],
                ignore_index=True,
            )

            csv_actualizado = df_log.to_csv(
                index=False
            )

            contenido_codificado = base64.b64encode(
                csv_actualizado.encode("utf-8")
            ).decode("utf-8")

            payload = {
                "message": (
                    f"Log: {nueva_fila['usuario']} - "
                    f"{nueva_fila['accion']}"
                ),
                "content": contenido_codificado,
                "branch": BRANCH,
                "sha": sha_actual,
            }

            respuesta_put = requests.put(
                url_registro,
                json=payload,
                headers=headers,
                timeout=10,
            )

            if respuesta_put.status_code in [200, 201]:
                return True

            if (
                respuesta_put.status_code == 409
                and intento < max_intentos - 1
            ):
                continue

            st.error(
                "No se pudo guardar el evento en GitHub. "
                f"Código: {respuesta_put.status_code}. "
                f"Detalle: {respuesta_put.text[:300]}"
            )
            return False

        except requests.exceptions.Timeout:
            st.error(
                "GitHub tardó demasiado en responder "
                "al registrar la actividad."
            )
            return False

        except requests.exceptions.ConnectionError:
            st.error(
                "No se pudo conectar con GitHub "
                "para registrar la actividad."
            )
            return False

        except Exception as e:
            st.error(
                f"Error registrando la actividad: {e}"
            )
            return False

    return False


# =====================================================
# LISTADO DE CLIENTES
# =====================================================

@st.cache_data(ttl=300)
def obtener_organizaciones():
    """
    Obtiene el listado de clientes desde Orgs CONCI.csv.
    """

    url_api_orgs = (
        f"https://api.github.com/repos/"
        f"{REPO_OWNER}/{REPO_NAME}/contents/"
        f"Orgs%20CONCI.csv"
    )

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        response = requests.get(
            url_api_orgs,
            headers=headers,
            timeout=10,
        )

        if response.status_code != 200:
            st.error(
                "No se pudo leer Orgs CONCI.csv. "
                f"Código de GitHub: {response.status_code}"
            )
            return []

        file_data = response.json()

        contenido = base64.b64decode(
            file_data["content"]
        ).decode("utf-8-sig")

        df_orgs = pd.read_csv(
            StringIO(contenido)
        )

        df_orgs.columns = (
            df_orgs.columns
            .astype(str)
            .str.strip()
        )

        if "Organización" not in df_orgs.columns:
            st.error(
                "Orgs CONCI.csv no contiene "
                "la columna 'Organización'."
            )
            return []

        organizaciones = (
            df_orgs["Organización"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        organizaciones = organizaciones[
            organizaciones != ""
        ]

        return sorted(
            organizaciones.unique().tolist()
        )

    except Exception as e:
        st.error(
            f"Error cargando organizaciones: {e}"
        )
        return []


# =====================================================
# LECTURA DE ARCHIVOS
# =====================================================

def leer_csv_tractor(archivo):
    """
    Lee un CSV de tractor tratando de soportar
    distintas codificaciones.
    """

    ultimo_error = None

    for encoding in ["utf-8-sig", "utf-8", "latin-1"]:
        try:
            archivo.seek(0)

            df = pd.read_csv(
                archivo,
                encoding=encoding,
            )

            df.columns = (
                df.columns
                .astype(str)
                .str.strip()
            )

            columnas_obligatorias = {
                "Número de serie de la máquina",
                "Alías",
                "Categoría",
                "Serie",
                "Valor",
            }

            faltantes = columnas_obligatorias.difference(
                df.columns
            )

            if faltantes:
                raise ValueError(
                    "Faltan las siguientes columnas: "
                    + ", ".join(sorted(faltantes))
                )

            df["Categoría"] = (
                df["Categoría"]
                .astype(str)
                .apply(normalizar_texto)
            )

            df["Serie"] = (
                df["Serie"]
                .astype(str)
                .apply(normalizar_texto)
            )

            df["Valor"] = convertir_numerico(
                df["Valor"]
            ).fillna(0)

            df["Número de serie de la máquina"] = (
                df["Número de serie de la máquina"]
                .astype(str)
                .str.strip()
                .str.upper()
            )

            return df

        except Exception as e:
            ultimo_error = e

    raise ValueError(
        f"No se pudo leer el CSV. {ultimo_error}"
    )


def leer_excel_ociosos(archivo):
    """
    Lee y normaliza el Excel de motivos ociosos.
    """

    archivo.seek(0)

    df = pd.read_excel(
        archivo,
        sheet_name=0,
        engine="openpyxl",
    )

    df.columns = [
        normalizar_texto(columna)
        for columna in df.columns
    ]

    columna_serie = obtener_primera_columna(
        df,
        [
            "Número de serie de la máquina",
            "Numero de serie de la máquina",
            "Número de serie",
        ],
    )

    if columna_serie is None:
        raise ValueError(
            "El Excel no contiene la columna "
            "'Número de serie de la máquina'."
        )

    df[columna_serie] = (
        df[columna_serie]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return df, columna_serie


# =====================================================
# IDENTIFICACIÓN DE TRACTORES
# =====================================================

def obtener_identificacion_tractor(df, numero_orden):
    """
    Obtiene alias y número de serie desde el CSV.
    """

    alias = f"Tractor {numero_orden}"
    numero_serie = ""

    if (
        "Alías" in df.columns
        and df["Alías"].notna().any()
    ):
        alias_detectado = normalizar_texto(
            df["Alías"].dropna().iloc[0]
        )

        if alias_detectado:
            alias = alias_detectado

    if (
        "Número de serie de la máquina" in df.columns
        and df["Número de serie de la máquina"]
        .notna()
        .any()
    ):
        numero_serie = normalizar_texto(
            df["Número de serie de la máquina"]
            .dropna()
            .iloc[0]
        ).upper()

    return alias, numero_serie


# =====================================================
# CÁLCULO DE TECNOLOGÍAS
# =====================================================

def obtener_porcentaje_tecnologia(
    df,
    nombre_categoria,
    series_activas=None,
    series_inactivas=None,
):
    """
    Calcula el porcentaje de utilización de una tecnología:

    horas activas / (horas activas + horas inactivas) * 100
    """

    if series_activas is None:
        series_activas = ["ENC", "AUTO"]

    if series_inactivas is None:
        series_inactivas = ["APAG", "MANUAL"]

    categoria_buscada = normalizar_texto(
        nombre_categoria
    ).casefold()

    categorias_normalizadas = (
        df["Categoría"]
        .astype(str)
        .apply(normalizar_texto)
        .str.casefold()
    )

    df_categoria = df[
        categorias_normalizadas == categoria_buscada
    ].copy()

    if df_categoria.empty:
        return 0.0

    df_categoria["Serie_Normalizada"] = (
        df_categoria["Serie"]
        .astype(str)
        .apply(normalizar_texto)
        .str.upper()
    )

    df_categoria["Valor"] = convertir_numerico(
        df_categoria["Valor"]
    ).fillna(0)

    activas = {
        normalizar_texto(valor).upper()
        for valor in series_activas
    }

    inactivas = {
        normalizar_texto(valor).upper()
        for valor in series_inactivas
    }

    horas_activas = df_categoria.loc[
        df_categoria["Serie_Normalizada"].isin(
            activas
        ),
        "Valor",
    ].sum()

    horas_inactivas = df_categoria.loc[
        df_categoria["Serie_Normalizada"].isin(
            inactivas
        ),
        "Valor",
    ].sum()

    horas_totales = (
        horas_activas
        + horas_inactivas
    )

    if horas_totales <= 0:
        return 0.0

    porcentaje = (
        horas_activas
        / horas_totales
    ) * 100

    return round(
        limitar_porcentaje(porcentaje),
        1,
    )


def obtener_porcentajes_tecnologias(df):
    """
    Calcula los seis porcentajes tecnológicos.
    """

    return {
        "AutoTrac": obtener_porcentaje_tecnologia(
            df,
            COLUMNAS_TECNOLOGIAS["AutoTrac"],
            series_activas=["Enc"],
            series_inactivas=["Apag"],
        ),

        "AutoPath": obtener_porcentaje_tecnologia(
            df,
            COLUMNAS_TECNOLOGIAS["AutoPath"],
            series_activas=["Enc"],
            series_inactivas=["Apag"],
        ),

        "Implement Guidance": obtener_porcentaje_tecnologia(
            df,
            COLUMNAS_TECNOLOGIAS["Implement Guidance"],
            series_activas=["Enc"],
            series_inactivas=["Apag"],
        ),

        "AutoTrac Turn Automation": obtener_porcentaje_tecnologia(
            df,
            COLUMNAS_TECNOLOGIAS[
                "AutoTrac Turn Automation"
            ],
            series_activas=["Enc"],
            series_inactivas=["Apag"],
        ),

        "Efficiency Manager": obtener_porcentaje_tecnologia(
            df,
            COLUMNAS_TECNOLOGIAS["Efficiency Manager"],
            series_activas=["Auto"],
            series_inactivas=["Manual"],
        ),

        "FieldCruise": obtener_porcentaje_tecnologia(
            df,
            COLUMNAS_TECNOLOGIAS["FieldCruise"],
            series_activas=["Enc"],
            series_inactivas=["Apag"],
        ),
    }


# =====================================================
# HORAS EN REPOSO DEL CSV
# =====================================================

def obtener_horas_reposo(df):
    """
    Obtiene las horas totales en reposo desde la categoría
    'Utilización de la máquina'.
    """

    categorias = (
        df["Categoría"]
        .astype(str)
        .apply(normalizar_texto)
        .str.casefold()
    )

    series = (
        df["Serie"]
        .astype(str)
        .apply(normalizar_texto)
        .str.casefold()
    )

    mascara = (
        categorias.eq(
            "Utilización de la máquina".casefold()
        )
        & series.isin(
            [
                "En reposo".casefold(),
                "Ralentí".casefold(),
                "Ralenti".casefold(),
            ]
        )
    )

    horas_reposo = convertir_numerico(
        df.loc[mascara, "Valor"]
    ).fillna(0).sum()

    return round(
        max(float(horas_reposo), 0.0),
        2,
    )


# =====================================================
# MOTIVOS OCIOSOS
# =====================================================

def identificar_columnas_motivos(df_ociosos):
    """
    Identifica las columnas de motivos que terminan en Período,
    excluyendo estados que no representan una razón concreta.
    """

    columnas = []

    for columna in df_ociosos.columns:
        nombre = normalizar_texto(columna)

        if not nombre.endswith("Período"):
            continue

        if nombre in MOTIVOS_EXCLUIDOS:
            continue

        columnas.append(columna)

    return columnas


def calcular_motivos_ociosos(
    df_ociosos,
    columna_serie_ociosos,
    numero_serie,
    horas_reposo,
):
    """
    Calcula:
    - horas con motivos registrados;
    - porcentaje de cobertura sobre el reposo total;
    - detalle de motivos de mayor a menor.
    """

    resultado_vacio = {
        "horas_registradas": 0.0,
        "porcentaje": 0.0,
        "detalle": pd.DataFrame(
            columns=[
                "Motivo",
                "Horas",
                "Participación (%)",
            ]
        ),
        "encontrado": False,
    }

    if df_ociosos is None:
        return resultado_vacio

    if not numero_serie:
        return resultado_vacio

    numero_serie = normalizar_texto(
        numero_serie
    ).upper()

    filas_tractor = df_ociosos[
        df_ociosos[columna_serie_ociosos]
        .astype(str)
        .str.strip()
        .str.upper()
        .eq(numero_serie)
    ].copy()

    if filas_tractor.empty:
        return resultado_vacio

    columnas_motivos = identificar_columnas_motivos(
        df_ociosos
    )

    motivos = []

    for columna in columnas_motivos:
        valores = pd.to_numeric(
            filas_tractor[columna]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .str.strip(),
            errors="coerce",
        ).fillna(0)

        horas = float(valores.sum())

        if horas > 0:
            motivo_limpio = normalizar_texto(
                columna
            ).replace(" Período", "")

            motivos.append(
                {
                    "Motivo": motivo_limpio,
                    "Horas": horas,
                }
            )

    if not motivos:
        return {
            **resultado_vacio,
            "encontrado": True,
        }

    df_detalle = pd.DataFrame(motivos)

    df_detalle = (
        df_detalle.groupby(
            "Motivo",
            as_index=False,
        )["Horas"]
        .sum()
        .sort_values(
            "Horas",
            ascending=False,
        )
        .reset_index(drop=True)
    )

    horas_registradas = float(
        df_detalle["Horas"].sum()
    )

    if horas_reposo > 0:
        porcentaje = (
            horas_registradas
            / horas_reposo
        ) * 100
    else:
        porcentaje = 0.0

    porcentaje = limitar_porcentaje(
        porcentaje
    )

    if horas_registradas > 0:
        df_detalle["Participación (%)"] = (
            df_detalle["Horas"]
            / horas_registradas
            * 100
        ).round(1)
    else:
        df_detalle["Participación (%)"] = 0.0

    df_detalle["Horas"] = (
        df_detalle["Horas"].round(2)
    )

    return {
        "horas_registradas": round(
            horas_registradas,
            2,
        ),
        "porcentaje": round(
            porcentaje,
            1,
        ),
        "detalle": df_detalle,
        "encontrado": True,
    }


# =====================================================
# PUNTAJE DEL TRACTOR
# =====================================================

def calcular_puntaje_tractor(
    df_tractor,
    porcentaje_motivos_ociosos,
):
    """
    Calcula el promedio simple de los siete componentes.
    """

    tecnologias = obtener_porcentajes_tecnologias(
        df_tractor
    )

    componentes = {
        **tecnologias,
        "Motivos ociosos": limitar_porcentaje(
            porcentaje_motivos_ociosos
        ),
    }

    puntaje_total = (
        sum(componentes.values())
        / 7
    )

    return {
        **componentes,
        "Puntaje Total": round(
            puntaje_total,
            1,
        ),
    }


def obtener_clasificacion(puntaje):
    """
    Clasificación visual preliminar.
    """

    if puntaje >= 80:
        return "🟢 Uso alto"

    if puntaje >= 60:
        return "🟡 Uso intermedio"

    return "🔴 Uso bajo"


# =====================================================
# ESTADO DE SESIÓN
# =====================================================

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "usuario" not in st.session_state:
    st.session_state.usuario = ""


# =====================================================
# LOGIN
# =====================================================

if not st.session_state.autenticado:
    st.markdown(
        """
        <style>
        .main .block-container {
            max-width: 450px;
            padding-top: 5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <h2 style="
            text-align: center;
            color: #367c2b;
        ">
            Acceso al Reporte de Tractores
        </h2>
        """,
        unsafe_allow_html=True,
    )

    legajo = st.text_input(
        "Ingresá tu legajo:",
        placeholder="X000000",
    )

    if st.button(
        "Ingresar al reporte",
        use_container_width=True,
    ):
        if verificar_usuario(legajo):
            usuario_limpio = (
                normalizar_texto(legajo).upper()
            )

            registro_correcto = (
                registrar_evento_github(
                    usuario_limpio,
                    "Ingreso al Reporte de Tractores",
                )
            )

            if registro_correcto:
                st.session_state.autenticado = True
                st.session_state.usuario = (
                    usuario_limpio
                )
                st.rerun()

        else:
            st.error(
                "❌ Usuario no autorizado. "
                "Verificá tu legajo."
            )

    st.stop()


# =====================================================
# LOGOS SUPERIORES
# =====================================================

col_logo_izq, col_espacio, col_logo_der = (
    st.columns([1, 4, 1])
)

with col_logo_izq:
    st.image(
        "CSC.png",
        width=170,
    )

with col_logo_der:
    st.image(
        "JD.png",
        width=180,
    )


# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.header(
    "Configuración del Informe"
)

st.sidebar.caption(
    f"Usuario: {st.session_state.usuario}"
)


# =====================================================
# CLIENTE
# =====================================================

lista_clientes = obtener_organizaciones()

cliente = st.sidebar.selectbox(
    "Cliente",
    options=[
        CLIENTE_VACIO,
        *lista_clientes,
    ],
)

cliente_valido = (
    cliente != CLIENTE_VACIO
)

if cliente_valido:
    st.sidebar.success(
        f"Cliente seleccionado:\n\n{cliente}"
    )

st.sidebar.markdown("---")


# =====================================================
# CANTIDAD DE TRACTORES
# =====================================================

cantidad_tractores = st.sidebar.number_input(
    "Cantidad de tractores",
    min_value=1,
    max_value=20,
    value=1,
    step=1,
)

cantidad_tractores = int(
    cantidad_tractores
)

st.sidebar.markdown("---")


# =====================================================
# CARGA DE CSV DE TRACTORES
# =====================================================

st.sidebar.subheader(
    "Archivos de Tractores"
)

archivos_tractores = []

for i in range(cantidad_tractores):
    archivo = st.sidebar.file_uploader(
        f"CSV Tractor {i + 1}",
        type=["csv"],
        key=f"tractor_{i}",
    )

    archivos_tractores.append(
        archivo
    )

st.sidebar.markdown("---")


# =====================================================
# CARGA DEL EXCEL DE MOTIVOS OCIOSOS
# =====================================================

st.sidebar.subheader(
    "Motivos Ociosos"
)

archivo_ociosos = st.sidebar.file_uploader(
    "Excel de motivos ociosos",
    type=["xlsx"],
    key="ociosos",
)


# =====================================================
# PORTADA
# =====================================================

st.title(
    "🚜 Informe de Utilización de Tractores"
)

if cliente_valido:
    st.info(
        f"📋 Cliente: **{cliente}**"
    )
else:
    st.warning(
        "Seleccioná un cliente para confeccionar "
        "el informe."
    )


# =====================================================
# RESUMEN DE CARGA
# =====================================================

cantidad_csv_cargados = sum(
    archivo is not None
    for archivo in archivos_tractores
)

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.metric(
        "Tractores a analizar",
        cantidad_tractores,
    )

with col_b:
    st.metric(
        "CSV cargados",
        (
            f"{cantidad_csv_cargados}/"
            f"{cantidad_tractores}"
        ),
    )

with col_c:
    st.metric(
        "Motivos ociosos",
        (
            "Cargado"
            if archivo_ociosos is not None
            else "Pendiente"
        ),
    )

st.markdown("---")


# =====================================================
# LECTURA DE LOS CSV
# =====================================================

tractores = []

for indice, archivo in enumerate(
    archivos_tractores,
    start=1,
):
    if archivo is None:
        continue

    try:
        df_tractor = leer_csv_tractor(
            archivo
        )

        alias, numero_serie = (
            obtener_identificacion_tractor(
                df_tractor,
                indice,
            )
        )

        tractores.append(
            {
                "orden": indice,
                "archivo": archivo.name,
                "alias": alias,
                "numero_serie": numero_serie,
                "df": df_tractor,
            }
        )

    except Exception as e:
        st.error(
            f"Error leyendo {archivo.name}: {e}"
        )


# =====================================================
# LECTURA DEL EXCEL DE OCIOSIDAD
# =====================================================

df_ociosos = None
columna_serie_ociosos = None

if archivo_ociosos is not None:
    try:
        (
            df_ociosos,
            columna_serie_ociosos,
        ) = leer_excel_ociosos(
            archivo_ociosos
        )

        st.success(
            "Archivo de motivos ociosos "
            "cargado correctamente."
        )

    except Exception as e:
        st.error(
            "Error leyendo el archivo de "
            f"motivos ociosos: {e}"
        )


# =====================================================
# CÁLCULO DEL PUNTAJE Y RANKING
# =====================================================

resultados_ranking = []
resultados_detallados = []

if tractores:
    for tractor in tractores:
        df_tractor = tractor["df"]

        horas_reposo = obtener_horas_reposo(
            df_tractor
        )

        resultado_ociosos = (
            calcular_motivos_ociosos(
                df_ociosos=df_ociosos,
                columna_serie_ociosos=(
                    columna_serie_ociosos
                ),
                numero_serie=tractor[
                    "numero_serie"
                ],
                horas_reposo=horas_reposo,
            )
            if (
                df_ociosos is not None
                and columna_serie_ociosos is not None
            )
            else {
                "horas_registradas": 0.0,
                "porcentaje": 0.0,
                "detalle": pd.DataFrame(),
                "encontrado": False,
            }
        )

        resultado_puntaje = (
            calcular_puntaje_tractor(
                df_tractor,
                resultado_ociosos["porcentaje"],
            )
        )

        fila_ranking = {
            "Tractor": tractor["alias"],
            "Número de serie": tractor[
                "numero_serie"
            ],
            **resultado_puntaje,
        }

        resultados_ranking.append(
            fila_ranking
        )

        resultados_detallados.append(
            {
                **tractor,
                "horas_reposo": horas_reposo,
                "resultado_ociosos": (
                    resultado_ociosos
                ),
                "resultado_puntaje": (
                    resultado_puntaje
                ),
            }
        )


# =====================================================
# RESULTADO GENERAL
# =====================================================

if resultados_ranking:
    df_ranking = pd.DataFrame(
        resultados_ranking
    )

    df_ranking = df_ranking.sort_values(
        by=[
            "Puntaje Total",
            "AutoTrac",
        ],
        ascending=[
            False,
            False,
        ],
    ).reset_index(drop=True)

    df_ranking.insert(
        0,
        "Posición",
        range(
            1,
            len(df_ranking) + 1,
        ),
    )

    df_ranking["Clasificación"] = (
        df_ranking["Puntaje Total"]
        .apply(obtener_clasificacion)
    )

    st.header(
        "1. Resultado general de utilización"
    )

    puntaje_promedio = (
        df_ranking["Puntaje Total"].mean()
    )

    mejor_tractor = df_ranking.iloc[0]

    col_resultado_1, col_resultado_2, col_resultado_3 = (
        st.columns(3)
    )

    with col_resultado_1:
        st.metric(
            "Puntaje promedio de la flota",
            f"{puntaje_promedio:.1f}/100",
        )

    with col_resultado_2:
        st.metric(
            "Tractor mejor posicionado",
            mejor_tractor["Tractor"],
        )

    with col_resultado_3:
        st.metric(
            "Mejor puntaje",
            (
                f"{mejor_tractor['Puntaje Total']:.1f}"
                "/100"
            ),
        )

    st.markdown(
        "### 🏆 Ranking de tractores"
    )

    columnas_ranking = [
        "Posición",
        "Tractor",
        "Número de serie",
        "Puntaje Total",
        "Clasificación",
    ]

    st.dataframe(
        df_ranking[columnas_ranking],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Posición": st.column_config.NumberColumn(
                "Posición",
                format="%d",
            ),
            "Puntaje Total": (
                st.column_config.ProgressColumn(
                    "Puntaje",
                    min_value=0,
                    max_value=100,
                    format="%.1f",
                )
            ),
        },
    )

    st.markdown(
        "### Composición de los puntajes"
    )

    columnas_componentes = [
        "Tractor",
        "AutoTrac",
        "AutoPath",
        "Implement Guidance",
        "AutoTrac Turn Automation",
        "Efficiency Manager",
        "FieldCruise",
        "Motivos ociosos",
        "Puntaje Total",
    ]

    st.dataframe(
        df_ranking[columnas_componentes],
        use_container_width=True,
        hide_index=True,
        column_config={
            columna: st.column_config.ProgressColumn(
                columna,
                min_value=0,
                max_value=100,
                format="%.1f%%",
            )
            for columna in columnas_componentes
            if columna != "Tractor"
        },
    )

    st.caption(
        "El puntaje corresponde al promedio simple "
        "de AutoTrac, AutoPath, Implement Guidance, "
        "AutoTrac Turn Automation, Efficiency Manager, "
        "FieldCruise y cobertura de motivos ociosos."
    )


# =====================================================
# DETALLE INDIVIDUAL
# =====================================================

if resultados_detallados:
    st.markdown("---")

    st.header(
        "2. Detalle individual por tractor"
    )

    for resultado in resultados_detallados:
        alias = resultado["alias"]
        numero_serie = resultado["numero_serie"]
        puntajes = resultado[
            "resultado_puntaje"
        ]
        ociosos = resultado[
            "resultado_ociosos"
        ]

        st.subheader(
            f"🚜 {alias}"
        )

        st.caption(
            f"Número de serie: {numero_serie}"
        )

        col_p1, col_p2, col_p3, col_p4 = (
            st.columns(4)
        )

        with col_p1:
            st.metric(
                "Puntaje general",
                (
                    f"{puntajes['Puntaje Total']:.1f}"
                    "/100"
                ),
            )

        with col_p2:
            st.metric(
                "Horas en reposo",
                (
                    f"{resultado['horas_reposo']:.1f} h"
                ),
            )

        with col_p3:
            st.metric(
                "Horas con motivo",
                (
                    f"{ociosos['horas_registradas']:.1f} h"
                ),
            )

        with col_p4:
            st.metric(
                "Cobertura de motivos",
                (
                    f"{ociosos['porcentaje']:.1f}%"
                ),
            )

        datos_componentes = pd.DataFrame(
            {
                "Componente": [
                    "AutoTrac",
                    "AutoPath",
                    "Implement Guidance",
                    "AutoTrac Turn Automation",
                    "Efficiency Manager",
                    "FieldCruise",
                    "Motivos ociosos",
                ],
                "Porcentaje": [
                    puntajes["AutoTrac"],
                    puntajes["AutoPath"],
                    puntajes[
                        "Implement Guidance"
                    ],
                    puntajes[
                        "AutoTrac Turn Automation"
                    ],
                    puntajes[
                        "Efficiency Manager"
                    ],
                    puntajes["FieldCruise"],
                    puntajes[
                        "Motivos ociosos"
                    ],
                ],
            }
        )

        st.bar_chart(
            datos_componentes,
            x="Componente",
            y="Porcentaje",
            horizontal=True,
            color="#367C2B",
            use_container_width=True,
        )

        if not ociosos["encontrado"]:
            st.warning(
                "No se encontró este número de serie "
                "en el Excel de motivos ociosos. "
                "El componente Motivos ociosos se "
                "calcula con 0%."
            )

        elif not ociosos["detalle"].empty:
            st.markdown(
                "#### Motivos ociosos registrados"
            )

            st.dataframe(
                ociosos["detalle"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Horas": (
                        st.column_config.NumberColumn(
                            "Horas",
                            format="%.2f h",
                        )
                    ),
                    "Participación (%)": (
                        st.column_config.ProgressColumn(
                            "Participación",
                            min_value=0,
                            max_value=100,
                            format="%.1f%%",
                        )
                    ),
                },
            )

        else:
            st.info(
                "El tractor fue encontrado en el Excel, "
                "pero no presenta horas en las columnas "
                "de motivos seleccionadas."
            )

        observaciones = st.text_area(
            "Observaciones:",
            placeholder=(
                "Ingresá observaciones sobre la "
                "utilización del tractor..."
            ),
            height=120,
            key=(
                f"observaciones_"
                f"{resultado['orden']}_"
                f"{numero_serie}"
            ),
        )

        st.markdown("---")


# =====================================================
# PREVISUALIZACIÓN DE DATOS
# =====================================================

with st.expander(
    "Ver datos cargados"
):
    for tractor in tractores:
        st.markdown(
            f"#### {tractor['alias']}"
        )

        st.write(
            f"Archivo: {tractor['archivo']}"
        )

        st.write(
            f"Registros: {len(tractor['df']):,}"
        )

        st.dataframe(
            tractor["df"].head(),
            use_container_width=True,
        )

    if df_ociosos is not None:
        st.markdown(
            "#### Archivo de motivos ociosos"
        )

        st.dataframe(
            df_ociosos.head(),
            use_container_width=True,
        )


# =====================================================
# VALIDACIONES PARA EL INFORME
# =====================================================

todos_los_csv_cargados = (
    cantidad_csv_cargados
    == cantidad_tractores
)

excel_ociosos_cargado = (
    df_ociosos is not None
)

reporte_listo = (
    cliente_valido
    and todos_los_csv_cargados
    and excel_ociosos_cargado
    and len(resultados_ranking) > 0
)


# =====================================================
# BOTÓN FINAL
# =====================================================

if not reporte_listo:
    st.info(
        "Para registrar el reporte debés seleccionar "
        "un cliente, cargar todos los CSV de tractores "
        "y cargar el Excel de motivos ociosos."
    )

if st.button(
    "Generar Reporte PDF",
    use_container_width=True,
    disabled=not reporte_listo,
):
    registro_correcto = registrar_evento_github(
        usuario=st.session_state.usuario,
        accion=(
            "Exportó Reporte de Tractores a PDF"
        ),
        cliente=cliente,
    )

    if registro_correcto:
        st.success(
            "🎉 Reporte registrado correctamente "
            f"para {cliente}."
        )
