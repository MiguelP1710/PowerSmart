# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import time, date, datetime
import io
from fpdf import FPDF
from PIL import Image
import streamlit.components.v1 as components # <-- Importante para embeber HTML

# --- CONFIGURACIÓN DE LA PÁGINA Y ESTILOS ---
st.set_page_config(
    page_title="Analizador de Consumo",
    page_icon="⚡",
    layout="wide"
)

def load_css():
    """Función para cargar y aplicar estilos CSS personalizados."""
    css = """
    <style>
        /* Paleta de Colores Solar */
        :root {
            --primary-color: #FFC300; --secondary-color: #003566;
            --background-color: #001d3d; --text-color: #f0f2f6;
            --accent-color: #ffd60a;
        }
        .stApp { background-color: var(--background-color); }
        h1, h2, h3 { color: var(--primary-color) !important; }
        h1 { padding-top: 0.5rem; }
        p, .st-caption, .st-markdown, div[data-baseweb="form-field"] label {
            color: var(--text-color) !important;
        }
        [data-testid="stImage"] img {
            border-radius: 10px; border: 2px solid var(--primary-color);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
            /* Estilo específico para la imagen del bot en sidebar */
             &.bot-image-sidebar {
                 border-radius: 50%; /* Hacerla redonda */
                 border: 3px solid var(--accent-color);
                 margin-bottom: 1rem;
                 display: block; /* Necesario para centrar con margin: auto */
                 margin-left: auto;
                 margin-right: auto;
                 max-width: 100px; /* Limitar tamaño en sidebar */
             }
        }
        .st-emotion-cache-r421ms { /* Contenedores */
            background-color: var(--secondary-color);
            border: 1px solid var(--accent-color); border-radius: 10px; padding: 1rem;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: var(--secondary-color);
            border: 1px solid var(--accent-color); border-radius: 10px; padding: 1rem;
        }
        [data-testid="stTabs"] button {
            color: var(--text-color); border-radius: 5px 5px 0 0;
        }
        [data-testid="stTabs"] button[aria-selected="true"] {
            background-color: var(--primary-color); color: var(--background-color) !important;
            font-weight: bold;
        }
        .stButton button {
            background-color: var(--primary-color); color: var(--background-color) !important;
            border: none; border-radius: 5px; font-weight: bold;
        }
        .stButton button:hover {
            background-color: var(--accent-color); color: var(--background-color) !important;
        }
        [data-testid="stMetric"] {
            background-color: var(--secondary-color); border-left: 5px solid var(--primary-color);
            padding: 1rem; border-radius: 10px;
        }
        [data-testid="stMetricValue"] {
            color: var(--text-color) !important;
            font-size: 2.75rem !important;
        }
        [data-testid="stMetricLabel"] {
             color: rgba(240, 242, 246, 0.65) !important; /* Etiqueta de métrica */
        }
        /* Sidebar Styles */
        [data-testid="stSidebar"] {
             background-color: var(--secondary-color);
             padding-top: 1rem; /* Add some padding at the top */
         }
         [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { /* Sidebar titles */
             color: var(--primary-color) !important;
             text-align: center;
             margin-bottom: 1rem;
         }
         [data-testid="stSidebar"] p, [data-testid="stSidebar"] .stMarkdown { /* Text in sidebar */
             color: var(--text-color) !important;
             /* text-align: center; */ /* Remove center align for better chat layout */
         }
        [data-testid="stFileUploader"] {
            background-color: rgba(0, 53, 102, 0.8); border: 2px dashed var(--primary-color);
            border-radius: 10px;
        }
        /* Contenedor para el chatbot embebido */
        .chatbase-container-sidebar {
            height: 400px; /* Ajusta la altura para la sidebar */
            width: 100%;
            border: none;
            overflow: hidden;
            margin-top: 1rem;
        }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

load_css()

# --- ESTADO DE LA SESIÓN ---
if 'df_consumo' not in st.session_state: st.session_state.df_consumo = pd.DataFrame()
if 'electrodomesticos' not in st.session_state: st.session_state.electrodomesticos = []

# --- FUNCIONES AUXILIARES --- (Sin cambios)
@st.cache_data
def cargar_datos_masivos(uploaded_file):
    try:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = [col.lower().strip() for col in df.columns]
        ts_col = next((c for c in ['timestamp', 'fecha', 'time', 'date'] if c in df.columns), None)
        p_col = next((c for c in ['potencia_kw', 'kw', 'power_kw', 'potencia_w', 'w', 'consumo'] if c in df.columns), None)
        if not ts_col or not p_col: return pd.DataFrame()
        df['Timestamp'] = pd.to_datetime(df[ts_col], errors='coerce'); df.dropna(subset=['Timestamp'], inplace=True); df = df.set_index('Timestamp'); df['Potencia_kW'] = pd.to_numeric(df[p_col], errors='coerce')
        if df['Potencia_kW'].median() > 1000: st.toast("W detectados -> kW.", icon="⚠️"); df['Potencia_kW'] /= 1000.0
        df = df[['Potencia_kW']].sort_index(); df = df[~df.index.duplicated(keep='first')]; return df.asfreq('h', method='ffill')
    except Exception as e: return pd.DataFrame()

def generar_perfil_manual(items: list, year: int):
    if not items: st.warning("No hay electrodomésticos."); return pd.DataFrame()
    idx = pd.date_range(start=f'{year}-01-01 00:00', end=f'{year}-12-31 23:00', freq='h'); idx.name = 'Timestamp'
    perfil = pd.DataFrame(0.0, index=idx, columns=['Potencia_kW'])
    for item in items:
        potencia_kw = (item['potencia_w'] * item['cantidad']) / 1000.0
        dias_de_uso = list(range(item['dias_por_semana']))
        horas_de_uso = item['horas_de_uso']
        if not horas_de_uso: continue
        filtro_dias = perfil.index.dayofweek.isin(dias_de_uso)
        filtro_horas = perfil.index.hour.isin(horas_de_uso)
        perfil.loc[filtro_dias & filtro_horas, 'Potencia_kW'] += potencia_kw
    return perfil

def cargar_perfil_desde_archivo(uploaded_file):
    try:
        uploaded_file.seek(0)
        df_perfil = (pd.read_csv(uploaded_file, skiprows=7) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file, skiprows=7))
        df_perfil.columns = [str(col).strip().split('.')[0] for col in df_perfil.columns]
        if 'Carga' not in df_perfil.columns or 'Potencia (W)' not in df_perfil.columns: return pd.DataFrame()
        hourly_cols = [str(i) for i in range(24) if str(i) in df_perfil.columns]
        items_manuales = []
        for _, row in df_perfil.iterrows():
            nombre = row['Carga']; potencia_w = pd.to_numeric(row['Potencia (W)'], errors='coerce')
            if pd.isna(nombre) or pd.isna(potencia_w) or potencia_w == 0: continue
            horas_de_uso = [int(h) for h in hourly_cols if pd.to_numeric(row[h], errors='coerce') == 1]
            if horas_de_uso: items_manuales.append({"nombre": nombre, "cantidad": 1, "potencia_w": potencia_w, "dias_por_semana": 7, "horas_de_uso": horas_de_uso})
        if not items_manuales: st.warning("Archivo leído, sin datos válidos."); return pd.DataFrame()
        year_actual = date.today().year; df_generado = generar_perfil_manual(items_manuales, year_actual)
        return df_generado
    except Exception as e: return pd.DataFrame()

def generar_reporte_pdf(metrics_diarios: dict, fig_perfil_diario: go.Figure) -> bytes:
    pdf = FPDF()
    pdf.add_page(); pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "Reporte Perfil Consumo Diario", 0, 1, 'C')
    pdf.set_font("Arial", '', 10); pdf.cell(0, 8, f"Generado: {date.today().strftime('%d/%m/%Y')}", 0, 1, 'C'); pdf.ln(10)
    pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, "Métricas Clave (Diarias)", 0, 1, 'L'); pdf.set_font("Arial", '', 11)
    pdf.cell(95, 8, "Pico Potencia:", 1, 0, 'L'); pdf.cell(95, 8, f"{metrics_diarios['pico_kw_diario']:.2f} kW", 1, 1, 'R')
    pdf.cell(95, 8, "Prom. Potencia:", 1, 0, 'L'); pdf.cell(95, 8, f"{metrics_diarios['media_kw_diaria']:.2f} kW", 1, 1, 'R')
    pdf.cell(95, 8, "Consumo Mensual Est.:", 1, 0, 'L'); pdf.cell(95, 8, f"{metrics_diarios['consumo_mensual_kwh']:,.0f} kWh", 1, 1, 'R')
    pdf.cell(95, 8, "Consumo Anual Est.:", 1, 0, 'L'); pdf.cell(95, 8, f"{metrics_diarios['consumo_anual_kwh']:,.0f} kWh", 1, 1, 'R'); pdf.ln(5)
    curva_bytes = io.BytesIO(fig_perfil_diario.to_image(format="png", width=800, height=400, scale=2))
    pdf.add_page(); pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "Perfil Consumo Diario Promedio", 0, 1, 'C'); pdf.ln(5); pdf.image(curva_bytes, x=10, w=pdf.w - 20)
    return bytes(pdf.output())

def generar_reporte_factura_pdf(metrics: dict, df_factura: pd.DataFrame, fig_factura: go.Figure) -> bytes:
    pdf = FPDF()
    pdf.add_page(); pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "Reporte Consumo Factura", 0, 1, 'C')
    pdf.set_font("Arial", '', 10); pdf.cell(0, 8, f"Generado: {date.today().strftime('%d/%m/%Y')}", 0, 1, 'C'); pdf.ln(10)
    pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, "Resumen Anual", 0, 1, 'L'); pdf.set_font("Arial", '', 11)
    pdf.cell(95, 8, "Total Anual:", 1, 0, 'L'); pdf.cell(95, 8, f"{metrics['total_anual']:.1f} kWh", 1, 1, 'R')
    pdf.cell(95, 8, "Prom. Mensual:", 1, 0, 'L'); pdf.cell(95, 8, f"{metrics['promedio_mensual']:.1f} kWh", 1, 1, 'R'); pdf.ln(5)
    pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, "Detalle Mensual", 0, 1, 'L'); pdf.set_font("Arial", 'B', 10)
    pdf.cell(95, 8, "Mes", 1, 0, 'C'); pdf.cell(95, 8, "Consumo (kWh)", 1, 1, 'C')
    pdf.set_font("Arial", '', 10)
    for _, row in df_factura.iterrows(): pdf.cell(95, 8, row['Mes'], 1, 0, 'L'); pdf.cell(95, 8, f"{row['Consumo (kWh)']:.1f}", 1, 1, 'R')
    factura_bytes = io.BytesIO(fig_factura.to_image(format="png", width=800, height=500, scale=2))
    pdf.add_page(); pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "Consumo Anual por Mes", 0, 1, 'C'); pdf.ln(5); pdf.image(factura_bytes, x=10, w=pdf.w - 20)
    return bytes(pdf.output())

# --- INTERFAZ DE USUARIO ---
try:
    image_main = Image.open("macro/consumo.jpg"); col_img_main, col_title = st.columns([0.25, 0.75])
    with col_img_main: st.image(image_main, width=220)
    with col_title: st.title("Analizador de Consumo"); st.caption("Visualiza y entiende tus patrones de consumo eléctrico.")
except FileNotFoundError:
    st.title("⚡ Analizador de Consumo"); st.caption("Visualiza y entiende tus patrones de consumo eléctrico.")

# --- PESTAÑAS (SIN CHATBOT) ---
tab_carga, tab_dashboard, tab_ldc, tab_exportar = st.tabs([
    "📂 Ingreso Datos",
    "📊 Dashboard",
    "⚡ LDC Diario",
    "📤 Exportar"
])


# --- PESTAÑA CARGA DE DATOS ---
# (ESTE BLOQUE AHORA VA PRIMERO, ANTES DEL SIDEBAR)
with st.container(border=True):
    with tab_carga:
        st.header("Paso 1: Ingresa tus datos")
        modo_carga = st.radio("Elige método:", ("Cargar Archivo", "Ingreso Manual", "Factura Mensual"), horizontal=True, label_visibility="collapsed")
        
        # --- (Código para Cargar Archivo, Ingreso Manual, Factura Mensual sin cambios) ---
        if modo_carga == "Cargar Archivo":
            st.subheader("📄 Carga Masiva (CSV/XLSX)")
            st.markdown("Sube **series de tiempo** o **perfil de carga**.")
            archivo = st.file_uploader("Sube archivo", type=['csv', 'xlsx'], label_visibility="collapsed")
            if archivo:
                with st.spinner("Procesando..."):
                    df_cargado_ts = cargar_datos_masivos(archivo)
                    if not df_cargado_ts.empty: st.session_state.df_consumo = df_cargado_ts; st.success(f"✅ Series de tiempo cargadas!")
                    else:
                        df_cargado_perfil = cargar_perfil_desde_archivo(archivo)
                        if not df_cargado_perfil.empty: st.session_state.df_consumo = df_cargado_perfil; st.success(f"✅ Perfil de carga procesado!")
                        else: st.error("Error: Archivo no coincide.")

        elif modo_carga == "Ingreso Manual":
            st.subheader("✍️ Perfil Manual"); st.markdown("Añade electrodomésticos.")
            col1, col2 = st.columns([1.2, 1])
            with col1:
                with st.form("form_manual", border=False):
                    st.markdown("**Añadir Electrodoméstico**")
                    nombre = st.text_input("Nombre", "Foco LED")
                    cantidad = st.number_input("Cantidad", 1, 100, 5, 1)
                    potencia_w = st.number_input("Potencia (W) c/u", 0, 20000, 10, 1)
                    dias_por_semana = st.number_input("Días uso/sem", 1, 7, 7)
                    st.markdown("---")
                    uso_todo_el_dia = st.checkbox("Usar 0-23h", False)
                    rango_diurno_slider = st.slider("Define horario diurno", 0, 23, (6, 18), disabled=uso_todo_el_dia)
                    h_inicio_d, h_fin_d = rango_diurno_slider
                    horas_d_opts = sorted(list(set(range(h_inicio_d, h_fin_d + 1))))
                    horas_n_opts = sorted(list(set(range(24)) - set(horas_d_opts)))
                    st.caption("Horas de uso:")
                    horas_d_sel = st.multiselect(f"DIURNAS ({h_inicio_d}-{h_fin_d}h)", options=horas_d_opts, disabled=uso_todo_el_dia)
                    horas_n_sel = st.multiselect("NOCTURNAS", options=horas_n_opts, disabled=uso_todo_el_dia)
                    if st.form_submit_button("➕ Añadir", use_container_width=True, type="primary"):
                        if uso_todo_el_dia: horas_final = list(range(24))
                        else: horas_final = sorted(list(set(horas_d_sel + horas_n_sel)))
                        if not horas_final: st.warning("No seleccionaste horas.")
                        else:
                            st.session_state.electrodomesticos.append({"nombre": nombre, "cantidad": cantidad, "potencia_w": potencia_w, "dias_por_semana": dias_por_semana, "horas_de_uso": horas_final})
                            st.toast(f"'{nombre}' añadido.", icon="👍")
            with col2:
                st.markdown("**Lista**")
                if st.session_state.electrodomesticos:
                    st.dataframe(pd.DataFrame(st.session_state.electrodomesticos), use_container_width=True, hide_index=True)
                    st.button("🗑️ Limpiar", use_container_width=True, on_click=lambda: st.session_state.update(electrodomesticos=[]))
                else: st.info("Añade aparatos.")
            if st.session_state.electrodomesticos:
                st.subheader("🚀 Generar Perfil"); year_manual = st.number_input("Año", 2020, date.today().year + 1, date.today().year)
                if st.button("⚡ Generar", use_container_width=True, type="primary"):
                    with st.spinner("Calculando..."): df_generado = generar_perfil_manual(st.session_state.electrodomesticos, year_manual)
                    if not df_generado.empty: st.session_state.df_consumo = df_generado; st.success(f"✅ ¡Perfil generado!")

        elif modo_carga == "Factura Mensual":
            st.subheader("🧾 Desde Factura"); st.markdown("Ingresa kWh mensual.")
            with st.form("factura_form"):
                MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]; consumos = {}; cols = st.columns(4)
                for i, mes in enumerate(MESES):
                    with cols[i % 4]: consumos[mes] = st.number_input(f"{mes}", 0.0, 5000.0, 150.0, 10.0, key=f"fact_{mes}", label_visibility="collapsed")
                submitted = st.form_submit_button("📈 Analizar", use_container_width=True, type="primary")
            if submitted:
                consumos_validos = {m: v for m, v in consumos.items() if v > 0}
                if not consumos_validos: st.warning("Ingresa consumo > 0.")
                else:
                    total_anual = sum(consumos_validos.values()); promedio_mensual = np.mean(list(consumos_validos.values())); st.markdown("---"); st.subheader("📊 Resumen Anual")
                    c1, c2 = st.columns(2); c1.metric("⚡ Total Anual", f"{total_anual:,.1f} kWh"); c2.metric("↔️ Prom. Mensual", f"{promedio_mensual:,.1f} kWh", help=f"Promedio {len(consumos_validos)} meses.")
                    df_factura = pd.DataFrame(consumos.items(), columns=["Mes", "kWh"]); df_sorted = df_factura.sort_values(by="kWh", ascending=False)
                    st.markdown("**Consumo Mensual**")
                    fig_factura = px.bar(df_sorted, x="Mes", y="kWh", title="Consumo Mensual", text_auto='.1f'); fig_factura.update_traces(textposition='outside'); fig_factura.update_layout(title_x=0.5, template="plotly_dark", yaxis_title="kWh"); st.plotly_chart(fig_factura, use_container_width=True)
                    st.subheader("📄 Exportar")
                    try:
                        factura_metrics = {'total_anual': total_anual, 'promedio_mensual': promedio_mensual}
                        pdf_data = generar_reporte_factura_pdf(factura_metrics, df_sorted.rename(columns={'kWh': 'Consumo (kWh)'}), fig_factura); st.download_button("📥 PDF Factura", pdf_data, "reporte_factura.pdf", "app/pdf", use_container_width=True)
                    except Exception as e: st.warning(f"PDF requiere 'kaleido'. Error: {e}")


# --- INICIALIZACIÓN DE VARIABLES PARA SIDEBAR ---
# (ESTE BLOQUE AHORA VA DESPUÉS DE tab_carga)
# Define default values for sliders/selects even if data isn't loaded yet
hora_diurna_inicio_val = time(6, 0)
hora_diurna_fin_val = time(18, 0)
escenario_val = "Normal"
porcentaje_diurno_val = 50

# --- SIDEBAR (CON CHATBOT Y FILTROS) ---
# (ESTE BLOQUE AHORA VA DESPUÉS DE tab_carga)
with st.sidebar:
    st.header("🤖 Miguelito")
    try:
        image_bot = Image.open("macro/bot.png")
        st.image(image_bot, caption="Miguelito", use_column_width=False, width=100, output_format='PNG', clamp=True, channels='RGB')
        st.markdown('<style>div[data-testid="stImage"] img.bot-image-sidebar{border-radius:50%;border:3px solid var(--accent-color);}</style>', unsafe_allow_html=True)
        st.markdown(f'<script>document.querySelector(\'img[alt="Miguelito"]\').classList.add("bot-image-sidebar");</script>', unsafe_allow_html=True)
    except FileNotFoundError:
        st.info("💡")

    st.markdown("Pregúntame sobre consumo o esta app.")
    st.markdown("---")

    # --- CÓDIGO EMBEBIDO DE CHATBASE ---
    chatbase_script = """
    <script>
    (function(){if(!window.chatbase||window.chatbase("getState")!=="initialized"){window.chatbase=(...arguments)=>{if(!window.chatbase.q){window.chatbase.q=[]}window.chatbase.q.push(arguments)};window.chatbase=new Proxy(window.chatbase,{get(target,prop){if(prop==="q"){return target.q}return(...args)=>target(prop,...args)}})}const onLoad=function(){const script=document.createElement("script");script.src="https://www.chatbase.co/embed.min.js";script.id="-mv7HDZnIZjawbcECFXUg";script.domain="www.chatbase.co";document.body.appendChild(script)};if(document.readyState==="complete"){onLoad()}else{window.addEventListener("load",onLoad)}})();
    </script>
    """
    components.html(f'<div class="chatbase-container-sidebar">{chatbase_script}</div>', height=410)
    st.caption("Chatbot by Chatbase")

    # --- Filtros y Ajustes ---
    st.markdown("---")
    st.header("⚙️ Filtros y Ajustes")

    # Only show interactive widgets if data is loaded
    # (Esta condición ahora se evalúa DESPUÉS de que tab_carga haya tenido la oportunidad de llenar st.session_state)
    if not st.session_state.df_consumo.empty:
         with st.expander("Filtros Análisis", expanded=True):
             hora_diurna_inicio_val, hora_diurna_fin_val = st.slider(
                 "Define horario diurno", time(0, 0), time(23, 59), (hora_diurna_inicio_val, hora_diurna_fin_val),
                 key = "slider_diurno",
                 help="Define cómo se calculan métricas y gráficos 'Diurnos' y 'Nocturnos'."
             )
         with st.expander("🛠️ Ajustes Perfil", expanded=False):
             st.caption("Simula escenarios."); escenario_val = st.selectbox("Escenario", ["Normal", "Verano / Seca", "Invierno / Lluvias", "Vacaciones"], key="select_escenario");
             porcentaje_diurno_val = st.slider("Reparto Diurno (%)", 0, 100, porcentaje_diurno_val, key="slider_reparto", help="% del consumo en horario diurno.");
    else:
        st.info("Carga datos para ver filtros.")

    # Assign values (either default or from widgets) to be used later
    hora_diurna_inicio = hora_diurna_inicio_val
    hora_diurna_fin = hora_diurna_fin_val
    escenario = escenario_val
    porcentaje_diurno = porcentaje_diurno_val


# --- BLOQUE PRINCIPAL DE VISUALIZACIÓN Y CÁLCULOS ---
# (Se ejecuta solo si hay datos df_consumo)
if not st.session_state.df_consumo.empty:
    # --- !! Asignar df_consumo aquí !! ---
    df_consumo = st.session_state.df_consumo

    # --- Aplicar Ajustes (Usar valores de sidebar) ---
    df_ajustado = df_consumo.copy()
    if escenario == "Verano / Seca": df_ajustado['Potencia_kW'] *= 1.20; df_ajustado.loc[df_ajustado.index.hour.isin(range(14, 22)), 'Potencia_kW'] *= 1.15
    elif escenario == "Invierno / Lluvias": df_ajustado['Potencia_kW'] *= 1.10; df_ajustado.loc[df_ajustado.index.hour.isin(range(18, 23)), 'Potencia_kW'] *= 1.10
    elif escenario == "Vacaciones": df_ajustado['Potencia_kW'] *= 0.60

    total_energia = df_ajustado['Potencia_kW'].sum();
    energia_diurna_actual = df_ajustado.between_time(hora_diurna_inicio, hora_diurna_fin)['Potencia_kW'].sum();
    energia_nocturna_actual = total_energia - energia_diurna_actual
    energia_diurna_deseada = total_energia * (porcentaje_diurno / 100.0);
    energia_nocturna_deseada = total_energia * (1 - porcentaje_diurno / 100.0)
    factor_escala_diurno = energia_diurna_deseada / energia_diurna_actual if energia_diurna_actual > 0 else 0;
    factor_escala_nocturno = energia_nocturna_deseada / energia_nocturna_actual if energia_nocturna_actual > 0 else 0
    df_ajustado.loc[df_ajustado.index.hour.isin(range(hora_diurna_inicio.hour, hora_diurna_fin.hour + 1)), 'Potencia_kW'] *= factor_escala_diurno
    df_ajustado.loc[~df_ajustado.index.hour.isin(range(hora_diurna_inicio.hour, hora_diurna_fin.hour + 1)), 'Potencia_kW'] *= factor_escala_nocturno

    # --- Cálculos ---
    df_perfil_diario = df_ajustado.groupby(df_ajustado.index.hour)['Potencia_kW'].mean()
    df_perfil_diario.index.name = 'Hora'; df_perfil_diario = df_perfil_diario.reset_index()
    total_kwh_diario = df_perfil_diario['Potencia_kW'].sum(); pico_kw_diario = df_perfil_diario['Potencia_kW'].max(); media_kw_diaria = df_perfil_diario['Potencia_kW'].mean()
    consumo_mensual_kwh = total_kwh_diario * 30; consumo_anual_kwh = total_kwh_diario * 365
    metrics_dashboard = {"pico_kw_diario": pico_kw_diario, "media_kw_diaria": media_kw_diaria, "consumo_mensual_kwh": consumo_mensual_kwh, "consumo_anual_kwh": consumo_anual_kwh}
    total_kwh_anual = df_ajustado['Potencia_kW'].sum(); pico_kw_anual = df_ajustado['Potencia_kW'].max(); media_kw_anual = df_ajustado['Potencia_kW'].mean()

    # --- Gráficos ---
    horas_diurnas_list = list(range(hora_diurna_inicio.hour, hora_diurna_fin.hour + 1))
    df_diurno_graf = df_perfil_diario[df_perfil_diario['Hora'].isin(horas_diurnas_list)]; df_nocturno_graf = df_perfil_diario[~df_perfil_diario['Hora'].isin(horas_diurnas_list)]
    fig_diurno = px.line(df_diurno_graf, x='Hora', y='Potencia_kW', title="Perfil Diurno", markers=True, labels={'Hora': 'Hora', 'Potencia_kW': 'kW'}); fig_diurno.update_layout(title_x=0.5, template="plotly_dark")
    fig_nocturno = px.line(df_nocturno_graf, x='Hora', y='Potencia_kW', title="Perfil Nocturno", markers=True, labels={'Hora': 'Hora', 'Potencia_kW': 'kW'}); fig_nocturno.update_layout(title_x=0.5, template="plotly_dark")
    fig_curva = px.line(df_perfil_diario, x='Hora', y='Potencia_kW', title="Perfil Diario (Línea)", markers=True, labels={'Hora': 'Hora', 'Potencia_kW': 'kW'}); fig_curva.update_layout(title_x=0.5, template="plotly_dark")
    fig_barras_diario = px.bar(df_perfil_diario, x='Hora', y='Potencia_kW', title="Perfil Diario (Barras)", labels={'Hora': 'Hora', 'Potencia_kW': 'kW'}); fig_barras_diario.update_layout(title_x=0.5, template="plotly_dark")
    df_heatmap_data = df_ajustado.copy(); df_heatmap_data['Hora'] = df_heatmap_data.index.hour
    dias_map = {0: 'Lun', 1: 'Mar', 2: 'Mié', 3: 'Jue', 4: 'Vie', 5: 'Sáb', 6: 'Dom'}; df_heatmap_data['Día'] = df_heatmap_data.index.dayofweek.map(dias_map)
    dias_ordenados = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']; pivot = pd.pivot_table(df_heatmap_data, values='Potencia_kW', index='Hora', columns='Día', aggfunc='mean').reindex(columns=dias_ordenados)
    fig_heatmap = px.imshow(pivot, labels=dict(x="Día", y="Hora", color="kW"), color_continuous_scale='YlOrRd', aspect='auto'); fig_heatmap.update_yaxes(autorange='reversed'); fig_heatmap.update_layout(title_x=0.5, template="plotly_dark", title="Heatmap Semanal Prom.")
    s_sorted_anual = df_ajustado['Potencia_kW'].sort_values(ascending=False).reset_index(drop=True); pct_tiempo_anual = (np.arange(1, len(s_sorted_anual) + 1) / len(s_sorted_anual)) * 100
    df_ldc_anual = pd.DataFrame({'Potencia_kW': s_sorted_anual, 'Porcentaje_Tiempo': pct_tiempo_anual}); fig_ldc_anual = px.area(df_ldc_anual, x='Porcentaje_Tiempo', y='Potencia_kW', title="LDC Anual", labels={'Porcentaje_Tiempo': '% Horas Año', 'Potencia_kW': 'kW'}); fig_ldc_anual.add_hline(y=pico_kw_anual, line_dash="dot", annotation_text=f"Pico: {pico_kw_anual:.2f} kW"); fig_ldc_anual.add_hline(y=media_kw_anual, line_dash="dash", annotation_text=f"Prom: {media_kw_anual:.2f} kW", line_color="#2ECC71"); fig_ldc_anual.update_layout(title_x=0.5, template="plotly_dark")
    s_sorted_diario = df_perfil_diario['Potencia_kW'].sort_values(ascending=False).reset_index(drop=True); pct_tiempo_diario = (np.arange(1, len(s_sorted_diario) + 1) / len(s_sorted_diario)) * 100
    df_ldc_diario = pd.DataFrame({'Potencia_kW': s_sorted_diario, 'Porcentaje_Tiempo': pct_tiempo_diario}); pico_kw_diario_ldc = metrics_dashboard['pico_kw_diario']; media_kw_diaria_ldc = metrics_dashboard['media_kw_diaria']
    fig_ldc_diario = px.area(df_ldc_diario, x='Porcentaje_Tiempo', y='Potencia_kW', title="LDC Diaria", labels={'Porcentaje_Tiempo': '% Horas Día', 'Potencia_kW': 'kW'}); fig_ldc_diario.add_hline(y=pico_kw_diario_ldc, line_dash="dot", annotation_text=f"Pico: {pico_kw_diario_ldc:.2f} kW"); fig_ldc_diario.add_hline(y=media_kw_diaria_ldc, line_dash="dash", annotation_text=f"Prom: {media_kw_diaria_ldc:.2f} kW", line_color="#2ECC71"); fig_ldc_diario.update_layout(title_x=0.5, template="plotly_dark")

# --- RENDERIZADO DE PESTAÑAS (depende de si hay datos) ---
with st.container(border=True):
    with tab_dashboard:
        st.header("Dashboard")
        if st.session_state.df_consumo.empty: st.info("👆 Carga/genera datos.")
        else:
            st.subheader("📊 Métricas Clave")
            cols1, cols2 = st.columns(2)
            with cols1: st.metric("🔼 Pico Diario", f"{metrics_dashboard['pico_kw_diario']:.2f} kW"); st.metric("📅 Consumo Mensual", f"{metrics_dashboard['consumo_mensual_kwh']:,.0f} kWh")
            with cols2: st.metric("↔️ Prom. Diario", f"{metrics_dashboard['media_kw_diaria']:.2f} kW"); st.metric("🗓️ Consumo Anual", f"{metrics_dashboard['consumo_anual_kwh']:,.0f} kWh")
            st.markdown("---"); st.subheader("📈 Perfiles Diarios")
            st.plotly_chart(fig_curva, use_container_width=True)
            st.plotly_chart(fig_barras_diario, use_container_width=True)
            st.markdown("---"); st.subheader("⏱️ Diurno/Nocturno")
            c1, c2 = st.columns(2)
            with c1: st.plotly_chart(fig_diurno, use_container_width=True)
            with c2: st.plotly_chart(fig_nocturno, use_container_width=True)
            st.markdown("---"); st.subheader("🔥 Heatmap Semanal")
            st.caption("Potencia prom. (kW) por hora y día.")
            st.plotly_chart(fig_heatmap, use_container_width=True)

with st.container(border=True):
    with tab_ldc:
        st.header("LDC - Diario")
        if st.session_state.df_consumo.empty: st.info("👆 Carga/genera datos.")
        else:
            st.subheader("⚡ LDC (Diaria)")
            st.info("Ordena potencia diaria (0-23h) de > a <.")
            st.plotly_chart(fig_ldc_diario, use_container_width=True)
            with st.expander("Ver tabla"): st.dataframe(df_ldc_diario, use_container_width=True)

with st.container(border=True):
    with tab_exportar:
        st.header("Exportar")
        if st.session_state.df_consumo.empty: st.warning("No hay datos.")
        else:
            filename = "perfil_consumo"
            st.subheader("🗂️ Datos (Anual)")
            csv_data = df_ajustado.to_csv().encode('utf-8'); xlsx_output = io.BytesIO(); df_ajustado.to_excel(xlsx_output, engine='openpyxl'); xlsx_data = xlsx_output.getvalue()
            c1, c2 = st.columns(2)
            c1.download_button("📥 CSV", csv_data, f"{filename}_anual.csv", "text/csv", use_container_width=True)
            c2.download_button("📥 XLSX", xlsx_data, f"{filename}_anual.xlsx", use_container_width=True)
            st.subheader("🖼️ Gráficos (PNG)"); c1, c2, c3, c4 = st.columns(4)
            try:
                c1.download_button("Perfil Línea", fig_curva.to_image(format='png', scale=2), f"perfil_linea_{filename}.png", use_container_width=True)
                c2.download_button("Perfil Barras", fig_barras_diario.to_image(format='png', scale=2), f"perfil_barras_{filename}.png", use_container_width=True)
                c3.download_button("Heatmap Semanal", fig_heatmap.to_image(format='png', scale=2), f"heatmap_{filename}.png", use_container_width=True)
                c4.download_button("LDC Anual", fig_ldc_anual.to_image(format='png', scale=2), f"ldc_anual_{filename}.png", use_container_width=True)
            except Exception as e: st.warning(f"PNG requiere 'kaleido'. Error: {e}")
            st.subheader("📜 Reporte (PDF)")
            try:
                pdf_data = generar_reporte_pdf(metrics_dashboard, fig_curva)
                st.download_button("📄 PDF (Diario)", pdf_data, f"reporte_diario_{filename}.pdf", "app/pdf", use_container_width=True, type="primary")
            except Exception as e: st.warning(f"PDF requiere 'kaleido'. Error: {e}")

# --- MENSAJES INICIALES SI NO HAY DATOS ---
if st.session_state.df_consumo.empty:
    with tab_dashboard: st.info("👆 Carga/genera datos en 'Ingreso Datos'.")
    with tab_ldc: st.info("👆 Carga/genera datos en 'Ingreso Datos'.")
    with tab_exportar: st.info("👆 Carga/genera datos en 'Ingreso Datos'.")
    # Chatbot en sidebar no necesita mensaje aquí