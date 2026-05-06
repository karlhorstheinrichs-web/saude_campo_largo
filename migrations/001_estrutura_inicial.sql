-- ============================================================
-- MIGRACAO 001 - Estrutura inicial do banco de dados
-- Projeto: Modelo Preditivo de Decisao Orcamentaria
-- Funcao Saude - Campo Largo/PR
-- Data: 2026
-- ============================================================

-- --------------------------------------------------------
-- TABELA 1: municipios
-- Cadastro dos municipios do estudo
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS municipios (
    id                  SERIAL PRIMARY KEY,
    codigo_ibge         VARCHAR(7) NOT NULL UNIQUE,
    nome                VARCHAR(100) NOT NULL,
    uf                  VARCHAR(2) NOT NULL DEFAULT 'PR',
    populacao_estimada  INTEGER,
    regiao_metropolitana VARCHAR(100),
    eh_municipio_principal BOOLEAN DEFAULT FALSE,
    criado_em           TIMESTAMP DEFAULT NOW()
);

-- Insere Campo Largo como municipio principal
INSERT INTO municipios (codigo_ibge, nome, uf, populacao_estimada, regiao_metropolitana, eh_municipio_principal)
VALUES ('4104204', 'Campo Largo', 'PR', 140000, 'Regiao Metropolitana de Curitiba', TRUE);

-- --------------------------------------------------------
-- TABELA 2: subfuncoes
-- As 8 subfuncoes da funcao saude identificadas na LOA 2024
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS subfuncoes (
    id                  SERIAL PRIMARY KEY,
    codigo              VARCHAR(10) NOT NULL UNIQUE,
    nome                VARCHAR(100) NOT NULL,
    modelo_financiamento CHAR(1) NOT NULL CHECK (modelo_financiamento IN ('A','B','C','D')),
    -- A = Previne Brasil (capitacao + desempenho)
    -- B = Tabela SUS (pagamento por procedimento)
    -- C = Custo misto fixo + variavel (U/E)
    -- D = Repasse por programa e meta (vigilancias)
    descricao_modelo    VARCHAR(200),
    valor_loa_2024      NUMERIC(15,2),
    eh_nucleo_kcore     BOOLEAN DEFAULT FALSE,
    criado_em           TIMESTAMP DEFAULT NOW()
);

INSERT INTO subfuncoes (codigo, nome, modelo_financiamento, descricao_modelo, valor_loa_2024, eh_nucleo_kcore) VALUES
('301', 'Atencao Basica',                    'A', 'Capitacao + desempenho Previne Brasil', 69554545.87, TRUE),
('302', 'Assistencia Hospitalar e Ambulatorial','B', 'Pagamento por procedimento tabela SUS', 74874474.33, TRUE),
('303', 'Suporte Profilatico e Terapeutico', 'B', 'Farmacia - tabela SUS e programas',     11495918.69, FALSE),
('304', 'Vigilancia Sanitaria',              'D', 'Repasse por programa e meta',            3375300.00, FALSE),
('305', 'Vigilancia Epidemiologica',         'D', 'Repasse por programa e meta',            4224639.87, FALSE),
('306', 'Alimentacao e Nutricao',            'D', 'Repasse por programa e meta',            2770000.00, FALSE),
('122', 'Administracao Geral',               'B', 'Gestao do fundo municipal de saude',     5792891.39, FALSE),
('128', 'Normatizacao e Fiscalizacao',       'D', 'Conselho municipal de saude',              104000.00, FALSE);

-- --------------------------------------------------------
-- TABELA 3: acoes_orcamentarias
-- As 16 acoes reais da LOA 2024 de Campo Largo
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS acoes_orcamentarias (
    id                  SERIAL PRIMARY KEY,
    municipio_id        INTEGER REFERENCES municipios(id),
    subfuncao_id        INTEGER REFERENCES subfuncoes(id),
    codigo_acao         VARCHAR(10) NOT NULL,
    titulo              VARCHAR(200) NOT NULL,
    modelo_financiamento CHAR(1) NOT NULL CHECK (modelo_financiamento IN ('A','B','C','D')),
    valor_loa_2024      NUMERIC(15,2),
    proporcao_subfuncao NUMERIC(5,4),  -- proporcao historica dentro da subfuncao
    ativo               BOOLEAN DEFAULT TRUE,
    exercicio           INTEGER DEFAULT 2024,
    criado_em           TIMESTAMP DEFAULT NOW()
);

