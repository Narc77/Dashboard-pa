import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# ===========================
# CONFIGURAÇÃO DA PÁGINA
# ===========================
st.set_page_config(
    page_title="Dashboard de Performance do Fundo",
    layout="wide",
    initial_sidebar_state="expanded"
)


st.title("📊 Dashboard de Performance do Fundo")
st.markdown("---")


# ===========================
# SIDEBAR - PARÂMETROS
# ===========================
st.sidebar.header("⚙️ Parâmetros do Fundo")



taxa_adm = st.sidebar.number_input(
    "Taxa de Administração (%)",
    min_value=0.0,
    max_value=10.0,
    value=1.0,
    step=0.1,
    format="%.2f"
) / 100


despesas = st.sidebar.number_input(
    "Despesas (%)",
    min_value=0.0,
    max_value=5.0,
    value=0.10,
    step=0.01,
    format="%.2f"
) / 100


st.sidebar.markdown("---")
st.sidebar.markdown(f"**Total de Custos Anuais:** {(taxa_adm + despesas)*100:.2f}%")


# ===========================
# CARREGAR DADOS
# ===========================
@st.cache_data
def load_data():
    try:
        benchmarks = pd.read_excel('Indices.xlsx').set_index('Date')
        benchmarks.index = pd.to_datetime(benchmarks.index)
        return benchmarks
    except:
        st.error("Erro ao carregar o arquivo 'indices.xlsx'. Certifique-se de que o arquivo existe.")
        return None


benchmarks = load_data()


if benchmarks is None:
    st.stop()


# ===========================
# SIDEBAR - SELEÇÃO DE BENCHMARK
# ===========================
st.sidebar.markdown("---")
st.sidebar.header("📊 Benchmark para Análise")

benchmark_options = list(benchmarks.columns)
selected_benchmark = st.sidebar.selectbox(
    "Selecione o Benchmark:",
    benchmark_options,
    index=0 if len(benchmark_options) > 0 else None
)


# ===========================
# DADOS DO FUNDO
# ===========================
total_anual = [
    -3.42, 5.21, 22.63, -16.70, 78.43, 153.09, 10.43,
    -34.31, 51.86, 29.04, 21.02
]
anos_fechamento = list(range(2014, 2026))


# ===========================
# CALCULAR COTA COM TAXAS
# ===========================
def calcular_cota_com_taxas(retornos_anuais, taxa_adm, despesas):
    """Calcula a cota aplicando taxas de administração e despesas"""
    cota = [1.0]
    custo_total_anual = taxa_adm + despesas
    
    for ret_pct in retornos_anuais:
        # Aplica retorno e desconta custos fixos
        nova_cota = cota[-1] * (1 + ret_pct/100) * (1 - custo_total_anual)
        cota.append(nova_cota)
    
    return cota


cota_fechamento_anual_acumulada = calcular_cota_com_taxas(total_anual, taxa_adm, despesas)
cota_series_precos = pd.Series(cota_fechamento_anual_acumulada, index=anos_fechamento)
cota_series_precos.index.name = "Ano"


# ===========================
# PROCESSAR BENCHMARKS
# ===========================
yearly_prices_benchmarks = benchmarks.resample('YE').last()
yearly_prices_benchmarks.index = yearly_prices_benchmarks.index.year
yearly_prices_benchmarks.index.name = "Ano"


# Retornos
cota_returns_pct = cota_series_precos.pct_change()
benchmark_returns_pct = yearly_prices_benchmarks.pct_change()


# Outperformance
outperformance_pct = benchmark_returns_pct.rsub(cota_returns_pct, axis=0)


# ===========================
# CALCULAR HIGH WATERMARK
# ===========================
hwm_end_of_year = cota_series_precos.expanding().max()
hwm_start_of_year = hwm_end_of_year.shift(1)
profit_vs_hwm = cota_series_precos - hwm_start_of_year
is_above_hwm = (profit_vs_hwm > 0)


# ===========================
# TAXA DE PERFORMANCE (para o benchmark selecionado)
# ===========================
cota_start_of_year = cota_series_precos.shift(1)

# Outperformance vs benchmark selecionado
outperformance_selected = outperformance_pct[selected_benchmark]
outperformance_profit_selected = outperformance_selected * cota_start_of_year
positive_outperformance_selected = outperformance_profit_selected.clip(lower=0)

# Condição: outperformance > 0 E cota > HWM
has_positive_outperformance = (positive_outperformance_selected > 0)
paga_taxa_selected = has_positive_outperformance & is_above_hwm

# Taxa de performance
fee_rate = 0.20
fee_base_selected = positive_outperformance_selected.where(is_above_hwm, 0)
performance_fee_selected = (fee_base_selected * fee_rate).dropna()


# ===========================
# TAXA DE PERFORMANCE (TODOS OS BENCHMARKS)
# ===========================
outperformance_profit_dollars = outperformance_pct.multiply(cota_start_of_year, axis=0)
positive_outperformance_profit = outperformance_profit_dollars.clip(lower=0)
fee_base = positive_outperformance_profit.where(is_above_hwm, 0)
final_performance_fee = (fee_base * fee_rate).dropna()
final_performance_fee.index.name = "Ano"


