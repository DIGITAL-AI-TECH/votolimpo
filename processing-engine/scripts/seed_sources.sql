-- Seed: principais fontes de notícias do Brasil e do mundo
-- Inserir com ON CONFLICT para não duplicar fontes já existentes (auto-criadas pelo sink)
-- reputation_score: 0.00-0.99 (quanto maior, mais confiável)

INSERT INTO votolimpo.sources (name, domain, reputation_score, category) VALUES
-- ============================================================
-- BRASIL — Mainstream (grandes veículos)
-- ============================================================
('g1.globo.com',           'g1.globo.com',           0.85, 'mainstream'),
('folha.uol.com.br',       'folha.uol.com.br',       0.85, 'mainstream'),
('estadao.com.br',         'estadao.com.br',          0.85, 'mainstream'),
('oglobo.globo.com',       'oglobo.globo.com',        0.85, 'mainstream'),
('uol.com.br',             'uol.com.br',              0.75, 'mainstream'),
('terra.com.br',           'terra.com.br',             0.70, 'mainstream'),
('r7.com',                 'r7.com',                   0.70, 'mainstream'),
('band.uol.com.br',        'band.uol.com.br',         0.75, 'mainstream'),
('cnn.com.br',             'cnn.com.br',               0.75, 'mainstream'),
('bbc.com/portuguese',      'bbc.com',                 0.90, 'mainstream'),
('metropoles.com',          'metropoles.com',          0.75, 'mainstream'),
('poder360.com.br',         'poder360.com.br',         0.80, 'mainstream'),
('infomoney.com.br',        'infomoney.com.br',        0.80, 'mainstream'),
('valor.globo.com',         'valor.globo.com',         0.85, 'mainstream'),
('gazetadopovo.com.br',     'gazetadopovo.com.br',     0.75, 'mainstream'),
('cartacapital.com.br',     'cartacapital.com.br',     0.70, 'mainstream'),
('revistaforum.com.br',     'revistaforum.com.br',     0.55, 'mainstream'),
('crusoemagazine.com.br',   'crusoemagazine.com.br',   0.65, 'mainstream'),
('jornaldacidadeonline.com.br', 'jornaldacidadeonline.com.br', 0.45, 'portal'),
('diariodopoder.com.br',    'diariodopoder.com.br',    0.65, 'mainstream'),
('correiobraziliense.com.br', 'correiobraziliense.com.br', 0.75, 'mainstream'),
('istoe.com.br',            'istoe.com.br',            0.70, 'mainstream'),
('veja.abril.com.br',       'veja.abril.com.br',       0.75, 'mainstream'),
('exame.com',               'exame.com',               0.75, 'mainstream'),
('epocanegocios.globo.com', 'epocanegocios.globo.com', 0.75, 'mainstream'),

-- ============================================================
-- BRASIL — Regionais
-- ============================================================
('gazetaonline.com.br',     'gazetaonline.com.br',     0.65, 'regional'),
('diariodepernambuco.com.br', 'diariodepernambuco.com.br', 0.65, 'regional'),
('correio24horas.com.br',   'correio24horas.com.br',   0.65, 'regional'),
('nsctotal.com.br',          'nsctotal.com.br',         0.65, 'regional'),
('zerohora.com.br',          'zerohora.com.br',         0.70, 'regional'),
('jornaldocomercio.com',     'jornaldocomercio.com',    0.65, 'regional'),

-- ============================================================
-- BRASIL — Governo / Institucionais
-- ============================================================
('gov.br',                   'gov.br',                  0.90, 'govt'),
('agenciabrasil.ebc.com.br', 'agenciabrasil.ebc.com.br', 0.85, 'agency'),
('camara.leg.br',            'camara.leg.br',           0.90, 'govt'),
('senado.leg.br',            'senado.leg.br',           0.90, 'govt'),
('stf.jus.br',               'stf.jus.br',             0.90, 'govt'),
('tse.jus.br',               'tse.jus.br',             0.90, 'govt'),

-- ============================================================
-- INTERNACIONAL — Mainstream
-- ============================================================
('reuters.com',              'reuters.com',             0.95, 'international'),
('apnews.com',               'apnews.com',             0.95, 'international'),
('bbc.com',                  'bbc.com',                 0.90, 'international'),
('nytimes.com',              'nytimes.com',             0.90, 'international'),
('washingtonpost.com',       'washingtonpost.com',      0.90, 'international'),
('theguardian.com',          'theguardian.com',         0.85, 'international'),
('cnn.com',                  'cnn.com',                 0.80, 'international'),
('aljazeera.com',            'aljazeera.com',           0.80, 'international'),
('france24.com',             'france24.com',            0.80, 'international'),
('dw.com',                   'dw.com',                  0.80, 'international'),
('elpais.com',               'elpais.com',              0.85, 'international'),
('lemonde.fr',               'lemonde.fr',              0.85, 'international'),
('ft.com',                   'ft.com',                  0.90, 'international'),
('economist.com',            'economist.com',           0.90, 'international'),
('wsj.com',                  'wsj.com',                 0.90, 'international'),
('bloomberg.com',            'bloomberg.com',           0.90, 'international'),

-- ============================================================
-- AGÊNCIAS DE NOTÍCIA
-- ============================================================
('afp.com',                  'afp.com',                 0.95, 'agency'),
('efe.com',                  'efe.com',                 0.90, 'agency'),
('xinhua.net',               'xinhua.net',              0.65, 'agency'),
('tass.com',                 'tass.com',                0.55, 'agency'),

-- ============================================================
-- PORTAIS / AGREGADORES (score mais baixo)
-- ============================================================
('msn.com',                  'msn.com',                 0.55, 'portal'),
('yahoo.com',                'yahoo.com',               0.60, 'portal'),
('ig.com.br',                'ig.com.br',               0.55, 'portal'),
('bol.uol.com.br',           'bol.uol.com.br',         0.55, 'portal')

ON CONFLICT (name) DO UPDATE SET
    reputation_score = EXCLUDED.reputation_score,
    category = EXCLUDED.category,
    domain = EXCLUDED.domain,
    updated_at = NOW();
