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
    layout="wide",
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
    "AutoTrac": "AutoTrac™ Activo",
    "AutoPath": "AutoPath™ Activo",
    "Implement Guidance": (
        "Guiado pasivo de implemento AutoTrac™ Activo"
    ),
    "AutoTrac Turn Automation": (
        "Automatización de maniobras AutoTrac™ Activo"
    ),
    "Efficiency Manager": (
        "Tiempo de activación de Efficiency Manager™ Automático"
    ),
    "FieldCruise": "FieldCruise™ Activado",
}

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

    return " ".join(
        str(valor).strip().split()
    )


def convertir_valor_numerico(valor):
    """
    Convierte un único valor a número.

    Admite:
    - números;
    - porcentajes;
    - coma decimal;
    - celdas vacías.
    """

    if pd.isna(valor):
        return 0.0

    texto = (
        str(valor)
        .replace("%", "")
        .replace(",", ".")
        .strip()
    )

    numero = pd.to_numeric(
        texto,
        errors="coerce",
    )

    if pd.isna(numero):
        return 0.0

    return float(numero)


def convertir_serie_numerica(serie):
    """
    Convierte una serie completa a valores numéricos.
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

    valor = convertir_valor_numerico(valor)

    return max(
        0.0,
        min(valor, 100.0),
    )


def obtener_primera_columna(
    df,
    nombres_posibles,
):
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

    legajo_limpio = normalizar_texto(
        legajo_ingresado
    ).upper()

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
                "No se pudo leer el listado de usuarios "
                "autorizados. "
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
            .str.replace(
                r"\r|\n",
                "",
                regex=True,
            )
            .str.strip()
            .str.upper()
        )

        return (
            legajo_limpio
            in usuarios_autorizados.values
        )

    except requests.exceptions.Timeout:
        st.error(
            "GitHub tardó demasiado en responder "
            "al validar el usuario."
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

    Incluye un reintento si GitHub devuelve
    un conflicto de SHA.
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
        "usuario": normalizar_texto(
            usuario
        ).upper(),
        "accion": normalizar_texto(
            accion
        ),
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
                    "No se pudo leer "
                    "registro_actividad.csv. "
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

            contenido_codificado = (
                base64.b64encode(
                    csv_actualizado.encode("utf-8")
                ).decode("utf-8")
            )

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

            if respuesta_put.status_code in [
                200,
                201,
            ]:
                return True

            if (
                respuesta_put.status_code == 409
                and intento < max_intentos - 1
            ):
                continue

            st.error(
                "No se pudo guardar el evento "
                "en GitHub. "
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
    Obtiene el listado de clientes desde
    Orgs CONCI.csv.
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
# LECTURA DEL EXCEL CONSOLIDADO DE TRACTORES
# =====================================================

def leer_excel_tractores(archivo):
    """
    Lee el Excel consolidado del Analizador de Máquina.

    El archivo debe contener una fila por tractor.
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

    columnas_obligatorias = [
        "Máquina",
        "Modelo",
        "Número de serie de la máquina",
    ]

    faltantes = [
        columna
        for columna in columnas_obligatorias
        if columna not in df.columns
    ]

    if faltantes:
        raise ValueError(
            "Faltan columnas obligatorias: "
            + ", ".join(faltantes)
        )

    df = df.dropna(
        subset=[
            "Número de serie de la máquina"
        ]
    ).copy()

    df["Número de serie de la máquina"] = (
        df["Número de serie de la máquina"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["Máquina"] = (
        df["Máquina"]
        .astype(str)
        .str.strip()
    )

    df["Modelo"] = (
        df["Modelo"]
        .astype(str)
        .str.strip()
    )

    if "Tipo" in df.columns:
        df = df[
            df["Tipo"]
            .astype(str)
            .str.strip()
            .str.casefold()
            .eq("tractor")
        ].copy()

    df = df.drop_duplicates(
        subset=[
            "Número de serie de la máquina"
        ],
        keep="first",
    )

    return df.reset_index(drop=True)



# =====================================================
# LECTURA DEL EXCEL DE MOTIVOS OCIOSOS
# =====================================================

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
# COLUMNAS DE UTILIZACIÓN
# =====================================================

def obtener_columnas_utilizacion(df):
    """
    Identifica las columnas de porcentaje y horas.

    Pandas agrega .1 a los encabezados duplicados.
    """

    return {
        "trabajo_pct": obtener_primera_columna(
            df,
            [
                "Utilización Trabajo",
                "Utilizacion Trabajo",
            ],
        ),

        "trabajo_horas": obtener_primera_columna(
            df,
            [
                "Utilización Trabajo.1",
                "Utilizacion Trabajo.1",
                "Utilización Trabajo horas",
            ],
        ),

        "ralenti_pct": obtener_primera_columna(
            df,
            [
                "Utilización Ralentí",
                "Utilizacion Ralenti",
            ],
        ),

        "ralenti_horas": obtener_primera_columna(
            df,
            [
                "Utilización Ralentí.1",
                "Utilizacion Ralenti.1",
                "Utilización Ralentí horas",
            ],
        ),

        "transporte_pct": obtener_primera_columna(
            df,
            [
                "Utilización Transporte",
                "Utilizacion Transporte",
            ],
        ),

        "transporte_horas": obtener_primera_columna(
            df,
            [
                "Utilización Transporte.1",
                "Utilizacion Transporte.1",
                "Utilización Transporte horas",
            ],
        ),
    }


# =====================================================
# MOTIVOS OCIOSOS
# =====================================================

def identificar_columnas_motivos(df_ociosos):
    """
    Identifica las columnas que representan
    motivos ociosos registrados.
    """

    columnas = []

    for columna in df_ociosos.columns:
        nombre = normalizar_texto(
            columna
        )

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
    horas_ralenti,
):
    """
    Calcula:
    - horas con motivos registrados;
    - porcentaje sobre el ralentí total;
    - detalle ordenado de motivos.
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

    columnas_motivos = (
        identificar_columnas_motivos(
            df_ociosos
        )
    )

    motivos = []

    for columna in columnas_motivos:
        valores = convertir_serie_numerica(
            filas_tractor[columna]
        ).fillna(0)

        horas = float(
            valores.sum()
        )

        if horas > 0:
            motivo_limpio = (
                normalizar_texto(columna)
                .replace(" Período", "")
            )

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

    df_detalle = pd.DataFrame(
        motivos
    )

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

    if horas_ralenti > 0:
        porcentaje = (
            horas_registradas
            / horas_ralenti
            * 100
        )
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
    fila,
    porcentaje_motivos_ociosos,
):
    """
    Calcula el promedio simple de los siete componentes.
    """

    componentes = {}

    for (
        nombre_visible,
        columna_excel,
    ) in COLUMNAS_TECNOLOGIAS.items():

        if columna_excel in fila.index:
            valor = limitar_porcentaje(
                fila[columna_excel]
            )
        else:
            valor = 0.0

        componentes[nombre_visible] = round(
            valor,
            1,
        )

    componentes["Motivos ociosos"] = round(
        limitar_porcentaje(
            porcentaje_motivos_ociosos
        ),
        1,
    )

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
            usuario_limpio = normalizar_texto(
                legajo
            ).upper()

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
# CARGA DEL EXCEL CONSOLIDADO
# =====================================================

st.sidebar.subheader(
    "Datos de los Tractores"
)

archivo_tractores = st.sidebar.file_uploader(
    "Excel consolidado de tractores",
    type=["xlsx"],
    key="excel_tractores",
    help=(
        "Cargá el archivo del Analizador de Máquina "
        "con todos los tractores que querés analizar."
    ),
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
    key="excel_ociosos",
)

# =====================================================
# VARIABLES POR DEFECTO
# =====================================================

fecha_inicio = "-"
fecha_fin = "-"

df_tractores = None
columnas_utilizacion = {}

# =====================================================
# PORTADA
# =====================================================

st.title(
    "🚜 Informe de Utilización de Tractores"
)

col_info1, col_info2 = st.columns(2)

with col_info1:

    if cliente_valido:

        st.subheader(
            f"Cliente: {cliente}"
        )

    else:

        st.subheader(
            "Cliente: No seleccionado"
        )

with col_info2:

    st.markdown(
        f"""
        <div style="
        text-align:right;
        font-size:18px;
        font-weight:bold;
        color:#367c2b;
        ">
        📅 Período:
        {fecha_inicio} al {fecha_fin}
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("---")

# =====================================================
# LECTURA DEL EXCEL CONSOLIDADO
# =====================================================

if archivo_tractores is not None:

    try:

        df_tractores = leer_excel_tractores(
            archivo_tractores
        )

        columnas_utilizacion = (
            obtener_columnas_utilizacion(
                df_tractores
            )
        )

        # -------------------------
        # FILTRO DE MÁQUINAS
        # -------------------------

        lista_maquinas = sorted(
            df_tractores["Máquina"]
            .dropna()
            .unique()
            .tolist()
        )

        maquinas_seleccionadas = st.sidebar.multiselect(
            "Tractores a analizar",
            options=lista_maquinas,
            default=lista_maquinas
        )

        df_tractores = df_tractores[
            df_tractores["Máquina"].isin(
                maquinas_seleccionadas
            )
        ]

        # -------------------------
        # FECHAS
        # -------------------------

        if (
            len(df_tractores) > 0
            and "Fecha de inicio" in df_tractores.columns
            and "Fecha de terminación" in df_tractores.columns
        ):

            fecha_inicio = (
                pd.to_datetime(
                    df_tractores["Fecha de inicio"],
                    errors="coerce"
                )
                .min()
                .strftime("%d/%m/%Y")
            )

            fecha_fin = (
                pd.to_datetime(
                    df_tractores["Fecha de terminación"],
                    errors="coerce"
                )
                .max()
                .strftime("%d/%m/%Y")
            )

        st.success(
            f"Excel consolidado cargado correctamente. "
            f"Tractores detectados: {len(df_tractores)}"
        )

    except Exception as e:

        st.error(
            f"Error leyendo el Excel consolidado: {e}"
        )
# =====================================================
# LECTURA DEL EXCEL DE MOTIVOS OCIOSOS
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
            "Excel de motivos ociosos "
            "cargado correctamente."
        )

    except Exception as e:
        st.error(
            "Error leyendo el Excel de "
            f"motivos ociosos: {e}"
        )



