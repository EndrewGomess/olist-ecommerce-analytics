# Olist E-Commerce Analytics (dbt Core + DuckDB + Streamlit)

Pipeline analítico de ponta a ponta construído sobre o dataset público da Olist (Brazilian E-Commerce). O projeto implementa engenharia de analytics moderna e *serverless*, combinando **dbt Core** para modelagem modular e qualidade de dados, **DuckDB** como motor colunar OLAP in-process, e uma interface gerencial interativa em **Streamlit**.

---

## 1. Visão Geral

O objetivo principal deste projeto é transformar dados brutos de mais de 100 mil pedidos reais de e-commerce brasileiro (2016 a 2018) em uma camada analítica consolidada e confiável, viabilizando:
- Análise de faturamento e composição de ticket médio por pedido.
- Monitoramento de SLA logístico, lead time de entrega e identificação de pedidos atrasados.
- Testes automatizados de qualidade de dados (unicidade, integridade de domínio e não-nulidade).
- Exploração interativa através de um dashboard gerencial em Streamlit com suporte a filtros dinâmicos e modo demonstração em memória.

---

## 2. Arquitetura de Dados

O pipeline adota o modelo em camadas estruturado do dbt:

```
[ Kaggle Dataset (Olist) ]
            │
            ▼ (kagglehub)
   [ raw_data/*.csv ]
            │
    ┌───────┴─────────────────────────────────────────┐
    │                dbt-duckdb                       │
    │                                                 │
    │  1. Camada Staging (stg_)                       │
    │     - Leitura das fontes raw                    │
    │     - Limpeza, tipagem (casting) e renomeação   │
    │                                                 │
    │  2. Camada Intermediate (int_)                  │
    │     - Agregação por pedido (itens, frete, etc.) │
    │                                                 │
    │  3. Camada Marts (fct_)                         │
    │     - Tabela Fato de Pedidos (fct_orders)       │
    │     - Lead time e margens de prazo              │
    │                                                 │
    │  4. Testes de Qualidade                         │
    │     - unique, not_null, accepted_values         │
    └───────────────────────┬─────────────────────────┘
                            │
                            ▼
           [ olist_analytics.duckdb (Arquivo OLAP) ]
                            │
                            ▼
                 [ Dashboard Streamlit ]
```

### Camadas de Modelagem
- **Staging (`models/staging`)**:
  - `stg_orders`: Padronização de datas, identificadores e status de ciclo de vida do pedido.
  - `stg_order_items`: Tipagem numérica estrita de valores de produtos e fretes.
- **Intermediate (`models/intermediate`)**:
  - `int_order_items_summary`: Agregação transacional ao nível de `order_id` (total de itens, produtos distintos, subtotal de itens e frete).
- **Marts (`models/marts`)**:
  - `fct_orders`: Consolidação dimensional e de métricas agregadas por pedido, calculando lead time de entrega (`delivery_time_days`) e margem de cumprimento do prazo estimado (`delivery_margin_days`).

---

## 3. Estrutura do Repositório

```
olist-ecommerce-analytics/
├── app.py                     # Aplicação Streamlit (Dashboard Executivo e Logístico)
├── requirements.txt           # Dependências do projeto Python
├── README.md                  # Documentação técnica do projeto
├── notebooks/
│   └── dbt_duckdb_ecommerce_olist.ipynb # Notebook executável ponta a ponta (Colab / Jupyter)
└── dbt_project/               # Projeto dbt Core integrado ao DuckDB
    ├── dbt_project.yml        # Configuração do projeto dbt
    ├── profiles.yml.example   # Modelo de conexão para o DuckDB
    └── models/
        ├── staging/           # Fontes brutas e modelos de staging
        │   ├── sources.yml
        │   ├── stg_orders.sql
        │   ├── stg_orders.yml
        │   └── stg_order_items.sql
        ├── intermediate/      # Agregações intermediárias
        │   └── int_order_items_summary.sql
        └── marts/             # Tabelas fato e testes de marts
            ├── fct_orders.sql
            └── marts.yml
```

---

## 4. Pré-requisitos

- Python 3.10 ou superior
- Pip e virtualenv

Instale as dependências executando:

```bash
pip install -r requirements.txt
```

---

## 5. Como Executar o Pipeline dbt

### 5.1. Download dos dados brutos
Para obter o conjunto de dados da Olist diretamente do Kaggle, você pode utilizar o script embutido no notebook ou executar via Python:

```python
import kagglehub
import shutil, os

path = kagglehub.dataset_download("olistbr/brazilian-ecommerce")
os.makedirs("raw_data", exist_ok=True)
for file in os.listdir(path):
    if file.endswith(".csv"):
        shutil.copy(os.path.join(path, file), os.path.join("raw_data", file))
```

### 5.2. Configurar o perfil do dbt
Crie o arquivo de perfil local ou configure em `~/.dbt/profiles.yml`:

```yaml
olist_dbt:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: "../olist_analytics.duckdb"
      threads: 4
```

### 5.3. Execução das transformações e validação de testes
Acesse a pasta do projeto dbt e execute:

```bash
cd dbt_project
dbt run --profiles-dir .
dbt test --profiles-dir .
```

---

## 6. Como Executar o Dashboard Streamlit

Com o ambiente virtual ativado e as dependências instaladas, execute:

```bash
streamlit run app.py
```

### Funcionalidades do Dashboard:
- **Resiliência a ausência de banco**: Caso o arquivo `olist_analytics.duckdb` ainda não tenha sido gerado, a aplicação ativa automaticamente um modo de demonstração com dados simulados em memória, garantindo navegação completa e imediata.
- **Top KPIs**: Faturamento total (R$), total de pedidos, ticket médio, lead time médio em dias e taxa de atraso no cumprimento do SLA.
- **Aba Comercial**: Gráfico temporal de faturamento mensal e distribuição de pedidos por status.
- **Aba Logística**: Gráfico donut de pontualidade de entrega (no prazo vs em atraso), lead time médio por estado e histograma de margem de entrega.
- **Exportação de Dados**: Tabela paginada dos registros filtrados com botão de download para arquivo CSV.

---

## 7. Execução no Google Colab

O notebook `notebooks/dbt_duckdb_ecommerce_olist.ipynb` foi desenhado para ser executado de ponta a ponta no Google Colab com zero configuração prévia.

O fluxo do notebook contempla:
1. Instalação automatizada das dependências (`dbt-duckdb`, `duckdb`, `pandas`, `kagglehub`).
2. Download direto dos CSVs da Olist via KaggleHub para `raw_data/`.
3. Escrita automática dos arquivos do dbt (`dbt_project.yml`, `sources.yml`, modelos SQL e arquivos YAML de teste).
4. Execução de `dbt run` e `dbt test`.
5. Análise exploratória e consultas SQL conectando diretamente no arquivo `olist_analytics.duckdb` gerado.
