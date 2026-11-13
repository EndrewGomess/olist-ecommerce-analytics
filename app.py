"""
Olist Analytics Dashboard
Aplicação interativa Streamlit com DuckDB & dbt Core
Tomada de decisão executiva e monitoramento logístico do E-Commerce brasileiro.
"""

import os
import datetime
import random
import numpy as np
import pandas as pd
import duckdb
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ==============================================================================
# 1. Configuração da Página
# ==============================================================================
st.set_page_config(
    page_title="Olist Analytics Dashboard",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilização CSS customizada e moderna
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .badge-tech {
        background-color: #E0E7FF;
        color: #4338CA;
        font-size: 0.8rem;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 6px;
        display: inline-block;
        margin-right: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# 2. Funções de Apoio e Formatação
# ==============================================================================
def format_currency_br(val: float) -> str:
    """Formata valor em Real Brasileiro (R$ 1.234,56)."""
    if pd.isna(val) or val is None:
        return "R$ 0,00"
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_number_br(val: int) -> str:
    """Formata número inteiro no padrão brasileiro (1.234)."""
    if pd.isna(val) or val is None:
        return "0"
    return f"{int(val):,}".replace(",", ".")


# ==============================================================================
# 3. Gerador de Dados de Demonstração (Fallback Gracioso)
# ==============================================================================
def generate_mock_data(n_records: int = 1200) -> pd.DataFrame:
    """Gera dados simulados realistas com o mesmo schema de fct_orders da Olist."""
    np.random.seed(42)
    random.seed(42)

    start_date = datetime.datetime(2017, 1, 1)
    end_date = datetime.datetime(2018, 8, 31)
    total_seconds = int((end_date - start_date).total_seconds())

    statuses = [
        "delivered",
        "shipped",
        "canceled",
        "invoiced",
        "processing",
        "unavailable",
    ]
    status_weights = [0.93, 0.03, 0.015, 0.01, 0.01, 0.005]

    states = [
        "SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "ES", "GO",
        "PE", "CE", "PA", "MT", "MS", "MA", "PB", "RN", "AL", "PI"
    ]
    state_weights = [
        0.42, 0.13, 0.11, 0.05, 0.05, 0.04, 0.03, 0.025, 0.02, 0.02,
        0.015, 0.015, 0.015, 0.01, 0.01, 0.01, 0.01, 0.005, 0.005, 0.01
    ]

    records = []
    for i in range(1, n_records + 1):
        order_id = f"demo_ord_{i:06d}"
        customer_id = f"demo_cust_{i:06d}"
        status = np.random.choice(statuses, p=status_weights)
        state = np.random.choice(states, p=state_weights)

        # Datas
        sec_offset = random.randint(0, total_seconds)
        purchase_at = start_date + datetime.timedelta(seconds=sec_offset)
        approved_at = purchase_at + datetime.timedelta(hours=random.uniform(1, 24))

        # Prazos e entrega
        estimated_delivery_days = random.randint(10, 32)
        estimated_at = purchase_at + datetime.timedelta(days=estimated_delivery_days)

        if status == "delivered":
            carrier_at = approved_at + datetime.timedelta(hours=random.uniform(12, 72))
            
            # 88% no prazo, 12% atrasado
            is_delayed = random.random() < 0.12
            if is_delayed:
                actual_days = estimated_delivery_days + random.uniform(1, 14)
            else:
                actual_days = estimated_delivery_days - random.uniform(1, 10)
                actual_days = max(2.0, actual_days)
            
            delivered_at = purchase_at + datetime.timedelta(days=actual_days)
            delivery_time_days = round(actual_days, 2)
            delivery_margin_days = round(estimated_delivery_days - actual_days, 2)
        else:
            carrier_at = None
            delivered_at = None
            delivery_time_days = None
            delivery_margin_days = None

        # Valores
        total_items = np.random.choice([1, 2, 3, 4], p=[0.82, 0.12, 0.04, 0.02])
        total_distinct = min(total_items, np.random.choice([1, 2], p=[0.9, 0.1]))
        
        # Preço log-normal realista
        base_item_price = float(np.random.lognormal(mean=4.2, sigma=0.85))
        total_items_amount = round(base_item_price * total_items, 2)
        total_freight_amount = round(15.0 + (total_items * random.uniform(4.0, 12.0)), 2)
        total_order_amount = round(total_items_amount + total_freight_amount, 2)

        records.append({
            "order_id": order_id,
            "customer_id": customer_id,
            "order_status": status,
            "customer_state": state,
            "order_purchase_at": purchase_at,
            "order_approved_at": approved_at,
            "order_delivered_carrier_at": carrier_at,
            "order_delivered_customer_at": delivered_at,
            "order_estimated_delivery_at": estimated_at,
            "total_items": total_items,
            "total_distinct_products": total_distinct,
            "total_items_amount": total_items_amount,
            "total_freight_amount": total_freight_amount,
            "total_order_amount": total_order_amount,
            "delivery_time_days": delivery_time_days,
            "delivery_margin_days": delivery_margin_days,
        })

    df = pd.DataFrame(records)
    return df


# ==============================================================================
# 4. Carregamento de Dados (DuckDB com Fallback Seguro)
# ==============================================================================
@st.cache_data(show_spinner=False)
def load_data(force_demo: bool = False):
    """
    Tenta carregar os dados transformados do DuckDB (fct_orders).
    Caso o arquivo não exista ou force_demo seja True, retorna dados simulados.
    """
    if force_demo:
        return generate_mock_data(), "demo"

    # Possíveis locais para o arquivo DuckDB
    candidate_paths = [
        "olist_analytics.duckdb",
        "/content/olist_analytics.duckdb",
        os.path.join(os.path.dirname(__file__), "olist_analytics.duckdb"),
        os.path.abspath("olist_analytics.duckdb"),
    ]

    found_db_path = None
    for path in candidate_paths:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            found_db_path = path
            break

    if not found_db_path:
        return generate_mock_data(), "demo"

    try:
        con = duckdb.connect(database=found_db_path, read_only=True)
        tables = con.execute("SHOW TABLES;").df()["name"].tolist()

        if "fct_orders" not in tables:
            con.close()
            return generate_mock_data(), "demo"

        # Verificar se podemos enriquecer com customer_state via CSV bruto
        raw_cust_csv = "raw_data/olist_customers_dataset.csv"
        alt_raw_cust_csv = "/content/raw_data/olist_customers_dataset.csv"
        csv_to_use = None
        if os.path.exists(raw_cust_csv):
            csv_to_use = raw_cust_csv.replace("\\", "/")
        elif os.path.exists(alt_raw_cust_csv):
            csv_to_use = alt_raw_cust_csv

        if csv_to_use:
            query = f"""
            SELECT 
                f.*,
                c.customer_state
            FROM fct_orders f
            LEFT JOIN read_csv_auto('{csv_to_use}') c
              ON f.customer_id = c.customer_id
            """
        else:
            query = "SELECT * FROM fct_orders"

        df = con.execute(query).df()
        con.close()

        # Garantir conversão de timestamps
        time_cols = [
            "order_purchase_at",
            "order_approved_at",
            "order_delivered_carrier_at",
            "order_delivered_customer_at",
            "order_estimated_delivery_at",
        ]
        for col in time_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        if "customer_state" not in df.columns:
            df["customer_state"] = "N/A"

        return df, "duckdb"

    except Exception:
        # Fallback seguro para o modo demonstração
        return generate_mock_data(), "demo"


# ==============================================================================
# 5. Interface - Barra Lateral e Filtros
# ==============================================================================
with st.sidebar:
    st.image(
        "https://cdn-icons-png.flaticon.com/512/3081/3081559.png",
        width=60,
    )
    st.title("Filtros do Painel")

    # Controle da fonte de dados
    force_demo_toggle = st.toggle("Modo Demonstração (Mock)", value=False)
    
    # Carregamento
    df_raw, data_source = load_data(force_demo=force_demo_toggle)

    if data_source == "duckdb":
        st.success("🟢 Conectado ao DuckDB (`fct_orders`)")
    else:
        st.warning("🟡 Dados de Demonstração (Mock)")

    st.markdown("---")

    # 1. Filtro de Período (Datas)
    min_date = df_raw["order_purchase_at"].dropna().min().date()
    max_date = df_raw["order_purchase_at"].dropna().max().date()

    date_range = st.date_input(
        "Período de Compra",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    # 2. Filtro de Status
    all_statuses = sorted(df_raw["order_status"].dropna().unique().tolist())
    default_statuses = [s for s in ["delivered", "shipped"] if s in all_statuses] or all_statuses
    selected_statuses = st.multiselect(
        "Status do Pedido",
        options=all_statuses,
        default=default_statuses,
        help="Filtre os pedidos pelo ciclo de vida no marketplace.",
    )

    # 3. Filtro de Estados (UF)
    all_states = sorted([s for s in df_raw["customer_state"].dropna().unique() if s != "N/A"])
    selected_states = st.multiselect(
        "Estados (UF)",
        options=all_states,
        default=[],
        help="Deixe vazio para considerar todos os estados.",
    )

    st.markdown("---")
    if st.button("🔄 Recarregar Dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption("Stack: **dbt Core** + **DuckDB** + **Streamlit**")

# ==============================================================================
# 6. Aplicação dos Filtros
# ==============================================================================
df_filtered = df_raw.copy()

# Filtro de data
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_dt, end_dt = date_range
    df_filtered = df_filtered[
        (df_filtered["order_purchase_at"].dt.date >= start_dt)
        & (df_filtered["order_purchase_at"].dt.date <= end_dt)
    ]

# Filtro de status
if selected_statuses:
    df_filtered = df_filtered[df_filtered["order_status"].isin(selected_statuses)]

# Filtro de estado
if selected_states:
    df_filtered = df_filtered[df_filtered["customer_state"].isin(selected_states)]

# ==============================================================================
# 7. Cabeçalho Principal
# ==============================================================================
st.markdown('<div class="main-header">📦 Olist Executive & Logistics Dashboard</div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="sub-header">
        <span class="badge-tech">DuckDB</span>
        <span class="badge-tech">dbt Core</span>
        <span class="badge-tech">Modern Data Stack</span>
        Visão estratégica de vendas, lead time e conformidade operacional de entrega.
    </div>
    """,
    unsafe_allow_html=True,
)

if data_source == "demo":
    st.info(
        "💡 **Ambiente de Demonstração Ativo:** O arquivo analítico `olist_analytics.duckdb` "
        "não foi detectado ou ainda não foi construído via dbt. "
        "O painel está operando com dados simulados realistas. "
        "Para gerar a base real, execute o pipeline no notebook `dbt_duckdb_ecommerce_olist.ipynb`."
    )

# ==============================================================================
# 8. Top KPIs Executivos (5 Colunas)
# ==============================================================================
total_orders = len(df_filtered)
total_revenue = df_filtered["total_order_amount"].sum()
avg_ticket = (total_revenue / total_orders) if total_orders > 0 else 0.0

delivered_orders = df_filtered[df_filtered["order_status"] == "delivered"]
avg_delivery_time = (
    delivered_orders["delivery_time_days"].mean() if not delivered_orders.empty else 0.0
)

# Taxa de atraso: pedidos entregues onde delivery_margin_days < 0
if not delivered_orders.empty:
    delayed_orders_count = (delivered_orders["delivery_margin_days"] < 0).sum()
    delay_rate = (delayed_orders_count / len(delivered_orders)) * 100.0
else:
    delay_rate = 0.0

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        label="Faturamento Total",
        value=format_currency_br(total_revenue),
        help="Soma acumulada do valor dos itens + frete dos pedidos filtrados.",
    )

with col2:
    st.metric(
        label="Total de Pedidos",
        value=format_number_br(total_orders),
        help="Volume total de pedidos no período selecionado.",
    )

with col3:
    st.metric(
        label="Ticket Médio",
        value=format_currency_br(avg_ticket),
        help="Valor médio gasto por pedido (GMV / Pedidos).",
    )

with col4:
    st.metric(
        label="Lead Time Médio",
        value=f"{avg_delivery_time:.1f} dias",
        help="Tempo médio decorrido entre a compra e a entrega ao cliente.",
    )

with col5:
    st.metric(
        label="Taxa de Atraso",
        value=f"{delay_rate:.1f}%",
        delta=f"{(100 - delay_rate):.1f}% no prazo",
        delta_color="inverse" if delay_rate > 10 else "normal",
        help="Percentual de pedidos entregues após a estimativa oficial informada.",
    )

st.markdown("<br>", unsafe_allow_html=True)

# ==============================================================================
# 9. Abas Analíticas
# ==============================================================================
tab_comercial, tab_logistica = st.tabs([
    "📊 Desempenho Comercial & Vendas",
    "🚚 Eficiência Logística & SLA",
])

# ------------------------------------------------------------------------------
# Aba 1: Comercial
# ------------------------------------------------------------------------------
with tab_comercial:
    if df_filtered.empty:
        st.warning("Nenhum dado encontrado para os filtros selecionados.")
    else:
        col_chart1, col_chart2 = st.columns([7, 3])

        with col_chart1:
            # Série Temporal Mensal
            df_monthly = (
                df_filtered.set_index("order_purchase_at")
                .resample("M")
                .agg({"total_order_amount": "sum", "order_id": "count"})
                .reset_index()
            )
            df_monthly["mes_ano"] = df_monthly["order_purchase_at"].dt.strftime("%Y-%m")

            fig_timeline = px.area(
                df_monthly,
                x="mes_ano",
                y="total_order_amount",
                title="Evolução Mensal do Faturamento (R$)",
                labels={"mes_ano": "Mês/Ano", "total_order_amount": "Faturamento (R$)"},
                color_discrete_sequence=["#3B82F6"],
            )
            fig_timeline.update_layout(
                template="plotly_white",
                margin=dict(l=20, r=20, t=40, b=20),
                hovermode="x unified",
                yaxis_tickprefix="R$ ",
            )
            fig_timeline.update_traces(
                line=dict(width=2.5),
                hovertemplate="<b>Faturamento:</b> R$ %{y:,.2f}<extra></extra>",
            )
            st.plotly_chart(fig_timeline, use_container_width=True)

        with col_chart2:
            # Distribuição por Status
            df_status = (
                df_filtered["order_status"]
                .value_counts()
                .reset_index()
                .rename(columns={"index": "status", "order_status": "pedidos"})
            )
            fig_status = px.bar(
                df_status,
                x="pedidos",
                y="status",
                orientation="h",
                title="Volume por Status de Pedido",
                labels={"pedidos": "Qtd. Pedidos", "status": "Status"},
                color="status",
                color_discrete_sequence=px.colors.qualitative.Prism,
            )
            fig_status.update_layout(
                template="plotly_white",
                margin=dict(l=20, r=20, t=40, b=20),
                showlegend=False,
            )
            st.plotly_chart(fig_status, use_container_width=True)

        # Gráfico adicional: Ticket Médio por Faixa de Itens
        st.markdown("#### 🛒 Análise de Composição da Cesta")
        c1, c2 = st.columns([5, 5])

        with c1:
            df_items_group = (
                df_filtered.groupby("total_items")
                .agg(
                    qtd_pedidos=("order_id", "count"),
                    ticket_medio=("total_order_amount", "mean"),
                    frete_medio=("total_freight_amount", "mean"),
                )
                .reset_index()
                .head(6)
            )
            df_items_group["total_items_label"] = df_items_group["total_items"].apply(
                lambda x: f"{x} item" if x == 1 else f"{x} itens"
            )

            fig_basket = px.bar(
                df_items_group,
                x="total_items_label",
                y="ticket_medio",
                title="Ticket Médio por Quantidade de Itens",
                labels={"total_items_label": "Itens no Pedido", "ticket_medio": "Ticket Médio (R$)"},
                color_discrete_sequence=["#10B981"],
                text_auto=".2f",
            )
            fig_basket.update_layout(template="plotly_white", yaxis_tickprefix="R$ ")
            st.plotly_chart(fig_basket, use_container_width=True)

        with c2:
            fig_scatter = px.scatter(
                df_filtered.head(400),
                x="total_items_amount",
                y="total_freight_amount",
                size="total_items",
                color="order_status",
                title="Relação: Valor dos Itens vs Valor do Frete",
                labels={"total_items_amount": "Valor dos Itens (R$)", "total_freight_amount": "Frete (R$)"},
                template="plotly_white",
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

# ------------------------------------------------------------------------------
# Aba 2: Logística
# ------------------------------------------------------------------------------
with tab_logistica:
    if delivered_orders.empty:
        st.warning("Não há pedidos com status 'delivered' no filtro atual para calcular métricas de entrega.")
    else:
        col_sla1, col_sla2 = st.columns([4, 6])

        with col_sla1:
            # Gráfico de Rosca - Pontualidade
            df_log_status = delivered_orders.copy()
            df_log_status["sla_status"] = df_log_status["delivery_margin_days"].apply(
                lambda x: "No Prazo" if x >= 0 else "Em Atraso"
            )
            df_pie = df_log_status["sla_status"].value_counts().reset_index()
            df_pie.columns = ["status_sla", "quantidade"]

            fig_donut = px.pie(
                df_pie,
                names="status_sla",
                values="quantidade",
                hole=0.55,
                title="Cumprimento de SLA de Entrega",
                color="status_sla",
                color_discrete_map={"No Prazo": "#10B981", "Em Atraso": "#EF4444"},
            )
            fig_donut.update_traces(
                textinfo="percent+label",
                hovertemplate="<b>%{label}:</b> %{value} pedidos (%{percent})<extra></extra>",
            )
            fig_donut.update_layout(
                template="plotly_white",
                margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
            )
            st.plotly_chart(fig_donut, use_container_width=True)

        with col_sla2:
            # Lead Time Médio por Estado
            if "customer_state" in delivered_orders.columns and delivered_orders["customer_state"].nunique() > 1:
                df_uf_lead = (
                    delivered_orders[delivered_orders["customer_state"] != "N/A"]
                    .groupby("customer_state")["delivery_time_days"]
                    .mean()
                    .reset_index()
                    .sort_values(by="delivery_time_days", ascending=False)
                    .head(12)
                )

                fig_uf = px.bar(
                    df_uf_lead,
                    x="delivery_time_days",
                    y="customer_state",
                    orientation="h",
                    title="Lead Time Médio por UF - Top 12 (Dias)",
                    labels={"delivery_time_days": "Dias de Entrega", "customer_state": "Estado (UF)"},
                    color="delivery_time_days",
                    color_continuous_scale="Reds",
                    text_auto=".1f",
                )
                fig_uf.update_layout(
                    template="plotly_white",
                    margin=dict(l=20, r=20, t=40, b=20),
                    yaxis={"categoryorder": "total ascending"},
                )
                st.plotly_chart(fig_uf, use_container_width=True)
            else:
                # Distribuição por faixas de prazo
                bins = [0, 5, 10, 15, 20, 100]
                labels = ["1 a 5 dias", "6 a 10 dias", "11 a 15 dias", "16 a 20 dias", "+20 dias"]
                delivered_orders["faixa_dias"] = pd.cut(
                    delivered_orders["delivery_time_days"], bins=bins, labels=labels
                )
                df_faixas = delivered_orders["faixa_dias"].value_counts().sort_index().reset_index()
                df_faixas.columns = ["faixa_dias", "total_pedidos"]

                fig_faixas = px.bar(
                    df_faixas,
                    x="faixa_dias",
                    y="total_pedidos",
                    title="Distribuição dos Pedidos por Faixa de Lead Time",
                    labels={"faixa_dias": "Faixa de Dias", "total_pedidos": "Total de Pedidos"},
                    color_discrete_sequence=["#6366F1"],
                )
                fig_faixas.update_layout(template="plotly_white")
                st.plotly_chart(fig_faixas, use_container_width=True)

        # Histograma de Margem de Entrega (Folga x Atraso)
        st.markdown("#### ⏱️ Margem de Segurança da Entrega")
        fig_margin = px.histogram(
            delivered_orders,
            x="delivery_margin_days",
            nbins=40,
            title="Distribuição da Margem de Entrega em Dias (Positivo = Antes do Prazo | Negativo = Atraso)",
            labels={"delivery_margin_days": "Margem de Cumprimento (Dias)"},
            color_discrete_sequence=["#8B5CF6"],
        )
        fig_margin.add_vline(x=0, line_width=2, line_dash="dash", line_color="#EF4444")
        fig_margin.update_layout(template="plotly_white")
        st.plotly_chart(fig_margin, use_container_width=True)

# ==============================================================================
# 10. Expander: Visualizar e Exportar Dados Detalhados
# ==============================================================================
st.markdown("<br>", unsafe_allow_html=True)
with st.expander("🔍 Visualizar e Exportar Dados Detalhados (Amostra Filtrada)"):
    st.write(f"Exibindo **{min(len(df_filtered), 100)}** de **{len(df_filtered)}** registros filtrados:")
    
    cols_display = [
        "order_id",
        "order_status",
        "customer_state",
        "order_purchase_at",
        "total_items",
        "total_items_amount",
        "total_freight_amount",
        "total_order_amount",
        "delivery_time_days",
        "delivery_margin_days",
    ]
    cols_present = [c for c in cols_display if c in df_filtered.columns]

    st.dataframe(
        df_filtered[cols_present].head(100),
        use_container_width=True,
        height=320,
    )

    csv_data = df_filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Baixar Base Filtrada Completa (.CSV)",
        data=csv_data,
        file_name="olist_analytics_filtered.csv",
        mime="text/csv",
        use_container_width=False,
    )

# ==============================================================================
# 11. Rodapé
# ==============================================================================
st.markdown("---")
st.caption(
    "Desenvolvido com **Streamlit**, **DuckDB** e **dbt Core** • "
    "Dataset: Olist Brazilian E-Commerce • "
    "Arquitetura de Dados Serverless & In-Process"
)
