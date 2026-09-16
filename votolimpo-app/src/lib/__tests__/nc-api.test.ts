/**
 * Testes unitarios para as funcoes de transformacao em nc-api.ts
 *
 * Cobre: entityToPolitician, ncArticleToArticle, ncStatsToStats, getSourceReliability
 * Todos os testes usam dados mockados inline — sem rede/API.
 */

import { describe, it, expect } from 'vitest';
import {
  entityToPolitician,
  ncArticleToArticle,
  ncStatsToStats,
  getSourceReliability,
  type NCEntity,
  type NCArticle,
  type NCStats,
  type NCVotoLimpoStats,
  type NCEntityScore,
} from '../nc-api';

// ---------------------------------------------------------------------------
// Helpers / factories
// ---------------------------------------------------------------------------

function makeEntity(overrides: Partial<NCEntity> = {}): NCEntity {
  return {
    id: 1,
    name: 'Fulano Silva',
    slug: 'fulano-silva',
    type: 'candidate',
    cpf_hash: null,
    party: 'PT',
    state: 'SP',
    role: 'Deputado Federal',
    active: true,
    metadata_json: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-06-01T00:00:00Z',
    ...overrides,
  };
}

function makeArticle(overrides: Partial<NCArticle> = {}): NCArticle {
  return {
    id: 10,
    job_id: 1,
    url: 'https://g1.globo.com/noticias/artigo.html',
    url_hash: 'abc123',
    title: 'Titulo do artigo',
    content: '<p>Conteudo do artigo</p>',
    summary: 'Resumo do artigo',
    author: 'Redacao',
    published_at: '2024-05-01T10:00:00Z',
    source_domain: 'g1.globo.com',
    source_name: 'G1',
    language: 'pt',
    sentiment: 'neutral',
    sentiment_score: 0.5,
    processing_status: 'processed',
    word_count: 300,
    created_at: '2024-05-01T11:00:00Z',
    updated_at: '2024-05-01T12:00:00Z',
    entities_linked: null,
    severity: 'low',
    is_political: true,
    score: 7,
    score_breakdown: { veracidade: 0.7 },
    pe_keywords: ['corrupcao', 'licitacao'],
    politicians: ['fulano-silva'],
    ...overrides,
  };
}

function makeNCStats(overrides: Partial<NCStats['database']> = {}): NCStats {
  return {
    database: {
      total_entities: 19514,
      total_sources: 42,
      total_articles: 120000,
      total_jobs: 500,
      articles_last_24h: 350,
      jobs_last_24h: 12,
      dedup_rate: 0.15,
      ...overrides,
    },
    scheduler_running: true,
    collected_at: '2024-09-01T08:00:00Z',
  };
}

// ---------------------------------------------------------------------------
// entityToPolitician
// ---------------------------------------------------------------------------

describe('entityToPolitician', () => {
  it('mapeia entidade completa corretamente', () => {
    const entity = makeEntity();
    const politician = entityToPolitician(entity);

    expect(politician.id).toBe('1');
    expect(politician.slug).toBe('fulano-silva');
    expect(politician.name).toBe('Fulano Silva');
    expect(politician.party).toBe('PT');
    expect(politician.partyColor).toBe('#CC0000');
    expect(politician.uf).toBe('SP');
    expect(politician.role).toBe('Deputado Federal');
    expect(politician.createdAt).toBe('2024-01-01T00:00:00Z');
    expect(politician.updatedAt).toBe('2024-06-01T00:00:00Z');
  });

  it('partido null -> "Sem Partido" e cor cinza', () => {
    const entity = makeEntity({ party: null });
    const politician = entityToPolitician(entity);

    expect(politician.party).toBe('Sem Partido');
    expect(politician.partyColor).toBe('#6B7280');
  });

  it('partido desconhecido -> cor cinza padrao', () => {
    const entity = makeEntity({ party: 'XYZABC' });
    const politician = entityToPolitician(entity);

    expect(politician.partyColor).toBe('#6B7280');
  });

  it('state null, metadata com uf_candidatura -> usa uf_candidatura', () => {
    const entity = makeEntity({
      state: null,
      metadata_json: JSON.stringify({ uf_candidatura: 'RJ' }),
    });
    const politician = entityToPolitician(entity);
    expect(politician.uf).toBe('RJ');
  });

  it('state null, metadata null -> uf fallback "BR"', () => {
    const entity = makeEntity({ state: null, metadata_json: null });
    const politician = entityToPolitician(entity);
    expect(politician.uf).toBe('BR');
  });

  it('metadata_json invalido -> nao explode, photoUrl undefined, uf "BR"', () => {
    const entity = makeEntity({ state: null, metadata_json: 'not json' });
    const politician = entityToPolitician(entity);
    expect(politician.photoUrl).toBeUndefined();
    expect(politician.uf).toBe('BR');
  });

  it('metadata_json com foto_url -> photoUrl preenchido', () => {
    const url = 'https://example.com/foto.jpg';
    const entity = makeEntity({ metadata_json: JSON.stringify({ foto_url: url }) });
    const politician = entityToPolitician(entity);
    expect(politician.photoUrl).toBe(url);
  });

  it('sem segundo argumento -> articleCount 0 (default)', () => {
    const entity = makeEntity();
    const politician = entityToPolitician(entity);
    expect(politician.articleCount).toBe(0);
  });

  it('scoreData explicito -> usa article_count e score do scoreData', () => {
    const entity = makeEntity();
    const scoreData: NCEntityScore = {
      entity_id: 1,
      score: 75,
      max_severity: 'medium',
      article_count: 42,
    };
    const politician = entityToPolitician(entity, scoreData);
    expect(politician.articleCount).toBe(42);
    expect(politician.score).toBe(75);
    expect(politician.maxSeverity).toBe('medium');
  });

  it('scoreData com score null -> score 0', () => {
    const entity = makeEntity();
    const scoreData: NCEntityScore = {
      entity_id: 1,
      score: null,
      max_severity: 'info',
      article_count: 5,
    };
    const politician = entityToPolitician(entity, scoreData);
    expect(politician.score).toBe(0);
  });

  it('campos hardcoded: milestoneCount sempre 0', () => {
    const entity = makeEntity();
    const politician = entityToPolitician(entity);
    expect(politician.milestoneCount).toBe(0);
  });

  it('maxSeverity "critical" e mapeado corretamente', () => {
    const entity = makeEntity();
    const scoreData: NCEntityScore = {
      entity_id: 1,
      score: 10,
      max_severity: 'critical',
      article_count: 10,
    };
    const politician = entityToPolitician(entity, scoreData);
    expect(politician.maxSeverity).toBe('critical');
  });

  it('maxSeverity invalida do backend -> fallback "info"', () => {
    const entity = makeEntity();
    const scoreData: NCEntityScore = {
      entity_id: 1,
      score: 50,
      max_severity: 'banana',
      article_count: 1,
    };
    const politician = entityToPolitician(entity, scoreData);
    expect(politician.maxSeverity).toBe('info');
  });
});

