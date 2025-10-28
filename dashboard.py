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

st.title("Dashboard de Performance do Fundo")
st.markdown("---")


# ===========================
# SIDEBAR - PARÂMETROS
# ===========================
st.sidebar.header("Parâmetros do Fundo")

taxa_adm = st.sidebar.number_input(
    "Taxa de Administração (%)",
    min_value=0.0,
    max_value=10.0,
    value=1.0,
    step=0.1,
    format="%.2f"
) / 100

fee_rate = st.sidebar.number_input(
    "Taxa de performance (%)",
    min_value=0.0,
    max_value=50.0,
    value=20.0,
    step=0.1,
    format="%.2f"
) / 100


# ===========================
# CARREGAR DADOS
# ===========================
@st.cache_data
def load_data():
    benchmarks = pd.read_excel('Indices.xlsx').set_index('Date')
    benchmarks.index = pd.to_datetime(benchmarks.index)
    return benchmarks

benchmarks = load_data()

if benchmarks is None:
    st.stop()


# ===========================
# SIDEBAR - SELEÇÃO DE BENCHMARK
# ===========================
st.sidebar.markdown("---")
st.sidebar.header("Benchmark para Taxa de Performance")

benchmark_options = list(benchmarks.columns)
selected_benchmark = st.sidebar.selectbox(
    "Selecione o Benchmark:",
    benchmark_options,
    index=0 if len(benchmark_options) > 0 else None
)



# ===========================
# PROCESSAR BENCHMARKS
# ===========================
yearly_prices_benchmarks = benchmarks.resample('YE').last()
yearly_prices_benchmarks.index = yearly_prices_benchmarks.index.year
yearly_prices_benchmarks.index.name = "Ano"

benchmark_returns_pct = yearly_prices_benchmarks.pct_change()
benchmark_selected_prices = yearly_prices_benchmarks[selected_benchmark]
benchmark_returns_selected = benchmark_returns_pct[selected_benchmark]


# ===========================
# DADOS DO FUNDO
# ===========================
total_anual = [
    -3.42, 5.21, 22.63, -16.70, 78.43, 153.09, 10.43,
    -34.31, 51.86, 29.04, 21.02
]
anos_fechamento = list(range(2014, 2026))


# ===========================
# CALCULAR COTA SEM TAXA DE PERFORMANCE (só ADM)
# ===========================
def calcular_cota_sem_performance(retornos_anuais, taxa_adm):
    """Calcula a cota aplicando apenas taxa de administração"""
    anos = list(range(2014, 2014 + len(retornos_anuais) + 1))
    cota = [1.0]
    
    for ret_pct in retornos_anuais:
        cota_apos_retorno = cota[-1] * (1 + ret_pct/100)
        cota_apos_adm = cota_apos_retorno * (1 - taxa_adm)
        cota.append(cota_apos_adm)
    
    return anos, cota

anos_sem_perf, cota_sem_performance = calcular_cota_sem_performance(total_anual, taxa_adm)
cota_sem_perf_series = pd.Series(cota_sem_performance, index=anos_sem_perf)
cota_sem_perf_series.index.name = "Ano"


# ===========================
# CALCULAR COTA COM TAXA DE PERFORMANCE
# ===========================
def calcular_cota_completa(retornos_anuais, benchmark_returns, taxa_adm, fee_rate):
    """Calcula a cota aplicando todas as taxas, incluindo taxa de performance"""
    anos = list(range(2014, 2014 + len(retornos_anuais) + 1))
    
    cota_bruta = [1.0]
    cota_liquida = [1.0]
    hwm = [1.0]
    taxa_performance_paga = [0.0]
    outperformance_values = [0.0]
    paga_taxa = [False]
    
    for i, ret_pct in enumerate(retornos_anuais):
        # 1. Aplica retorno e desconta taxa ADM
        cota_apos_retorno = cota_liquida[-1] * (1 + ret_pct/100)
        cota_apos_taxas_fixas = cota_apos_retorno * (1 - taxa_adm)
        
        # 2. Calcula outperformance vs benchmark
        benchmark_ret = benchmark_returns.iloc[i+1] if i+1 < len(benchmark_returns) else 0
        ret_cota = (cota_apos_taxas_fixas - cota_liquida[-1]) / cota_liquida[-1]
        outperformance = ret_cota - benchmark_ret
        outperformance_value = outperformance * cota_liquida[-1]
        
        # 3. Verifica se paga taxa de performance
        hwm_atual = hwm[-1]
        
        if cota_apos_taxas_fixas > hwm_atual and outperformance_value > 0:
            taxa_perf = outperformance_value * fee_rate
            nova_cota_liquida = cota_apos_taxas_fixas - taxa_perf
            novo_hwm = nova_cota_liquida
            paga = True
        else:
            taxa_perf = 0.0
            nova_cota_liquida = cota_apos_taxas_fixas
            novo_hwm = max(hwm_atual, nova_cota_liquida)
            paga = False
        
        cota_bruta.append(cota_apos_taxas_fixas)
        cota_liquida.append(nova_cota_liquida)
        hwm.append(novo_hwm)
        taxa_performance_paga.append(taxa_perf)
        outperformance_values.append(outperformance_value)
        paga_taxa.append(paga)
    
    return {
        'anos': anos,
        'cota_bruta': cota_bruta,
        'cota_liquida': cota_liquida,
        'hwm': hwm,
        'taxa_performance': taxa_performance_paga,
        'outperformance': outperformance_values,
        'paga_taxa': paga_taxa
    }