-- Insere as 16 acoes reais identificadas no arquivo saude.xls
INSERT INTO acoes_orcamentarias (municipio_id, subfuncao_id, codigo_acao, titulo, modelo_financiamento, valor_loa_2024) VALUES
-- Administracao Geral
(1, 7, '2024', 'Manutencao de Gestao do Fundo Municipal de Saude', 'B', 5792891.39),
-- Normatizacao e Fiscalizacao
(1, 8, '2113', 'Manutencao do Conselho Municipal de Saude', 'D', 104000.00),
-- Atencao Basica
(1, 1, '2101', 'Servicos de Atencao Primaria - Unidades Basicas de Saude', 'A', 69554545.87),
-- Assistencia Hospitalar e Ambulatorial
(1, 2, '2102', 'Acoes de Saude Mental', 'B', 4534163.87),
(1, 2, '2103', 'Acoes de Media Complexidade em Saude', 'B', 12190200.00),
(1, 2, '2104', 'Servicos de Urgencia e Emergencia - UPA', 'C', 45633974.43),
(1, 2, '2105', 'Servicos de Urgencia e Emergencia - SAMU', 'C', 7152190.63),
(1, 2, '2106', 'Consorcios de Saude - Assistencia Hospitalar', 'B', 5163946.40),
(1, 2, '1049', 'Ampliacao da Frota - Urgencia e Emergencia', 'C', 200000.00),
-- Suporte Profilatico e Terapeutico
(1, 3, '2107', 'Acoes de Assistencia Farmaceutica', 'B', 6855933.69),
(1, 3, '2108', 'Consorcios de Saude - Suporte Profilatico', 'B', 4140000.00),
(1, 3, '1055', 'Construcao da Sede da Farmacia Especial', 'B', 499985.00),
-- Vigilancia Sanitaria
(1, 4, '2109', 'Acoes de Vigilancia Sanitaria', 'D', 3375300.00),
-- Vigilancia Epidemiologica
(1, 5, '2110', 'Acoes de Vigilancia Epidemiologica', 'D', 4224639.87),
-- Alimentacao e Nutricao
(1, 6, '2111', 'Acoes de Alimentacao e Nutricao', 'D', 1470000.00),
(1, 6, '2112', 'Consorcios de Saude - Alimentacao e Nutricao', 'D', 1300000.00);

-- Atualiza proporcao dentro da subfuncao
UPDATE acoes_orcamentarias a
SET proporcao_subfuncao = a.valor_loa_2024 / s.total
FROM (
    SELECT subfuncao_id, SUM(valor_loa_2024) as total
    FROM acoes_orcamentarias
    GROUP BY subfuncao_id
) s
WHERE a.subfuncao_id = s.subfuncao_id;

-- --------------------------------------------------------
-- TABELA 4: sinais_leading_ambulatorial
-- Serie temporal mensal de producao ambulatorial SIA-SUS
-- Por subfuncao - leading indicator principal
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS sinais_leading_ambulatorial (
    id                  SERIAL PRIMARY KEY,
    municipio_id        INTEGER REFERENCES municipios(id),
    subfuncao_id        INTEGER REFERENCES subfuncoes(id),
    periodo             DATE NOT NULL,          -- primeiro dia do mes: 2010-01-01
    ano                 INTEGER NOT NULL,
    mes                 INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),

    -- Producao ambulatorial bruta
    total_procedimentos INTEGER,                -- total de procedimentos realizados
    total_consultas     INTEGER,                -- consultas medicas
    total_exames        INTEGER,                -- exames laboratoriais e de imagem
    total_outros        INTEGER,                -- outros procedimentos

    -- Indicadores derivados (calculados na EDA)
    variacao_mensal_pct NUMERIC(8,4),           -- variacao % em relacao ao mes anterior
    media_movel_3m      NUMERIC(12,2),          -- media movel 3 meses
    media_movel_6m      NUMERIC(12,2),          -- media movel 6 meses
    desvio_historico    NUMERIC(8,4),           -- desvio em relacao a media historica

    -- Componentes sazonais (calculados no pre-processamento TFD/Wavelets)
    componente_tendencia NUMERIC(12,2),
    componente_sazonal   NUMERIC(12,2),
    componente_residuo   NUMERIC(12,2),

    -- Regime detectado pelo MSM (preenchido no modulo 2)
    regime_msm          VARCHAR(20) CHECK (regime_msm IN ('equilibrio','alerta','colapso')),
    prob_equilibrio     NUMERIC(6,4),
    prob_alerta         NUMERIC(6,4),
    prob_colapso        NUMERIC(6,4),

    -- Metadados
    fonte               VARCHAR(50) DEFAULT 'SIA-SUS',
    criado_em           TIMESTAMP DEFAULT NOW(),
    atualizado_em       TIMESTAMP DEFAULT NOW(),

    UNIQUE (municipio_id, subfuncao_id, periodo)
);