# =====================================================
# CÁLCULO DEL PUNTAJE Y RANKING
# =====================================================

resultados_ranking = []
resultados_detallados = []

if df_tractores is not None:

    columna_trabajo_pct = (
        columnas_utilizacion.get(
            "trabajo_pct"
        )
    )

    columna_trabajo_horas = (
        columnas_utilizacion.get(
            "trabajo_horas"
        )
    )

    columna_ralenti_pct = (
        columnas_utilizacion.get(
            "ralenti_pct"
        )
    )

    columna_ralenti_horas = (
        columnas_utilizacion.get(
            "ralenti_horas"
        )
    )

    columna_transporte_pct = (
        columnas_utilizacion.get(
            "transporte_pct"
        )
    )

    columna_transporte_horas = (
        columnas_utilizacion.get(
            "transporte_horas"
        )
    )

    for indice, fila in df_tractores.iterrows():

        tractor = normalizar_texto(
            fila.get(
                "Máquina",
                f"Tractor {indice + 1}",
            )
        )

        modelo = normalizar_texto(
            fila.get(
                "Modelo",
                "",
            )
        )

        numero_serie = normalizar_texto(
            fila.get(
                "Número de serie de la máquina",
                "",
            )
        ).upper()

        trabajo_pct = (
            limitar_porcentaje(
                fila.get(
                    columna_trabajo_pct,
                    0,
                )
            )
            if columna_trabajo_pct
            else 0.0
        )

        trabajo_horas = (
            convertir_valor_numerico(
                fila.get(
                    columna_trabajo_horas,
                    0,
                )
            )
            if columna_trabajo_horas
            else 0.0
        )

        ralenti_pct = (
            limitar_porcentaje(
                fila.get(
                    columna_ralenti_pct,
                    0,
                )
            )
            if columna_ralenti_pct
            else 0.0
        )

        ralenti_horas = (
            convertir_valor_numerico(
                fila.get(
                    columna_ralenti_horas,
                    0,
                )
            )
            if columna_ralenti_horas
            else 0.0
        )

        transporte_pct = (
            limitar_porcentaje(
                fila.get(
                    columna_transporte_pct,
                    0,
                )
            )
            if columna_transporte_pct
            else 0.0
        )

        transporte_horas = (
            convertir_valor_numerico(
                fila.get(
                    columna_transporte_horas,
                    0,
                )
            )
            if columna_transporte_horas
            else 0.0
        )

        if (
            df_ociosos is not None
            and columna_serie_ociosos is not None
        ):
            resultado_ociosos = (
                calcular_motivos_ociosos(
                    df_ociosos=df_ociosos,
                    columna_serie_ociosos=(
                        columna_serie_ociosos
                    ),
                    numero_serie=numero_serie,
                    horas_ralenti=ralenti_horas,
                )
            )

        else:
            resultado_ociosos = {
                "horas_registradas": 0.0,
                "porcentaje": 0.0,
                "detalle": pd.DataFrame(),
                "encontrado": False,
            }

        resultado_puntaje = (
            calcular_puntaje_tractor(
                fila=fila,
                porcentaje_motivos_ociosos=(
                    resultado_ociosos[
                        "porcentaje"
                    ]
                ),
            )
        )

        fila_ranking = {
            "Tractor": tractor,
            "Modelo": modelo,
            "Número de serie": numero_serie,
            **resultado_puntaje,
            "Trabajo (%)": round(
                trabajo_pct,
                1,
            ),
            "Ralentí (%)": round(
                ralenti_pct,
                1,
            ),
            "Transporte (%)": round(
                transporte_pct,
                1,
            ),
        }

        resultados_ranking.append(
            fila_ranking
        )

        resultados_detallados.append(
            {
                "orden": indice + 1,
                "tractor": tractor,
                "modelo": modelo,
                "numero_serie": numero_serie,
                "trabajo_pct": trabajo_pct,
                "trabajo_horas": trabajo_horas,
                "ralenti_pct": ralenti_pct,
                "ralenti_horas": ralenti_horas,
                "transporte_pct": transporte_pct,
                "transporte_horas": transporte_horas,
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

    df_ranking = (
        df_ranking.sort_values(
            by=[
                "Puntaje Total",
                "AutoTrac",
            ],
            ascending=[
                False,
                False,
            ],
        )
        .reset_index(drop=True)
    )

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
        "Modelo",
        "Número de serie",
        "Puntaje Total",
        "Clasificación",
    ]

    st.dataframe(
        df_ranking[columnas_ranking],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Posición": (
                st.column_config.NumberColumn(
                    "Posición",
                    format="%d",
                )
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

    configuracion_componentes = {}

    for columna in columnas_componentes:
        if columna == "Tractor":
            continue

        configuracion_componentes[columna] = (
            st.column_config.ProgressColumn(
                columna,
                min_value=0,
                max_value=100,
                format="%.1f%%",
            )
        )

    st.dataframe(
        df_ranking[
            columnas_componentes
        ],
        use_container_width=True,
        hide_index=True,
        column_config=(
            configuracion_componentes
        ),
    )

    st.caption(
        "El puntaje corresponde al promedio simple "
        "de AutoTrac, AutoPath, Implement Guidance, "
        "AutoTrac Turn Automation, Efficiency Manager, "
        "FieldCruise y cobertura de motivos ociosos."
    )


# =====================================================
# UTILIZACIÓN OPERATIVA
# =====================================================

if resultados_ranking:

    st.markdown("---")

    st.header(
        "2. Utilización operativa"
    )

    columnas_utilizacion_tabla = [
        "Tractor",
        "Trabajo (%)",
        "Transporte (%)",
        "Ralentí (%)",
    ]

    st.dataframe(
        df_ranking[
            columnas_utilizacion_tabla
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Trabajo (%)": (
                st.column_config.ProgressColumn(
                    "Trabajo",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                )
            ),
            "Transporte (%)": (
                st.column_config.ProgressColumn(
                    "Transporte",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                )
            ),
            "Ralentí (%)": (
                st.column_config.ProgressColumn(
                    "Ralentí",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                )
            ),
        },
    )


# =====================================================
# DETALLE INDIVIDUAL
# =====================================================

if resultados_detallados:

    st.markdown("---")

    st.header(
        "3. Detalle individual por tractor"
    )

    for resultado in resultados_detallados:

        tractor = resultado["tractor"]
        modelo = resultado["modelo"]
        numero_serie = resultado[
            "numero_serie"
        ]

        puntajes = resultado[
            "resultado_puntaje"
        ]

        ociosos = resultado[
            "resultado_ociosos"
        ]

        st.subheader(
            f"🚜 {tractor}"
        )

        st.caption(
            f"Modelo: {modelo} | "
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
                "Trabajo",
                (
                    f"{resultado['trabajo_pct']:.1f}%"
                ),
                delta=(
                    f"{resultado['trabajo_horas']:.1f} h"
                ),
                delta_color="off",
            )

        with col_p3:
            st.metric(
                "Ralentí",
                (
                    f"{resultado['ralenti_pct']:.1f}%"
                ),
                delta=(
                    f"{resultado['ralenti_horas']:.1f} h"
                ),
                delta_color="off",
            )

        with col_p4:
            st.metric(
                "Transporte",
                (
                    f"{resultado['transporte_pct']:.1f}%"
                ),
                delta=(
                    f"{resultado['transporte_horas']:.1f} h"
                ),
                delta_color="off",
            )

        st.markdown(
            "#### Composición del puntaje"
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
            color="#367C2B",
            use_container_width=True,
        )

        st.markdown(
            "#### Registro de motivos ociosos"
        )

        col_o1, col_o2, col_o3 = (
            st.columns(3)
        )

        with col_o1:
            st.metric(
                "Horas totales en ralentí",
                (
                    f"{resultado['ralenti_horas']:.1f} h"
                ),
            )

        with col_o2:
            st.metric(
                "Horas con motivo",
                (
                    f"{ociosos['horas_registradas']:.1f} h"
                ),
            )

        with col_o3:
            st.metric(
                "Cobertura de motivos",
                (
                    f"{ociosos['porcentaje']:.1f}%"
                ),
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
                "##### Motivos ordenados de mayor a menor"
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
                "de motivos ociosos seleccionadas."
            )

        st.text_area(
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

    if df_tractores is not None:
        st.markdown(
            "#### Excel consolidado de tractores"
        )

        st.write(
            f"Tractores detectados: "
            f"{len(df_tractores)}"
        )

        st.dataframe(
            df_tractores,
            use_container_width=True,
        )

    else:
        st.info(
            "Todavía no se cargó el Excel "
            "consolidado de tractores."
        )

    if df_ociosos is not None:
        st.markdown(
            "#### Excel de motivos ociosos"
        )

        st.dataframe(
            df_ociosos,
            use_container_width=True,
        )

    else:
        st.info(
            "Todavía no se cargó el Excel "
            "de motivos ociosos."
        )


# =====================================================
# VALIDACIONES PARA EL INFORME
# =====================================================

excel_tractores_cargado = (
    df_tractores is not None
    and not df_tractores.empty
)

excel_ociosos_cargado = (
    df_ociosos is not None
)

reporte_listo = (
    cliente_valido
    and excel_tractores_cargado
    and excel_ociosos_cargado
    and len(resultados_ranking) > 0
)


# =====================================================
# BOTÓN FINAL
# =====================================================

if not reporte_listo:
    st.info(
        "Para registrar el reporte debés seleccionar "
        "un cliente, cargar el Excel consolidado "
        "de tractores y cargar el Excel de "
        "motivos ociosos."
    )

if st.button(
    "Generar Reporte PDF",
    use_container_width=True,
    disabled=not reporte_listo,
):

    registro_correcto = (
        registrar_evento_github(
            usuario=st.session_state.usuario,
            accion=(
                "Exportó Reporte de Tractores a PDF"
            ),
            cliente=cliente,
        )
    )

    if registro_correcto:
        st.success(
            "🎉 Reporte registrado correctamente "
            f"para {cliente}."
        )