# Calcular cota completa (com taxa de performance)
resultado = calcular_cota_completa(total_anual, benchmark_returns_selected, taxa_adm, fee_rate)

cota_com_perf_series = pd.Series(resultado['cota_liquida'], index=resultado['anos'])
cota_com_perf_series.index.name = "Ano"

hwm_series = pd.Series(resultado['hwm'], index=resultado['anos'])
taxa_perf_series = pd.Series(resultado['taxa_performance'], index=resultado['anos'])
paga_taxa_series = pd.Series(resultado['paga_taxa'], index=resultado['anos'])

cota_returns_pct = cota_com_perf_series.pct_change()


# ===========================
# MÉTRICAS PRINCIPAIS
# ===========================
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Cota Atual (só ADM)",
        f"{cota_sem_perf_series.iloc[-1]:.4f}",
        help="Cota com apenas taxa de administração"
    )

with col2:
    st.metric(
        f"Cota Atual (ADM + Perf vs {selected_benchmark})",
        f"{cota_com_perf_series.iloc[-1]:.4f}",
        help="Cota com taxa ADM e taxa de performance"
    )

with col3:
    retorno_total_sem_perf = (cota_sem_perf_series.iloc[-1] / cota_sem_perf_series.iloc[0] - 1) * 100
    st.metric(
        "Retorno Total (sem perf)",
        f"{retorno_total_sem_perf:.2f}%"
    )

with col4:
    total_taxa_perf = taxa_perf_series.sum()
    st.metric(
        "Total Taxa Performance",
        f"{total_taxa_perf:.4f}"
    )

st.markdown("---")


# ===========================
# GRÁFICO 1: COTA SEM TAXA DE PERFORMANCE
# ===========================
st.subheader("Gráfico 1: Cota (apenas com Taxa ADM)")


fig_sem_perf = go.Figure()

fig_sem_perf.add_trace(go.Scatter(
    x=anos_sem_perf,
    y=cota_sem_performance,
    mode='lines+markers',
    name='Cota (só ADM)',
    line=dict(color='blue', width=3),
    marker=dict(size=8)
))

fig_sem_perf.update_layout(
    title=f"Cota com Taxa ADM ({taxa_adm*100:.2f}%) - SEM Taxa de Performance",
    xaxis_title="Ano",
    yaxis_title="Valor da Cota",
    hovermode='x unified',
    height=500
)

st.plotly_chart(fig_sem_perf, use_container_width=True)


# ===========================
# GRÁFICO 2: COTA VS BENCHMARK (COM TAXA DE PERFORMANCE)
# ===========================
st.subheader(f"Gráfico 2: Taxa de Performance - Cota vs {selected_benchmark}")
st.caption(f"Esta cota inclui taxa ADM + taxa de performance calculada sobre o outperformance vs {selected_benchmark}")

benchmark_normalized = benchmark_selected_prices / benchmark_selected_prices.iloc[0]

fig_perf = go.Figure()

fig_perf.add_trace(go.Scatter(
    x=resultado['anos'],
    y=cota_com_perf_series.values,
    mode='lines+markers',
    name='Cota (com perf)',
    line=dict(color='blue', width=3),
    marker=dict(size=8)
))

fig_perf.add_trace(go.Scatter(
    x=resultado['anos'],
    y=benchmark_normalized.values,
    mode='lines+markers',
    name=selected_benchmark,
    line=dict(color='orange', width=3),
    marker=dict(size=8)
))

fig_perf.add_trace(go.Scatter(
    x=resultado['anos'],
    y=hwm_series.values,
    mode='lines',
    name='High Watermark',
    line=dict(color='red', width=2, dash='dash'),
    opacity=0.5
))