-- --------------------------------------------------------
-- TABELA 5: sinais_lagging_siops
-- Serie temporal mensal de execucao orcamentaria por acao
-- Extraida do SIOPS - variaveis dependentes Y1 e Y2
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS sinais_lagging_siops (
    id                  SERIAL PRIMARY KEY,
    municipio_id        INTEGER REFERENCES municipios(id),
    acao_id             INTEGER REFERENCES acoes_orcamentarias(id),
    periodo             DATE NOT NULL,
    ano                 INTEGER NOT NULL,
    mes                 INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),

    -- Execucao orcamentaria
    dotacao_inicial     NUMERIC(15,2),
    dotacao_atualizada  NUMERIC(15,2),
    empenhado           NUMERIC(15,2),
    liquidado           NUMERIC(15,2),
    pago                NUMERIC(15,2),

    -- Suplementacoes (variaveis dependentes)
    houve_suplementacao BOOLEAN DEFAULT FALSE,  -- Y1
    valor_suplementado  NUMERIC(15,2) DEFAULT 0, -- Y2
    tipo_instrumento    VARCHAR(50),             -- decreto ou projeto de lei

    -- Percentual de execucao
    pct_execucao        NUMERIC(6,4),           -- liquidado / dotacao_atualizada

    -- Metadados
    fonte               VARCHAR(50) DEFAULT 'SIOPS',
    criado_em           TIMESTAMP DEFAULT NOW(),

    UNIQUE (municipio_id, acao_id, periodo)
);

-- --------------------------------------------------------
-- TABELA 6: parametros_custo
-- Parametros do MDS por modelo de financiamento
-- Atualizados quando ha repactuacao federal
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS parametros_custo (
    id                  SERIAL PRIMARY KEY,
    subfuncao_id        INTEGER REFERENCES subfuncoes(id),
    modelo_financiamento CHAR(1) NOT NULL,
    parametro           VARCHAR(100) NOT NULL,  -- nome do parametro
    valor               NUMERIC(15,4) NOT NULL,
    unidade             VARCHAR(50),            -- por pessoa, por equipe, por procedimento
    eh_constante_exogena BOOLEAN DEFAULT FALSE, -- TRUE = parametro federal fixo
    fonte_referencia    VARCHAR(200),           -- portaria, tabela SUS, etc
    vigencia_inicio     DATE NOT NULL,
    vigencia_fim        DATE,                   -- NULL = vigente
    criado_em           TIMESTAMP DEFAULT NOW()
);

-- Parametros iniciais do Previne Brasil (Modelo A)
INSERT INTO parametros_custo (subfuncao_id, modelo_financiamento, parametro, valor, unidade, eh_constante_exogena, fonte_referencia, vigencia_inicio) VALUES
(1, 'A', 'capitacao_per_capita_mensal',     6.55,  'R$/pessoa/mes',    TRUE,  'Portaria GM/MS 3222/2019 e atualizacoes', '2024-01-01'),
(1, 'A', 'custo_equipe_esf_mensal',     44000.00,  'R$/equipe/mes',    TRUE,  'Piso da Atencao Basica 2024',             '2024-01-01'),
(1, 'A', 'bonus_desempenho_maximo',     10000.00,  'R$/equipe/bimestre',TRUE, 'Componente desempenho Previne Brasil',    '2024-01-01');

