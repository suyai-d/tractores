import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Reporte de Tractores",
    page_icon="🚜",
    layout="wide"
)

# ==========================
# LOGOS
# ==========================

col1, col2, col3 = st.columns([1,4,1])

with col1:
    st.image("CSC.png", width=170)

with col3:
    st.image("JD.png", width=180)

# ==========================
# SIDEBAR
# ==========================

st.sidebar.header("Configuración del Informe")

# Cliente

cliente = st.sidebar.text_input(
    "Cliente"
)

# Cantidad de tractores

cantidad_tractores = st.sidebar.number_input(
    "Cantidad de tractores",
    min_value=1,
    max_value=20,
    value=1,
    step=1
)

st.sidebar.markdown("---")

# ==========================
# CARGA DE CSV DE TRACTORES
# ==========================

archivos_tractores = []

st.sidebar.subheader("Archivos de Tractores")

for i in range(cantidad_tractores):

    archivo = st.sidebar.file_uploader(
        f"Tractor {i+1}",
        type=["csv"],
        key=f"tractor_{i}"
    )

    if archivo:
        archivos_tractores.append(archivo)

st.sidebar.markdown("---")

# ==========================
# MOTIVOS OCIOSOS
# ==========================

archivo_ociosos = st.sidebar.file_uploader(
    "Motivos Ociosos",
    type=["xlsx", "xls"],
    key="ociosos"
)

# ==========================
# PORTADA
# ==========================

st.title("🚜 Informe de Utilización de Tractores")

if cliente:
    st.info(f"Cliente: {cliente}")

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.metric(
        "Tractores Seleccionados",
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

# ==========================
# LECTURA DE TRACTORES
# ==========================

tractores = []

for archivo in archivos_tractores:

    try:

        df = pd.read_csv(archivo)

        tractores.append(df)

    except Exception as e:

        st.error(
            f"Error leyendo {archivo.name}: {e}"
        )

# ==========================
# LECTURA OCIOSIDAD
# ==========================

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

# ==========================
# PREVISUALIZACIÓN
# ==========================

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

    st.header("Motivos Ociosos")

    st.dataframe(
        df_ociosos.head()
    )