// ---------------------------------------------------------------------------
// ncArticleToArticle
// ---------------------------------------------------------------------------

describe('ncArticleToArticle', () => {
  it('artigo com PE severity "critical" -> severity "critical"', () => {
    const article = makeArticle({ severity: 'critical' });
    const result = ncArticleToArticle(article);
    expect(result.severity).toBe('critical');
  });

  it('artigo com PE severity "low" -> severity "low"', () => {
    const article = makeArticle({ severity: 'low' });
    const result = ncArticleToArticle(article);
    expect(result.severity).toBe('low');
  });

  it('severity invalida do PE -> fallback "info"', () => {
    const article = makeArticle({ severity: 'banana' });
    const result = ncArticleToArticle(article);
    expect(result.severity).toBe('info');
  });

  it('sem PE severity, sentiment_score 0.1 -> "critical"', () => {
    const article = makeArticle({ severity: null, sentiment_score: 0.1 });
    const result = ncArticleToArticle(article);
    expect(result.severity).toBe('critical');
  });

  it('sem PE severity, sentiment_score 0.3 -> "high"', () => {
    const article = makeArticle({ severity: null, sentiment_score: 0.3 });
    const result = ncArticleToArticle(article);
    expect(result.severity).toBe('high');
  });

  it('sem PE severity, sentiment_score 0.45 -> "medium"', () => {
    const article = makeArticle({ severity: null, sentiment_score: 0.45 });
    const result = ncArticleToArticle(article);
    expect(result.severity).toBe('medium');
  });

  it('sem PE severity, sentiment_score 0.55 -> "low"', () => {
    const article = makeArticle({ severity: null, sentiment_score: 0.55 });
    const result = ncArticleToArticle(article);
    expect(result.severity).toBe('low');
  });

  it('sem PE severity, sentiment_score 0.8 -> "info"', () => {
    const article = makeArticle({ severity: null, sentiment_score: 0.8 });
    const result = ncArticleToArticle(article);
    expect(result.severity).toBe('info');
  });

  it('sem PE severity, sem sentiment_score -> "info"', () => {
    const article = makeArticle({ severity: null, sentiment_score: null });
    const result = ncArticleToArticle(article);
    expect(result.severity).toBe('info');
  });

  it('PE score 7 -> truthScore 0.7', () => {
    const article = makeArticle({ score: 7 });
    const result = ncArticleToArticle(article);
    expect(result.truthScore).toBe(0.7);
  });

  it('PE score null, sentiment_score 0.65 -> truthScore 0.65', () => {
    const article = makeArticle({ score: null, sentiment_score: 0.65 });
    const result = ncArticleToArticle(article);
    expect(result.truthScore).toBe(0.65);
  });

  it('PE score null, sentiment null -> truthScore 0.5', () => {
    const article = makeArticle({ score: null, sentiment_score: null });
    const result = ncArticleToArticle(article);
    expect(result.truthScore).toBe(0.5);
  });

  it('title vazio, content com HTML -> extrai titulo do HTML', () => {
    const article = makeArticle({ title: '', content: '<h1>Titulo Extraido</h1>' });
    const result = ncArticleToArticle(article);
    expect(result.title).toBe('Titulo Extraido');
  });

  it('title e content vazios -> title vazio string', () => {
    const article = makeArticle({ title: '', content: '' });
    const result = ncArticleToArticle(article);
    expect(result.title).toBe('');
  });

  it('source_domain null -> source.name "Fonte desconhecida", source.url ""', () => {
    const article = makeArticle({ source_domain: null, source_name: null });
    const result = ncArticleToArticle(article);
    expect(result.source.name).toBe('Fonte desconhecida');
    expect(result.source.url).toBe('');
  });

  it('pe_keywords null -> tags []', () => {
    const article = makeArticle({ pe_keywords: null });
    const result = ncArticleToArticle(article);
    expect(result.tags).toEqual([]);
  });

  it('politicians null -> politicianIds []', () => {
    const article = makeArticle({ politicians: null });
    const result = ncArticleToArticle(article);
    expect(result.politicianIds).toEqual([]);
  });

  it('mapeia campos basicos corretamente', () => {
    const article = makeArticle();
    const result = ncArticleToArticle(article);
    expect(result.id).toBe('10');
    expect(result.url).toBe('https://g1.globo.com/noticias/artigo.html');
    expect(result.summary).toBe('Resumo do artigo');
    expect(result.publishedAt).toBe('2024-05-01T10:00:00Z');
    expect(result.isPolitical).toBe(true);
    expect(result.processingStatus).toBe('processed');
    expect(result.tags).toEqual(['corrupcao', 'licitacao']);
    expect(result.politicianIds).toEqual(['fulano-silva']);
  });

  it('source.reliability de dominio conhecido (g1.globo.com) -> 0.9', () => {
    const article = makeArticle({ source_domain: 'g1.globo.com' });
    const result = ncArticleToArticle(article);
    expect(result.source.reliability).toBe(0.9);
  });

  it('source.reliability de dominio desconhecido -> 0.6', () => {
    const article = makeArticle({ source_domain: 'desconhecido.com' });
    const result = ncArticleToArticle(article);
    expect(result.source.reliability).toBe(0.6);
  });
});

