"""
Painel de vendas Olist.

Layout de página única no estilo de relatório de BI: cabeçalho com filtros e
indicadores, seguido de uma grade de visuais. Lê a tabela fct_orders gerada
pelo dbt no DuckDB; se o banco não existir, usa dados simulados.
"""

import datetime
import os

import duckdb
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Vendas Olist",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ------------------------------------------------------------------------------
# Paleta
# ------------------------------------------------------------------------------
BG = "#0B0B0B"
CARD = "#161616"
BORDER = "#262626"
TEXT = "#E8E8E8"
MUTED = "#8C8C8C"
GRID = "#242424"
YELLOW = "#FFC107"
YELLOW_LIGHT = "#FFE082"
YELLOW_DARK = "#B38600"
YELLOW_DEEP = "#5C4A12"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]
MESES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun",
               "jul", "ago", "set", "out", "nov", "dez"]

ESTADOS = {
    "AC": ("Acre", -9.0, -70.5), "AL": ("Alagoas", -9.6, -36.6),
    "AP": ("Amapá", 1.4, -51.8), "AM": ("Amazonas", -4.2, -64.6),
    "BA": ("Bahia", -12.5, -41.7), "CE": ("Ceará", -5.2, -39.5),
    "DF": ("Distrito Federal", -15.8, -47.9), "ES": ("Espírito Santo", -19.6, -40.6),
    "GO": ("Goiás", -15.9, -49.8), "MA": ("Maranhão", -5.4, -45.4),
    "MT": ("Mato Grosso", -12.6, -55.9), "MS": ("Mato Grosso do Sul", -20.5, -54.6),
    "MG": ("Minas Gerais", -18.5, -44.6), "PA": ("Pará", -3.8, -52.5),
    "PB": ("Paraíba", -7.1, -36.8), "PR": ("Paraná", -24.6, -51.6),
    "PE": ("Pernambuco", -8.4, -37.9), "PI": ("Piauí", -7.7, -42.7),
    "RJ": ("Rio de Janeiro", -22.3, -42.7), "RN": ("Rio Grande do Norte", -5.8, -36.6),
    "RS": ("Rio Grande do Sul", -29.8, -53.2), "RO": ("Rondônia", -10.9, -62.8),
    "RR": ("Roraima", 2.0, -61.4), "SC": ("Santa Catarina", -27.3, -50.4),
    "SP": ("São Paulo", -22.2, -48.7), "SE": ("Sergipe", -10.6, -37.4),
    "TO": ("Tocantins", -10.2, -48.3),
}

CATEGORIAS = {
    "cama_mesa_banho": "Cama e Banho",
    "beleza_saude": "Beleza",
    "esporte_lazer": "Esporte",
    "moveis_decoracao": "Decoração",
    "informatica_acessorios": "Informática",
    "utilidades_domesticas": "Casa",
    "relogios_presentes": "Relógios",
    "telefonia": "Telefonia",
    "automotivo": "Automotivo",
    "brinquedos": "Brinquedos",
    "cool_stuff": "Cool Stuff",
    "ferramentas_jardim": "Jardim",
    "perfumaria": "Perfumaria",
    "bebes": "Bebês",
    "eletronicos": "Eletrônicos",
    "papelaria": "Papelaria",
    "fashion_bolsas_e_acessorios": "Moda",
    "pet_shop": "Pet Shop",
}

PAGAMENTOS = {
    "credit_card": "Cartão de crédito",
    "boleto": "Boleto",
    "voucher": "Voucher",
    "debit_card": "Cartão de débito",
}

STATUS_EXCLUIDOS = {"canceled", "unavailable"}