for i, ano in enumerate(resultado['anos']):
    if paga_taxa_series.iloc[i]:
        fig_perf.add_vrect(
            x0=ano-0.3, x1=ano+0.3,
            fillcolor="green", opacity=0.1,
            layer="below", line_width=0,
        )

fig_perf.update_layout(
    title=f"Cota vs {selected_benchmark} vs HWM (áreas verdes = taxa paga)",
    xaxis_title="Ano",
    yaxis_title="Valor",
    hovermode='x unified',
    height=500
)

st.plotly_chart(fig_perf, use_container_width=True)

# Info sobre taxa
col1, col2, col3 = st.columns(3)
with col1:
    anos_taxa = paga_taxa_series.sum()
    st.metric("Anos com Taxa Paga", f"{int(anos_taxa)}")
with col2:
    outperf_final = cota_com_perf_series.iloc[-1] - benchmark_normalized.iloc[-1]
    st.metric("Outperformance Acumulado", f"{outperf_final:+.4f}")
with col3:
    if anos_taxa > 0:
        st.metric("Taxa Média/Ano (quando paga)", f"{total_taxa_perf/anos_taxa:.4f}")
    else:
        st.metric("Taxa Média/Ano", "0.0000")


# ===========================
# TABELA: DETALHAMENTO ANUAL
# ===========================
st.subheader("📋 Detalhamento Anual")

df_detalhe = pd.DataFrame({
    'Ano': resultado['anos'][1:],
    'Cota (sem perf)': cota_sem_perf_series.iloc[1:].values,
    'Cota (com perf)': cota_com_perf_series.iloc[1:].values,
    'Diferença': cota_sem_perf_series.iloc[1:].values - cota_com_perf_series.iloc[1:].values,
    'HWM': hwm_series.iloc[1:].values,
    'Taxa Perf.': taxa_perf_series.iloc[1:].values,
    'Pagou Taxa?': ['Sim' if x else 'Não' for x in paga_taxa_series.iloc[1:]]
})

st.dataframe(
    df_detalhe.style.format({
        'Cota (sem perf)': '{:.4f}',
        'Cota (com perf)': '{:.4f}',
        'Diferença': '{:.4f}',
        'HWM': '{:.4f}',
        'Taxa Perf.': '{:.4f}'
    }).apply(
        lambda x: ['background-color: lightgreen' if v == 'Sim' else '' 
                  for v in x], 
        subset=['Pagou Taxa?']
    ),
    use_container_width=True,
    height=400
)


# ===========================
# GRÁFICO 3: RETORNO ACUMULADO (SEM TAXA DE PERFORMANCE)
# ===========================
st.subheader("Gráfico 3: Retorno Acumulado")
st.caption("Cota SEM taxa de performance para comparação justa com benchmarks (que não têm taxa de performance)")

base_prices_benchmarks = yearly_prices_benchmarks.iloc[0]
normalized_benchmarks = yearly_prices_benchmarks / base_prices_benchmarks

cota_plot = cota_sem_perf_series.copy()
cota_plot.name = 'Cota (sem taxa perf)'

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
    title='Retorno Acumulado: Cota (sem taxa perf) vs. Benchmarks',
    markers=True
)

fig_acumulado.update_traces(
    selector={'name': 'Cota (sem taxa perf)'},
    line={'width': 4}
)

fig_acumulado.add_hline(y=1, line_dash="dot", line_color="grey")
fig_acumulado.update_layout(height=500)

st.plotly_chart(fig_acumulado, use_container_width=True)


# ===========================
# COMPARAÇÃO FINAL
# ===========================
st.markdown("---")
st.subheader("Comparação: Impacto da Taxa de Performance")

col1, col2, col3 = st.columns(3)

with col1:
    impacto_abs = cota_sem_perf_series.iloc[-1] - cota_com_perf_series.iloc[-1]
    st.metric(
        "Impacto Absoluto da Taxa Perf",
        f"{impacto_abs:.4f}",
        help="Diferença entre cota sem e com taxa de performance"
    )

with col2:
    impacto_pct = (impacto_abs / cota_sem_perf_series.iloc[-1]) * 100
    st.metric(
        "Impacto Percentual",
        f"{impacto_pct:.2f}%",
        help="Quanto % a taxa de performance reduziu a cota"
    )

with col3:
    st.metric(
        "Total Taxas Pagas",
        f"{total_taxa_perf:.4f}",
        help=f"Soma das taxas de performance pagas vs {selected_benchmark}"
    )

