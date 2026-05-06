# Modelo Preditivo de Decisão Orçamentária — Função Saúde Municipal

**Projeto de Doutorado — PPGPGP/UTFPR**
**Autor:** Karl Horst Heinrichs
**Orientadora:** Profa. Dra. Maria Lúcia Figueiredo Gomes de Meza
**Município:** Campo Largo/PR

---

## O que é este projeto

Este repositório contém o protótipo computacional do modelo IPCSO-S — Índice de Prioridade Composto para Suplementação Orçamentária da Saúde — desenvolvido como parte da tese de doutorado em Planejamento e Governança Pública.

O modelo prediz:
- **Y1** — ocorrência de suplementação orçamentária na função saúde (variável binária)
- **Y2** — valor monetário da suplementação necessária por ação orçamentária (variável contínua)

E gera recomendações completas com prioridade, valor estimado, fonte de recursos e semáforo de viabilidade institucional.

---

## Arquitetura do modelo

```
Sinais Leading (SIA-SUS, SIH-SUS, SISAB)
        ↓
Pré-processamento (TFD + Wavelets)
        ↓
Markov-switching por subfunção → Y1 previsto
        ↓
MDS diferenciado (Modelos A/B/C/D) → Y2 estimado
        ↓
Rede Multiplex + ICS dinâmico
        ↓
IPCSO-S + CVI (semáforo institucional)
        ↓
Recomendação: ação + valor + fonte + semáforo
```

---

## Estrutura do repositório

```
saude_campo_largo/
│
├── README.md                    ← este arquivo
├── requirements.txt             ← bibliotecas necessárias
├── .env.example                 ← modelo de credenciais (sem dados reais)
├── .gitignore                   ← arquivos ignorados pelo Git
│
├── migrations/
│   └── 001_estrutura_inicial.sql  ← estrutura do banco de dados
│
├── modulo_1_coleta/
│   └── coleta_ambulatorial.py   ← coleta SIA-SUS e pré-processamento
│
├── modulo_2_msm/                ← Markov-switching (em desenvolvimento)
├── modulo_3_mds/                ← Dimensionamento por modelo de financiamento
├── modulo_4_ipcso/              ← Rede multiplex e IPCSO-S
└── modulo_5_dashboard/          ← Dashboard Streamlit
```

---

## Como instalar

```bash
# Clone o repositório
git clone https://github.com/karlheinrichs/saude_campo_largo.git
cd saude_campo_largo

# Crie um ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Instale as dependências
pip install -r requirements.txt

# Configure as credenciais
cp .env.example .env
# Edite o arquivo .env com suas credenciais do Supabase
```

---

## Como configurar o banco de dados

```bash
# No painel do Supabase, vá em Editor SQL e execute:
# migrations/001_estrutura_inicial.sql
```

---

## Como executar o Módulo 1 (coleta de dados)

```bash
python modulo_1_coleta/coleta_ambulatorial.py
```

Por padrão executa com dados simulados. Para usar dados reais do SIA-SUS,
altere o parâmetro `usar_dados_simulados=False` (disponível no Ano 1 do doutorado).

---

## Rastreamento de experimentos com MLflow

```bash
# Inicia o servidor local do MLflow
mlflow ui

# Acesse em: http://localhost:5000
```

---

## Banco de dados (Supabase)

O projeto usa PostgreSQL via Supabase. As tabelas são:

| Tabela | Descrição |
|--------|-----------|
| `municipios` | Cadastro dos municípios do estudo |
| `subfuncoes` | 8 subfunções da função saúde |
| `acoes_orcamentarias` | 16 ações da LOA 2024 Campo Largo |
| `sinais_leading_ambulatorial` | Produção ambulatorial SIA-SUS (Y leading) |
| `sinais_lagging_siops` | Execução orçamentária SIOPS (Y1 e Y2) |
| `parametros_custo` | Parâmetros MDS por modelo de financiamento |
| `parametros_institucionais_cvi` | Dados históricos para o CVI |
| `resultados_ipcso` | Recomendações geradas pelo IPCSO-S |

---

## Modelos de financiamento do MDS

| Modelo | Subfunção | Lógica |
|--------|-----------|--------|
| A | Atenção Básica | Capitação + desempenho (Previne Brasil) |
| B | Média e Alta Complexidade | Pagamento por procedimento (tabela SUS) |
| C | Urgência e Emergência | Custo misto fixo + variável |
| D | Vigilâncias e Farmácia | Repasse por programa e meta |

---

## Status do desenvolvimento

- [x] Estrutura do banco de dados
- [x] Módulo 1 — Coleta e pré-processamento (dados simulados)
- [ ] Módulo 1 — Download real SIA-SUS (Ano 1)
- [ ] Módulo 2 — Markov-switching (Ano 2)
- [ ] Módulo 3 — MDS diferenciado (Ano 2)
- [ ] Módulo 4 — Rede multiplex e IPCSO-S (Ano 2)
- [ ] Módulo 5 — Dashboard Streamlit (Ano 3)

---

## Licença

Creative Commons Attribution 4.0 International (CC BY 4.0)
