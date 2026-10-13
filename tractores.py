import streamlit as st
import pandas as pd

# =====================================================
# CONFIGURACIÓN DE PÁGINA
# =====================================================

st.set_page_config(
    page_title="Reporte de Tractores",
    page_icon="🚜",
    layout="wide"
)

# =====================================================
# FUNCIONES (TEMPORALES)
# =====================================================

# REEMPLAZAR DESPUÉS POR LAS FUNCIONES REALES
# verificar_usuario()
# registrar_evento_github()
# obtener_organizaciones()

def verificar_usuario(usuario):
    usuarios_demo = [
        "X000001",
        "X000002",
        "X000003"
    ]

    return usuario.upper() in usuarios_demo


def registrar_evento_github(usuario, accion, cliente="N/A"):
    """
    Reemplazar por tu función actual de GitHub.
    """
    pass


def obtener_organizaciones():

    return [
        "H&H Outfitters SA",
        "La Florida",
        "Los Grobo",
        "El Algarrobo"
    ]


# =====================================================
# LOGIN
# =====================================================

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "usuario" not in st.session_state:
    st.session_state.usuario = ""

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
        unsafe_allow_html=True
    )

    st.title("🚜 Reporte de Tractores")

    usuario = st.text_input(
        "Ingresá tu legajo",
        placeholder="X000000"
    )

    if st.button(
        "Ingresar",
        use_container_width=True
    ):

        if verificar_usuario(usuario):

            st.session_state.autenticado = True
            st.session_state.usuario = usuario.upper()

            registrar_evento_github(
                usuario.upper(),
                "Ingreso al Reporte de Tractores"
            )

            st.rerun()

        else:

            st.error(
                "Usuario no autorizado"
            )

    st.stop()

# =====================================================
# CABECERA
# =====================================================

col1, col2, col3 = st.columns([1,4,1])

with col1:
    st.image("CSC.png", width=170)

with col3:
    st.image("JD.png", width=180)

st.success(
    f"Usuario conectado: {st.session_state.usuario}"
)

# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.header("Configuración del Informe")

# =====================================================
# CLIENTE
# =====================================================

lista_clientes = obtener_organizaciones()

cliente = st.sidebar.selectbox(
    "Cliente",
    options=["Seleccionar Cliente..."] + lista_clientes
)

if cliente != "Seleccionar Cliente...":

    st.sidebar.success(
        f"Cliente seleccionado:\n{cliente}"
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
    step=1
)

st.sidebar.markdown("---")

# =====================================================
# CARGA DE CSVs
# =====================================================

archivos_tractores = []

st.sidebar.subheader(
    "Archivos de Tractores"
)

for i in range(cantidad_tractores):

    archivo = st.sidebar.file_uploader(
        f"Tractor {i + 1}",
        type=["csv"],
        key=f"tractor_{i}"
    )

    if archivo is not None:
        archivos_tractores.append(archivo)

st.sidebar.markdown("---")

# =====================================================
# MOTIVOS OCIOSOS
# =====================================================

archivo_ociosos = st.sidebar.file_uploader(
    "Motivos Ociosos",
    type=["xlsx", "xls"],
    key="ociosos"
)

# =====================================================
# PORTADA
# =====================================================

st.title("🚜 Informe de Utilización de Tractores")

if cliente != "Seleccionar Cliente...":

    st.info(
        f"📋 Cliente: {cliente}"
    )

# =====================================================
# RESUMEN
# =====================================================

col_a, col_b, col_c = st.columns(3)

with col_a:

    st.metric(
        "Tractores a Analizar",
        cantidad_tractores
    )

with col_b:

    st.metric(
        "CSV Cargados",
        len(archivos_tractores)
    )

with col_c:

    st.metric(
        "Motivos Ociosos",
        "✅" if archivo_ociosos else "❌"
    )

st.markdown("---")

# =====================================================
# LECTURA DE CSVs
# =====================================================

tractores = []

for archivo in archivos_tractores:

    try:

        df = pd.read_csv(
            archivo
        )

        tractores.append(df)

    except Exception as e:

        st.error(
            f"Error leyendo {archivo.name}: {e}"
        )

# =====================================================
# LECTURA OCIOSIDAD
# =====================================================

df_ociosos = None

if archivo_ociosos:

    try:

        df_ociosos = pd.read_excel(
            archivo_ociosos
        )

        st.success(
            "Archivo de motivos ociosos cargado correctamente"
        )

    except Exception as e:

        st.error(
            f"Error leyendo archivo de ociosidad: {e}"
        )

# =====================================================
# PREVISUALIZACIÓN
# =====================================================

st.header("Datos Cargados")

for i, df in enumerate(tractores):

    with st.expander(
        f"Tractor {i+1}"
    ):

        st.write(
            f"Registros: {len(df)}"
        )

        st.dataframe(
            df.head()
        )

if df_ociosos is not None:

    st.header(
        "Motivos Ociosos"
    )

    st.dataframe(
        df_ociosos.head()
    )

# =====================================================
# GENERAR INFORME
# =====================================================

if st.button(
    "Generar Reporte PDF",
    use_container_width=True
):

    if cliente == "Seleccionar Cliente...":

        st.warning(
            "Debés seleccionar un cliente."
        )

    else:

        registrar_evento_github(
            st.session_state.usuario,
            "Exportó Reporte Tractores",
            cliente
        )

        st.success(
            f"Reporte registrado para {cliente}"
        )