# ------------------------------------------------------------------------------
# Estilo
# ------------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,500,1,0');

    html, body, [class*="css"], .stApp {{
        font-family: 'Inter', sans-serif;
    }}
    .stApp {{ background: {BG}; }}
    header[data-testid="stHeader"], footer, #MainMenu,
    [data-testid="stSidebarCollapsedControl"], [data-testid="stToolbar"] {{
        display: none !important;
    }}
    .block-container {{
        padding: 1.2rem 1.6rem 1rem 1.6rem;
        max-width: 100%;
    }}

    /* Cartões */
    [class*="st-key-card"] {{
        background: {CARD};
        border: 1px solid {BORDER};
        border-radius: 12px;
        padding: 14px 16px 6px 16px;
    }}
    .card-title {{
        color: {TEXT};
        font-weight: 700;
        font-size: 0.98rem;
        line-height: 1.2;
    }}
    .card-sub {{
        color: {MUTED};
        font-size: 0.76rem;
        margin-bottom: 4px;
    }}

    /* Título */
    .dash-title {{
        font-family: 'Bebas Neue', sans-serif;
        font-size: 3.6rem;
        line-height: 0.9;
        letter-spacing: 1px;
        color: {YELLOW};
        margin: 0;
    }}
    .dash-tag {{
        color: {MUTED};
        font-size: 0.78rem;
        margin-top: 4px;
    }}
    .dash-tag b {{ color: {YELLOW}; font-weight: 600; }}

    /* Cartão de indicadores */
    .kpi-card {{
        background: linear-gradient(100deg, #1A1A1A 0%, #3A2E05 30%, {YELLOW_DARK} 65%, {YELLOW} 100%);
        border-radius: 12px;
        padding: 16px 22px;
        display: flex;
        justify-content: space-between;
        gap: 18px;
        min-height: 92px;
        align-items: center;
    }}
    .kpi {{ display: flex; align-items: center; gap: 12px; }}
    .kpi-icon {{
        font-family: 'Material Symbols Rounded';
        font-size: 26px;
        width: 46px; height: 46px;
        border-radius: 50%;
        background: {BG};
        color: {YELLOW};
        display: flex; align-items: center; justify-content: center;
        border: 1px solid rgba(255,193,7,0.35);
    }}
    .kpi-label {{
        color: #F4F4F4;
        font-size: 0.82rem;
        font-weight: 600;
    }}
    .kpi-value {{
        color: #FFFFFF;
        font-size: 1.55rem;
        font-weight: 700;
        line-height: 1.1;
        text-shadow: 0 1px 2px rgba(0,0,0,0.35);
    }}

    /* Widgets */
    [data-testid="stWidgetLabel"] p {{
        color: {TEXT};
        font-size: 0.8rem;
        font-weight: 600;
    }}
    [data-baseweb="select"] > div {{
        background: {BG};
        border-color: #333;
    }}
    .src-note {{
        color: {MUTED};
        font-size: 0.72rem;
        text-align: right;
        margin-top: 6px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------------------
# Formatação
# ------------------------------------------------------------------------------
def fmt_compacto(valor: float, prefixo: str = "R$ ") -> str:
    """Formata números grandes no padrão brasileiro (R$ 1,2 Mi, R$ 850 mil)."""
    if valor is None or pd.isna(valor):
        return f"{prefixo}0"
    v = float(valor)
    if abs(v) >= 1e9:
        txt = f"{v / 1e9:.1f} Bi"
    elif abs(v) >= 1e6:
        txt = f"{v / 1e6:.1f} Mi"
    elif abs(v) >= 1e3:
        txt = f"{v / 1e3:.1f} mil"
    else:
        txt = f"{v:.0f}"
    return prefixo + txt.replace(".", ",")


def fmt_inteiro(valor: float) -> str:
    return f"{int(valor):,}".replace(",", ".")


def fmt_moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def nome_categoria(slug) -> str:
    if slug is None or pd.isna(slug) or slug == "":
        return "Outros"
    return CATEGORIAS.get(slug, str(slug).replace("_", " ").title())


# ------------------------------------------------------------------------------
# Dados
# ------------------------------------------------------------------------------
def gerar_dados_demo(n: int = 30000) -> pd.DataFrame:
    """Gera pedidos simulados com distribuição próxima à base real da Olist."""
    rng = np.random.default_rng(42)

    dias = pd.date_range("2017-01-01", "2018-08-31", freq="D")
    t = np.arange(len(dias)) / len(dias)
    peso = (1 + 1.3 * t) * (1 + 0.18 * np.sin(2 * np.pi * (dias.dayofyear / 365.25 - 0.15)))
    black_friday = (dias.month == 11) & (dias.day >= 20) & (dias.day <= 27)
    peso = np.where(black_friday, peso * 2.6, peso)
    peso = peso / peso.sum()

    idx = rng.choice(len(dias), size=n, p=peso)
    compra = dias[idx] + pd.to_timedelta(rng.integers(0, 86400, n), unit="s")

    ufs = list(ESTADOS.keys())
    peso_uf = np.array([
        0.1, 0.4, 0.1, 0.15, 3.4, 1.3, 2.1, 2.0, 2.0, 0.75, 0.9, 0.7,
        11.7, 1.0, 0.5, 5.1, 1.7, 0.5, 12.9, 0.5, 5.5, 0.25, 0.05, 3.7,
        42.0, 0.35, 0.3,
    ])
    uf = rng.choice(ufs, size=n, p=peso_uf / peso_uf.sum())

    cats = list(CATEGORIAS.keys())
    peso_cat = np.array([11, 9.5, 8.5, 7.5, 7, 6.5, 6, 4.5, 4, 4, 3.5, 3.8, 3.2, 3, 2.5, 2.3, 1.9, 1.7])
    categoria = rng.choice(cats, size=n, p=peso_cat / peso_cat.sum())

    pagamento = rng.choice(list(PAGAMENTOS.keys()), size=n, p=[0.74, 0.195, 0.05, 0.015])
    status = rng.choice(
        ["delivered", "shipped", "canceled", "invoiced", "processing", "unavailable"],
        size=n, p=[0.97, 0.011, 0.006, 0.004, 0.004, 0.005],
    )

    itens = rng.choice([1, 2, 3, 4], size=n, p=[0.85, 0.1, 0.035, 0.015])
    valor_itens = np.round(rng.lognormal(4.45, 0.8, n) * itens, 2)
    frete = np.round(12 + itens * rng.uniform(3, 12, n), 2)

    prazo = rng.integers(12, 35, n)
    atrasado = rng.random(n) < 0.08
    dias_reais = np.where(
        atrasado,
        prazo + rng.uniform(1, 15, n),
        np.maximum(2, prazo - rng.uniform(3, 14, n)),
    )
    entregue = status == "delivered"

    df = pd.DataFrame({
        "order_id": [f"demo_{i:06d}" for i in range(n)],
        "order_status": status,
        "order_purchase_at": compra,
        "customer_state": uf,
        "category": categoria,
        "payment_type": pagamento,
        "total_items": itens,
        "total_items_amount": valor_itens,
        "total_freight_amount": frete,
        "total_order_amount": valor_itens + frete,
        "delivery_time_days": np.where(entregue, np.round(dias_reais, 2), np.nan),
        "delivery_margin_days": np.where(entregue, np.round(prazo - dias_reais, 2), np.nan),
    })
    return df


def _localizar_banco():
    candidatos = [
        os.path.join(BASE_DIR, "olist_analytics.duckdb"),
        os.path.abspath("olist_analytics.duckdb"),
        "/content/olist_analytics.duckdb",
    ]
    for caminho in candidatos:
        if os.path.exists(caminho) and os.path.getsize(caminho) > 0:
            return caminho
    return None


def _localizar_csvs():
    necessarios = [
        "olist_customers_dataset.csv",
        "olist_order_items_dataset.csv",
        "olist_products_dataset.csv",
        "olist_order_payments_dataset.csv",
    ]
    for pasta in (os.path.join(BASE_DIR, "raw_data"), "/content/raw_data"):
        if all(os.path.exists(os.path.join(pasta, f)) for f in necessarios):
            return pasta.replace("\\", "/")
    return None


@st.cache_data(show_spinner=False)
def carregar_dados():
    """Retorna (dataframe, origem). Origem: 'duckdb' ou 'demo'."""
    banco = _localizar_banco()
    if not banco:
        return gerar_dados_demo(), "demo"

    try:
        con = duckdb.connect(database=banco, read_only=True)
        tabelas = con.execute("SHOW TABLES").df()["name"].tolist()
        if "fct_orders" not in tabelas:
            con.close()
            return gerar_dados_demo(), "demo"

        raw = _localizar_csvs()
        if raw:
            consulta = f"""
            with cliente as (
                select customer_id, customer_state
                from read_csv_auto('{raw}/olist_customers_dataset.csv')
            ),
            categoria as (
                select order_id, product_category_name as category
                from (
                    select i.order_id, p.product_category_name,
                           row_number() over (partition by i.order_id order by i.price desc) as rn
                    from read_csv_auto('{raw}/olist_order_items_dataset.csv') i
                    left join read_csv_auto('{raw}/olist_products_dataset.csv') p
                      on i.product_id = p.product_id
                ) where rn = 1
            ),
            pagamento as (
                select order_id, payment_type
                from (
                    select order_id, payment_type,
                           row_number() over (partition by order_id order by payment_value desc) as rn
                    from read_csv_auto('{raw}/olist_order_payments_dataset.csv')
                ) where rn = 1
            )
            select f.*, c.customer_state, cat.category, pg.payment_type
            from fct_orders f
            left join cliente c on f.customer_id = c.customer_id
            left join categoria cat on f.order_id = cat.order_id
            left join pagamento pg on f.order_id = pg.order_id
            """
        else:
            consulta = """
            select *, null as customer_state, null as category, null as payment_type
            from fct_orders
            """

        df = con.execute(consulta).df()
        con.close()
        df["order_purchase_at"] = pd.to_datetime(df["order_purchase_at"], errors="coerce")
        return df, "duckdb"
    except Exception:
        return gerar_dados_demo(), "demo"


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[~df["order_status"].isin(STATUS_EXCLUIDOS)]
    df = df.dropna(subset=["order_purchase_at"])
    df["customer_state"] = df["customer_state"].fillna("N/I")
    df["categoria"] = df["category"].map(nome_categoria)
    df["pagamento"] = df["payment_type"].map(PAGAMENTOS).fillna("Outros")
    df["mes_ref"] = df["order_purchase_at"].dt.to_period("M").dt.to_timestamp()
    df["mes_num"] = df["order_purchase_at"].dt.month
    return df


df_raw, origem = carregar_dados()
df_all = preparar(df_raw)


# ------------------------------------------------------------------------------
# Visuais
# ------------------------------------------------------------------------------
def layout_base(fig: go.Figure, altura: int) -> go.Figure:
    fig.update_layout(
        height=altura,
        margin=dict(l=8, r=8, t=10, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=TEXT, size=12),
        hoverlabel=dict(bgcolor="#202020", bordercolor=YELLOW, font=dict(color=TEXT)),
    )
    return fig


def grafico_sazonalidade(df: pd.DataFrame) -> go.Figure:
    mensal = (
        df.groupby("mes_ref")
        .agg(receita=("total_order_amount", "sum"), pedidos=("order_id", "nunique"))
        .reset_index()
    )
    rotulos = [f"{MESES_ABREV[d.month - 1]} {d.year}" for d in mensal["mes_ref"]]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=mensal["mes_ref"], y=mensal["receita"], name="Receita",
        mode="lines", line=dict(color=YELLOW, width=3, shape="spline"),
        fill="tozeroy", fillcolor="rgba(255,193,7,0.14)",
        customdata=[[r, fmt_compacto(v)] for r, v in zip(rotulos, mensal["receita"])],
        hovertemplate="%{customdata[0]}<br>Receita: %{customdata[1]}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=mensal["mes_ref"], y=mensal["pedidos"], name="Pedidos", yaxis="y2",
        mode="lines", line=dict(color="#F5F5F5", width=2, shape="spline", dash="dot"),
        customdata=rotulos,
        hovertemplate="%{customdata}<br>Pedidos: %{y:,.0f}<extra></extra>",
    ))

    vmax = mensal["receita"].max() if len(mensal) else 1
    ticks = np.linspace(0, vmax, 4)
    layout_base(fig, 300)
    fig.update_layout(
        legend=dict(orientation="h", x=0, y=1.12, font=dict(size=11)),
        xaxis=dict(showgrid=False, tickformat="%b %Y", color=MUTED),
        yaxis=dict(
            gridcolor=GRID, zeroline=False, color=YELLOW,
            tickvals=ticks, ticktext=[fmt_compacto(v) for v in ticks],
        ),
        yaxis2=dict(overlaying="y", side="right", showgrid=False, color="#BDBDBD",
                    tickformat=",.0f", rangemode="tozero"),
        hovermode="x unified",
        separators=",.",
    )
    return fig


def grafico_matriz(df: pd.DataFrame) -> go.Figure:
    top = df["categoria"].value_counts().head(7).index.tolist()
    base = df[df["categoria"].isin(top)]
    matriz = (
        base.pivot_table(index="mes_num", columns="categoria", values="order_id",
                         aggfunc="count", fill_value=0)
        .reindex(index=range(1, 13), fill_value=0)
        .reindex(columns=top, fill_value=0)
    )
    texto = [[fmt_inteiro(v) for v in linha] for linha in matriz.values]

    fig = go.Figure(go.Heatmap(
        z=matriz.values, x=top, y=MESES,
        text=texto, texttemplate="%{text}", textfont=dict(color="#111111", size=11),
        colorscale=[[0, "#FFF8E1"], [0.5, "#FFD54F"], [1, "#FF9F00"]],
        showscale=False, xgap=2, ygap=2,
        hovertemplate="%{y} · %{x}<br>Pedidos: %{text}<extra></extra>",
    ))
    layout_base(fig, 300)
    fig.update_layout(
        xaxis=dict(side="top", showgrid=False, tickfont=dict(size=11, color=TEXT)),
        yaxis=dict(autorange="reversed", showgrid=False, tickfont=dict(size=11, color=TEXT)),
    )
    return fig


def grafico_estados(df: pd.DataFrame) -> go.Figure:
    por_uf = (
        df.groupby("customer_state")["total_order_amount"].sum()
        .sort_values(ascending=False).head(10).sort_values()
    )
    nomes = [ESTADOS.get(uf, (uf,))[0] for uf in por_uf.index]

    fig = go.Figure(go.Bar(
        x=por_uf.values, y=nomes, orientation="h",
        marker=dict(color=YELLOW, line=dict(width=0)),
        text=[fmt_compacto(v) for v in por_uf.values], textposition="outside",
        textfont=dict(color=TEXT, size=11), cliponaxis=False,
        hovertemplate="%{y}<br>Receita: %{text}<extra></extra>",
    ))
    layout_base(fig, 290)
    fig.update_layout(
        xaxis=dict(visible=False, range=[0, por_uf.max() * 1.28 if len(por_uf) else 1]),
        yaxis=dict(showgrid=False, tickfont=dict(size=11, color=TEXT)),
        bargap=0.35,
    )
    return fig


def grafico_mapa(df: pd.DataFrame) -> go.Figure:
    por_uf = df.groupby("customer_state")["total_order_amount"].sum().reset_index()
    por_uf = por_uf[por_uf["customer_state"].isin(ESTADOS.keys())]
    por_uf["nome"] = por_uf["customer_state"].map(lambda u: ESTADOS[u][0])
    por_uf["lat"] = por_uf["customer_state"].map(lambda u: ESTADOS[u][1])
    por_uf["lon"] = por_uf["customer_state"].map(lambda u: ESTADOS[u][2])
    vmax = por_uf["total_order_amount"].max() if len(por_uf) else 1
    tamanhos = 7 + 38 * np.sqrt(por_uf["total_order_amount"] / vmax)

    fig = go.Figure(go.Scattergeo(
        lat=por_uf["lat"], lon=por_uf["lon"], text=por_uf["customer_state"],
        mode="markers+text", textposition="top center",
        textfont=dict(color="#CFCFCF", size=9),
        marker=dict(size=tamanhos, color=YELLOW, opacity=0.8,
                    line=dict(color=BG, width=1)),
        customdata=np.stack([por_uf["nome"], por_uf["total_order_amount"].map(fmt_compacto)], axis=-1)
        if len(por_uf) else None,
        hovertemplate="%{customdata[0]}<br>Receita: %{customdata[1]}<extra></extra>",
    ))
    layout_base(fig, 290)
    fig.update_geos(
        scope="south america",
        projection_type="mercator",
        lataxis_range=[-34.5, 6], lonaxis_range=[-75, -33],
        showland=True, landcolor="#1F1F1F",
        showocean=True, oceancolor=BG,
        showcountries=True, countrycolor="#3A3A3A",
        showcoastlines=True, coastlinecolor="#3A3A3A",
        showlakes=False, showframe=False, bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    return fig


def grafico_pagamento(df: pd.DataFrame) -> go.Figure:
    pag = df.groupby("pagamento")["total_order_amount"].sum().sort_values(ascending=False)
    cores = [YELLOW, YELLOW_LIGHT, YELLOW_DARK, YELLOW_DEEP, "#3A3A3A"]

    fig = go.Figure(go.Pie(
        labels=pag.index, values=pag.values, hole=0.62, sort=False,
        marker=dict(colors=cores[: len(pag)], line=dict(color=CARD, width=2)),
        customdata=[fmt_compacto(v) for v in pag.values],
        texttemplate="%{label}<br>%{customdata} (%{percent})",
        textposition="outside", textfont=dict(color=TEXT, size=11),
        hovertemplate="%{label}<br>Receita: %{customdata}<br>%{percent}<extra></extra>",
    ))
    layout_base(fig, 290)
    fig.update_layout(showlegend=False, margin=dict(l=30, r=30, t=30, b=20), separators=",.")
    return fig


def cabecalho_cartao(titulo: str, subtitulo: str):
    st.markdown(
        f"<div class='card-title'>{titulo}</div><div class='card-sub'>{subtitulo}</div>",
        unsafe_allow_html=True,
    )


PLOT_CFG = {"displayModeBar": False}

# ------------------------------------------------------------------------------
# Cabeçalho: título, filtros e indicadores
# ------------------------------------------------------------------------------
col_titulo, col_filtros, col_kpi = st.columns([1.05, 1.75, 2.2], gap="medium", vertical_alignment="center")

with col_titulo:
    tag = "Fonte: <b>DuckDB · fct_orders</b>" if origem == "duckdb" else "Fonte: <b>dados de demonstração</b>"
    st.markdown(
        f"<p class='dash-title'>VENDAS OLIST</p><div class='dash-tag'>{tag}</div>",
        unsafe_allow_html=True,
    )

data_min = df_all["order_purchase_at"].min().date()
data_max = df_all["order_purchase_at"].max().date()
padrao_ini = max(data_min, datetime.date(2017, 1, 1))
padrao_fim = min(data_max, datetime.date(2018, 8, 31))
if padrao_ini >= padrao_fim:
    padrao_ini, padrao_fim = data_min, data_max

with col_filtros:
    with st.container(key="card_filtros"):
        f1, f2, f3 = st.columns([1.5, 1, 1])
        with f1:
            periodo = st.slider(
                "Período",
                min_value=data_min, max_value=data_max,
                value=(padrao_ini, padrao_fim),
                format="DD/MM/YYYY",
            )
        with f2:
            ufs_disp = sorted(u for u in df_all["customer_state"].unique() if u in ESTADOS)
            uf_sel = st.selectbox(
                "Estado", ["Todos"] + ufs_disp,
                format_func=lambda u: u if u == "Todos" else f"{u} · {ESTADOS[u][0]}",
            )
        with f3:
            cats_disp = df_all["categoria"].value_counts().index.tolist()
            cat_sel = st.selectbox("Categoria", ["Todas"] + cats_disp)

df = df_all[
    (df_all["order_purchase_at"].dt.date >= periodo[0])
    & (df_all["order_purchase_at"].dt.date <= periodo[1])
]
if uf_sel != "Todos":
    df = df[df["customer_state"] == uf_sel]
if cat_sel != "Todas":
    df = df[df["categoria"] == cat_sel]

receita = df["total_order_amount"].sum()
pedidos = df["order_id"].nunique()
ticket = receita / pedidos if pedidos else 0
entregues = df["delivery_margin_days"].dropna()
no_prazo = (entregues >= 0).mean() * 100 if len(entregues) else 0

def bloco_kpi(icone: str, rotulo: str, valor: str) -> str:
    return (
        f"<div class='kpi'><span class='kpi-icon'>{icone}</span>"
        f"<div><div class='kpi-label'>{rotulo}</div><div class='kpi-value'>{valor}</div></div></div>"
    )


with col_kpi:
    kpis = "".join([
        bloco_kpi("payments", "Receita", fmt_compacto(receita)),
        bloco_kpi("shopping_cart", "Pedidos", fmt_compacto(pedidos, "")),
        bloco_kpi("receipt_long", "Ticket médio", fmt_moeda(ticket)),
        bloco_kpi("local_shipping", "No prazo", f"{no_prazo:.1f}%".replace(".", ",")),
    ])
    st.markdown(f"<div class='kpi-card'>{kpis}</div>", unsafe_allow_html=True)

st.write("")

if df.empty:
    st.warning("Nenhum pedido encontrado para os filtros selecionados.")
    st.stop()

# ------------------------------------------------------------------------------
# Linha 2: sazonalidade e matriz
# ------------------------------------------------------------------------------
l2a, l2b = st.columns([1.9, 1.25], gap="medium")
with l2a:
    with st.container(key="card_sazonalidade"):
        cabecalho_cartao("Receita por Sazonalidade", "Receita total e quantidade de pedidos por mês")
        st.plotly_chart(grafico_sazonalidade(df), width="stretch", config=PLOT_CFG)
with l2b:
    with st.container(key="card_matriz"):
        cabecalho_cartao("Sazonalidade por Categoria", "Pedidos por mês nas 7 categorias de maior volume")
        st.plotly_chart(grafico_matriz(df), width="stretch", config=PLOT_CFG)

# ------------------------------------------------------------------------------
# Linha 3: estados, mapa e pagamento
# ------------------------------------------------------------------------------
l3a, l3b, l3c = st.columns([1.05, 1.05, 1.05], gap="medium")
with l3a:
    with st.container(key="card_estados"):
        cabecalho_cartao("Receita por Estado", "10 estados com maior receita")
        st.plotly_chart(grafico_estados(df), width="stretch", config=PLOT_CFG)
with l3b:
    with st.container(key="card_mapa"):
        cabecalho_cartao("Distribuição Geográfica", "Receita por estado do cliente")
        st.plotly_chart(grafico_mapa(df), width="stretch", config=PLOT_CFG)
with l3c:
    with st.container(key="card_pagamento"):
        cabecalho_cartao("Representatividade por Pagamento", "Participação na receita por forma de pagamento")
        st.plotly_chart(grafico_pagamento(df), width="stretch", config=PLOT_CFG)

st.markdown(
    "<div class='src-note'>Pedidos cancelados e indisponíveis não entram nos totais.</div>",
    unsafe_allow_html=True,
)