# ===========================
# MÉTRICAS PRINCIPAIS
# ===========================
col1, col2 = st.columns(2)


with col1:
    st.metric(
        "Cota Atual (2025)",
        f"{cota_series_precos.iloc[-1]:.4f}",
        f"{total_anual[-1]:+.2f}%"
    )


with col2:
    retorno_total = (cota_series_precos.iloc[-1] / cota_series_precos.iloc[0] - 1) * 100
    st.metric(
        "Retorno Total",
        f"{retorno_total:.2f}%"
    )



st.markdown("---")


# ===========================
# GRÁFICO 1: HIGH WATERMARK
# ===========================
st.subheader("📈 Evolução da Cota")


fig_hwm = go.Figure()


# Cota
fig_hwm.add_trace(go.Scatter(
    x=anos_fechamento,
    y=cota_series_precos.values,
    mode='lines+markers',
    name='Cota',
    line=dict(color='blue', width=3),
    marker=dict(size=8)
))



fig_hwm.update_layout(
    title="Cota",
    xaxis_title="Ano",
    yaxis_title="Valor da Cota",
    hovermode='x unified',
    height=500
)


st.plotly_chart(fig_hwm, use_container_width=True)


# ===========================
# GRÁFICO 2: COTA VS BENCHMARK (Taxa de Performance)
# ===========================
st.subheader(f"💰 Taxa de Performance: Cota vs {selected_benchmark}")

# Normalizar benchmark para começar em 1 (igual à cota)
benchmark_selected_prices = yearly_prices_benchmarks[selected_benchmark]
benchmark_normalized = benchmark_selected_prices / benchmark_selected_prices.iloc[0]

fig_perf = go.Figure()

# Cota
fig_perf.add_trace(go.Scatter(
    x=anos_fechamento,
    y=cota_series_precos.values,
    mode='lines+markers',
    name='Cota',
    line=dict(color='blue', width=3),
    marker=dict(size=8)
))

# Benchmark normalizado
fig_perf.add_trace(go.Scatter(
    x=anos_fechamento,
    y=benchmark_normalized.values,
    mode='lines+markers',
    name=selected_benchmark,
    line=dict(color='orange', width=3),
    marker=dict(size=8)
))

# HWM para referência
fig_perf.add_trace(go.Scatter(
    x=anos_fechamento,
    y=hwm_end_of_year.values,
    mode='lines',
    name='High Watermark',
    line=dict(color='red', width=2, dash='dash'),
    opacity=0.5
))

# Adicionar regiões onde taxa foi paga (CORRETO: outperformance > 0 E cota > HWM)
for i, ano in enumerate(anos_fechamento):
    if i > 0 and paga_taxa_selected.iloc[i]:
        fig_perf.add_vrect(
            x0=ano-0.3, x1=ano+0.3,
            fillcolor="green", opacity=0.1,
            layer="below", line_width=0,
        )

fig_perf.update_layout(
    title=f"Cota vs {selected_benchmark} vs HWM (áreas verdes = taxa paga)",
    xaxis_title="Ano",
    yaxis_title="Valor ",
    hovermode='x unified',
    height=500
)

st.plotly_chart(fig_perf, use_container_width=True)

# Info sobre taxa
col1, col2 = st.columns(2)
with col1:
    anos_taxa = paga_taxa_selected.iloc[1:].sum()
    st.metric("Anos com Taxa Paga", f"{anos_taxa}")
with col2:
    outperf_final = cota_series_precos.iloc[-1] - benchmark_normalized.iloc[-1]
    st.metric("Outperformance Acumulado", f"{outperf_final:+.4f}")


# ===========================
# GRÁFICO 4: RETORNO ACUMULADO
# ===========================
st.subheader("📈 Retorno Acumulado")


base_prices_benchmarks = yearly_prices_benchmarks.iloc[0]
normalized_benchmarks = yearly_prices_benchmarks / base_prices_benchmarks


cota_plot = cota_series_precos.copy()
cota_plot.name = 'Cota'


plot_data_acumulado = pd.concat([cota_plot, normalized_benchmarks], axis=1)
plot_data_acumulado_long = plot_data_acumulado.reset_index().melt(
    id_vars='Ano',
    var_name='Ativo',
    value_name='Retorno Acumulado'
)


fig_acumulado = px.line(
    plot_data_acumulado_long,
    x='Ano',
    y='Retorno Acumulado',
    color='Ativo',
    title='Retorno Acumulado: Cota vs. Benchmarks ',
    markers=True
)


fig_acumulado.update_traces(
    selector={'name': 'Cota'},
    line={'width': 4}
)


fig_acumulado.add_hline(y=1, line_dash="dot", line_color="grey")
fig_acumulado.update_layout(height=500)


st.plotly_chart(fig_acumulado, use_container_width=True)


# ===========================
# RODAPÉ
# ===========================
st.markdown("---")
st.markdown(f"""
**Notas:**
- A cota já incorpora taxa de administração e despesas
- Taxa de performance(20%) é cobrada quando:
  1. Cota tem outperformance POSITIVO vs {selected_benchmark}
  2. E a cota está acima do High Watermark (HWM)
""")