-- --------------------------------------------------------
-- TABELA 7: parametros_institucionais_cvi
-- Dados historicos para o Componente de Viabilidade Institucional
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS parametros_institucionais_cvi (
    id                      SERIAL PRIMARY KEY,
    municipio_id            INTEGER REFERENCES municipios(id),
    exercicio               INTEGER NOT NULL,
    limite_suplementacao_loa NUMERIC(15,2),      -- limite % autorizado na LOA para suplementacao
    saldo_credito_disponivel NUMERIC(15,2),      -- saldo disponivel no periodo
    prazo_decreto_dias      INTEGER DEFAULT 5,   -- prazo medio para decreto executivo
    prazo_projeto_lei_dias  INTEGER DEFAULT 45,  -- prazo medio para PL de credito adicional
    periodo                 DATE,
    criado_em               TIMESTAMP DEFAULT NOW()
);

-- --------------------------------------------------------
-- TABELA 8: resultados_ipcso
-- Armazena as recomendacoes geradas pelo IPCSO-S
-- Rastreabilidade dos alertas e recomendacoes
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS resultados_ipcso (
    id                  SERIAL PRIMARY KEY,
    municipio_id        INTEGER REFERENCES municipios(id),
    subfuncao_id        INTEGER REFERENCES subfuncoes(id),
    periodo_alerta      DATE NOT NULL,          -- periodo em que o alerta foi gerado
    periodo_previsto    DATE NOT NULL,          -- periodo previsto para suplementacao (t+1)

    -- Componentes do IPCSO-S
    iam                 NUMERIC(6,4),           -- Indice de Anomalia MSM
    icd                 NUMERIC(6,4),           -- Indice de Confianca da Deteccao
    ics                 NUMERIC(6,4),           -- Indice de Contagio Sistemico
    pna                 NUMERIC(6,4),           -- Peso Normativo AHP-Gaussiano
    ipcso_s             NUMERIC(6,4),           -- Indice final normalizado

    -- Previsoes
    y1_previsto         BOOLEAN,                -- previsao de ocorrencia de suplementacao
    y2_estimado         NUMERIC(15,2),          -- valor estimado da suplementacao
    modelo_financiamento CHAR(1),               -- modelo de custo utilizado (A/B/C/D)
    cenario             VARCHAR(20),            -- intra_capacidade ou extra_capacidade
    fonte_recomendada   VARCHAR(100),           -- fonte de recurso recomendada

    -- CVI - Viabilidade Institucional
    saldo_credito       NUMERIC(15,2),
    instrumento_juridico VARCHAR(50),           -- decreto ou projeto_lei
    prazo_execucao_dias INTEGER,
    semaforo_cvi        VARCHAR(10) CHECK (semaforo_cvi IN ('verde','amarelo','vermelho')),

    -- Resultado real (preenchido depois para validacao)
    y1_realizado        BOOLEAN,
    y2_realizado        NUMERIC(15,2),
    data_suplementacao  DATE,

    -- Metadados
    modelo_versao       VARCHAR(20),            -- versao do modelo (1,2,3,4)
    mlflow_run_id       VARCHAR(100),           -- rastreamento MLflow
    criado_em           TIMESTAMP DEFAULT NOW()
);

-- --------------------------------------------------------
-- INDICES para performance
-- --------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_ambulatorial_periodo   ON sinais_leading_ambulatorial(municipio_id, subfuncao_id, periodo);
CREATE INDEX IF NOT EXISTS idx_siops_periodo          ON sinais_lagging_siops(municipio_id, acao_id, periodo);
CREATE INDEX IF NOT EXISTS idx_resultados_periodo     ON resultados_ipcso(municipio_id, subfuncao_id, periodo_alerta);

-- --------------------------------------------------------
-- Mensagem de confirmacao
-- --------------------------------------------------------
DO $$
BEGIN
    RAISE NOTICE 'Migracao 001 executada com sucesso!';
    RAISE NOTICE 'Tabelas criadas: municipios, subfuncoes, acoes_orcamentarias,';
    RAISE NOTICE '                 sinais_leading_ambulatorial, sinais_lagging_siops,';
    RAISE NOTICE '                 parametros_custo, parametros_institucionais_cvi,';
    RAISE NOTICE '                 resultados_ipcso';
    RAISE NOTICE 'Dados iniciais inseridos: 1 municipio, 8 subfuncoes, 16 acoes orcamentarias';
END $$;