// ---------------------------------------------------------------------------
// ncStatsToStats
// ---------------------------------------------------------------------------

describe('ncStatsToStats', () => {
  it('mapeia stats normais corretamente', () => {
    const ncStats = makeNCStats();
    const result = ncStatsToStats(ncStats);

    expect(result.totalPoliticians).toBe(19514);
    expect(result.totalArticles).toBe(120000);
    expect(result.totalEntities).toBe(19514);
    expect(result.totalRelationships).toBe(42);
  });

  it('totalRelationships vem de total_sources', () => {
    const ncStats = makeNCStats({ total_sources: 99 });
    const result = ncStatsToStats(ncStats);
    expect(result.totalRelationships).toBe(99);
  });

  it('sem vlStats -> avgScore 0 e criticalCount 0 (hardcoded fallback)', () => {
    const ncStats = makeNCStats();
    const result = ncStatsToStats(ncStats);
    // Documenta o comportamento hardcoded: sem vlStats, ambos sao 0
    expect(result.avgScore).toBe(0);
    expect(result.criticalCount).toBe(0);
  });

  it('com vlStats -> usa avg_score e critical_count', () => {
    const ncStats = makeNCStats();
    const vlStats: NCVotoLimpoStats = {
      avg_score: 72,
      critical_count: 5,
      entities_with_articles: 100,
    };
    const result = ncStatsToStats(ncStats, vlStats);
    expect(result.avgScore).toBe(72);
    expect(result.criticalCount).toBe(5);
  });

  it('vlStats com avg_score null -> avgScore 0', () => {
    const ncStats = makeNCStats();
    const vlStats: NCVotoLimpoStats = {
      avg_score: null,
      critical_count: 3,
      entities_with_articles: 50,
    };
    const result = ncStatsToStats(ncStats, vlStats);
    expect(result.avgScore).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// getSourceReliability (helper exportado)
// ---------------------------------------------------------------------------

describe('getSourceReliability', () => {
  it('dominio null -> 0.5', () => {
    expect(getSourceReliability(null)).toBe(0.5);
  });

  it('dominio desconhecido -> 0.6', () => {
    expect(getSourceReliability('xyzdesconhecido.com')).toBe(0.6);
  });

  it('g1.globo.com -> 0.9', () => {
    expect(getSourceReliability('g1.globo.com')).toBe(0.9);
  });

  it('www.g1.globo.com -> 0.9 (strip www)', () => {
    expect(getSourceReliability('www.g1.globo.com')).toBe(0.9);
  });

  it('bbc.com -> 0.95', () => {
    expect(getSourceReliability('bbc.com')).toBe(0.95);
  });

  it('tse.jus.br -> 0.95', () => {
    expect(getSourceReliability('tse.jus.br')).toBe(0.95);
  });
});
