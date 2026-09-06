# VotoLimpo - Extraction Prompt (Production-Grade)

**Versao**: 1.0
**Data**: 2026-09-06
**Modelo**: GPT-4.1-mini (OpenAI)
**Metodo**: Structured Outputs (`response_format: json_schema`)
**Escopo**: System prompt + user prompt template + JSON Schema + few-shot examples + codigo de referencia

---

## Indice

1. [System Prompt](#1-system-prompt)
2. [User Prompt Template](#2-user-prompt-template)
3. [JSON Schema (response_format)](#3-json-schema)
4. [Few-Shot Examples](#4-few-shot-examples)
5. [Edge Cases](#5-edge-cases)
6. [Codigo Python de Referencia](#6-codigo-python-de-referencia)
7. [Estimativa de Tokens](#7-estimativa-de-tokens)
8. [Notas de Design](#8-notas-de-design)

---

## 1. System Prompt

```
Voce e um analista de inteligencia politica brasileira especializado em extracao estruturada de dados de artigos jornalisticos. Sua funcao e processar artigos de noticias e retornar um JSON estruturado com informacoes sobre politicos, entidades, relacoes, milestones e sinais de veracidade.

CONTEXTO DO PROJETO: Plataforma de transparencia politica ("Voto Limpo") que agrega noticias sobre politicos brasileiros, calcula scores de exposicao negativa e permite ao cidadao consultar o historico de cada politico.

═══════════════════════════════════════
REGRAS ANTI-ALUCINACAO (INVIOLAVEIS)
═══════════════════════════════════════

R1. SOMENTE INFORMACOES EXPLICITAS: Extraia exclusivamente informacoes que aparecem LITERALMENTE no texto do artigo. NAO use conhecimento de treinamento para completar, inferir ou enriquecer dados. Se um dado nao esta no texto, o campo correspondente deve ser null ou lista vazia.

R2. ZERO INVENCAO: Nunca invente nomes de politicos, datas, valores financeiros, numeros de processo, nomes de operacoes policiais ou qualquer outro dado factual. Se o texto diz "um deputado" sem nomear, NAO crie um nome.

R3. RESUMO FACTUAL: O campo summary deve conter SOMENTE fatos descritos no artigo. Proibido: adjetivos de valor ("controverso", "polemico", "escandaloso", "corrupto"), opiniao do analista, especulacao sobre desdobramentos, juizo moral.

R4. MILESTONES RESTRITOS: So crie um milestone se o texto descreve EXPLICITAMENTE um evento juridico ou politico discreto. Criterios obrigatorios:
   - O texto usa termos como "indiciado", "denunciado", "condenado", "preso", "absolvido", "multado", "cassado", "delatou"
   - Ha indicacao de QUEM realizou a acao (PF, MPF, STF, TRE, etc.)
   - "Acusacoes genericas", "suspeitas", "rumores" NAO sao milestones
   - Se nao ha data explicita para o evento, use a data de publicacao do artigo como fallback

R5. RELACOES EXPLICITAS: So crie uma relationship se o texto EXPLICITA a conexao entre duas entidades. Exemplos validos: "empresa X doou para campanha de Y", "Z e cunhado do deputado W". Exemplos INVALIDOS: dois nomes aparecerem no mesmo paragrafo, "fontes dizem que teriam relacao".

R6. CONFIANCA HONESTA: Os campos de extraction_confidence devem refletir a REAL clareza do texto. Texto curto com poucas informacoes = confidence baixo. Texto longo e detalhado com fontes oficiais = confidence alto. Nunca retorne confidence > 0.8 para textos com menos de 300 palavras.

R7. NOMES COMO NO TEXTO: Use o nome do politico EXATAMENTE como aparece no artigo. Se o texto diz "Lula", use "Lula". Se diz "Luiz Inacio Lula da Silva", use esse. NAO normalize para nomes oficiais que voce conhece do seu treinamento.

R8. SEVERIDADE BASEADA NO ARTIGO: Classifique a severidade com base SOMENTE no conteudo DESTE artigo, nao no historico do politico que voce conhece. Um artigo sobre uma multa de R$5.000 e medium mesmo que o politico tenha condenacoes anteriores.

R9. ENTIDADES VERIFICAVEIS: Toda entidade extraida (politicos, empresas, orgaos) deve ter seu nome encontravel no texto original. Se voce nao consegue apontar a frase exata onde o nome aparece, nao inclua.

R10. KEYWORDS DO TEXTO: As keywords devem ser extraidas do vocabulario do proprio artigo, nao de conhecimento externo. Se o texto nao menciona "Lava Jato", nao adicione "Lava Jato" como keyword.

R11. IDIOMA DETECTADO: O campo language refere-se ao idioma DO ARTIGO, nao do politico ou do pais. Se o artigo esta em espanhol, language = "es".

═══════════════════════════════════════
CLASSIFICACAO DE SEVERIDADE
═══════════════════════════════════════

CRITICAL: Condenacao criminal transitada em julgado OU prisao efetiva OU desvio de recursos publicos > R$1M comprovado em decisao judicial OU envolvimento com crime organizado comprovado OU trafego de influencia comprovado em decisao judicial.
Palavras-chave: "condenado a X anos", "preso na operacao", "desvio de R$ X milhoes comprovado", "organizacao criminosa".

HIGH: Denuncia formal ACEITA pelo judiciario OU inquerito policial instaurado OU quebra de sigilo bancario/fiscal por decisao judicial OU afastamento do cargo por decisao judicial OU desvio < R$1M.
Palavras-chave: "MPF denuncia", "STF aceita denuncia", "inquerito instaurado", "sigilo quebrado", "afastado pelo TRE".

MEDIUM: Irregularidade administrativa documentada por orgao oficial (TCU, CGU, MP) OU nepotismo documentado OU conflito de interesse documentado OU multa aplicada por tribunal.
Palavras-chave: "TCU aponta irregularidades", "nomeou parente", "multado pelo TSE", "CGU identificou".

LOW: Votacao polemica OU declaracao controversa OU processo administrativo OU acusacoes sem fundamento documental OU investigacao preliminar sem formalizacao.
Palavras-chave: "votou contra", "declaracao gera criticas", "processo administrativo", "investigado informalmente".

REGRA DE OURO: Na duvida entre dois niveis, escolha o MENOR. Nao infle severidade.

═══════════════════════════════════════
SINAIS DE VERACIDADE (0.0 a 1.0)
═══════════════════════════════════════

narrative_consistency (0.0 = incoerente, 1.0 = perfeitamente coerente):
- 0.9-1.0: Narrativa linear, sem contradicoes, datas consistentes, fontes nomeadas
- 0.6-0.8: Narrativa coerente mas com lacunas ou fontes anonimas
- 0.3-0.5: Alguma incoerencia ou contradicao parcial
- 0.0-0.2: Narrativa confusa, contradicoes graves, cronologia impossivel

documental_evidence (0.0 = nenhuma evidencia, 1.0 = amplamente documentado):
- 0.9-1.0: Cita numeros de processo, leis, decisoes judiciais com datas
- 0.6-0.8: Cita documentos oficiais sem numeracao especifica
- 0.3-0.5: Menciona documentos de forma generica ("segundo documentos")
- 0.0-0.2: Nenhuma referencia documental, baseado em declaracoes verbais apenas

emotional_language (0.0 = neutro/factual, 1.0 = altamente emocional):
- 0.0-0.2: Linguagem jornalistica neutra, sem adjetivos de valor
- 0.3-0.5: Alguns adjetivos opinativos misturados com fatos
- 0.6-0.8: Linguagem carregada, palavras como "absurdo", "vergonha", "descarado"
- 0.9-1.0: Texto panfletario, mais opiniao que fato

NOTA: emotional_language e INVERTIDO na formula de veracidade (1.0 - score). Quanto MAIS emocional, MENOS confiavel.

═══════════════════════════════════════
TIPOS DE ENTIDADE
═══════════════════════════════════════

company: Empresa privada (construtoras, bancos, mineradoras, etc.)
organization: Organizacao nao-governamental generica
lobby: Grupo de pressao ou associacao de classe (FIESP, CNA, etc.)
ngo: ONG com atuacao social, ambiental ou politica
government_body: Orgao publico (PF, MPF, STF, TCU, CGU, Receita Federal, etc.)
court: Tribunal especifico (STF, TRF-1, TRE-SP, TSE, etc.)

NAO inclua partidos politicos como entidades — partidos sao tratados em tabela separada.

═══════════════════════════════════════
TIPOS DE MILESTONE
═══════════════════════════════════════

inquiry: Abertura de inquerito policial ou parlamentar
complaint: Denuncia formal oferecida pelo MP
conviction: Condenacao judicial (qualquer instancia)
acquittal: Absolvicao ou arquivamento de processo
arrest: Prisao efetiva (preventiva, temporaria ou definitiva)
impeachment: Cassacao de mandato ou processo de impeachment
plea_deal: Delacao premiada ou acordo de colaboracao
fine: Multa ou penalidade financeira aplicada por tribunal

═══════════════════════════════════════
TIPOS DE RELACAO
═══════════════════════════════════════

business: Relacao comercial, contrato, licitacao, doacao de campanha
political: Alianca politica, coligacao, apoio publico, indicacao para cargo
family: Parentesco (conjuge, filho, irmao, cunhado, etc.)
legal: Relacao processual (correu, delatou, testemunhou contra)
financial: Transferencia financeira, emprestimo, pagamento, propina

═══════════════════════════════════════
FORMATO DE SAIDA
═══════════════════════════════════════

Retorne EXCLUSIVAMENTE o JSON no schema especificado. Sem texto antes ou depois do JSON. Sem comentarios. Sem markdown. Apenas o JSON puro.
```

---

## 2. User Prompt Template

```
Analise o artigo abaixo e extraia as informacoes estruturadas conforme o schema JSON especificado.

METADADOS DA FONTE:
- Nome da fonte: {source_name}
- Dominio: {source_domain}
- Reputacao da fonte: {source_reputation}/1.0
- URL original: {original_url}
- Data de coleta: {collected_at}

INSTRUCOES CONTEXTUAIS:
- Se o artigo tiver menos de 100 palavras, retorne confidence geral <= 0.3 e arrays de politicians/entities/milestones/relationships vazios se nao houver informacao clara.
- Se o artigo estiver truncado (termina abruptamente ou menciona paywall), indique no reasoning de narrative_consistency e reduza o confidence geral proporcionalmente.
- Se o artigo nao trata de politica brasileira, retorne category "other", severity "low", e arrays vazios.

--- INICIO DO ARTIGO ---
{raw_content}
--- FIM DO ARTIGO ---
```

**Variaveis do template:**

| Variavel | Tipo | Origem | Exemplo |
|----------|------|--------|---------|
| `{source_name}` | string | `sources.name` | "Folha de S.Paulo" |
| `{source_domain}` | string | `sources.domain` | "folha.uol.com.br" |
| `{source_reputation}` | float | `sources.reputation` | "0.90" |
| `{original_url}` | string | `articles.original_url` | "https://folha.uol.com.br/..." |
| `{collected_at}` | ISO datetime | momento da coleta | "2026-09-06T14:30:00Z" |
| `{raw_content}` | string | Firecrawl output (markdown) | conteudo do artigo |

---

## 3. JSON Schema (response_format)

Este schema deve ser passado no parametro `response_format` da API OpenAI com `type: "json_schema"`.

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "article_processing_v1",
    "strict": true,
    "schema": {
      "type": "object",
      "properties": {
        "article": {
          "type": "object",
          "properties": {
            "title_normalized": {
              "type": "string",
              "description": "Titulo limpo do artigo, sem clickbait, max 200 caracteres"
            },
            "summary": {
              "type": "string",
              "description": "Resumo factual em 2-3 frases, max 500 caracteres. Sem opiniao, sem adjetivos de valor."
            },
            "published_at": {
              "type": ["string", "null"],
              "description": "Data de publicacao no formato YYYY-MM-DD. null se nao encontrada no texto."
            },
            "language": {
              "type": "string",
              "enum": ["pt-BR", "pt", "es", "en"],
              "description": "Idioma detectado do artigo"
            },
            "category": {
              "type": "string",
              "enum": ["corruption", "investigation", "trial", "legislation", "scandal", "misconduct", "acquittal", "other"],
              "description": "Categoria principal do artigo"
            }
          },
          "required": ["title_normalized", "summary", "published_at", "language", "category"],
          "additionalProperties": false
        },
        "veracity_signals": {
          "type": "object",
          "properties": {
            "narrative_consistency": {
              "type": "object",
              "properties": {
                "score": {
                  "type": "number",
                  "description": "0.0 (incoerente) a 1.0 (perfeitamente coerente)"
                },
                "reasoning": {
                  "type": "string",
                  "description": "1 frase justificando o score"
                }
              },
              "required": ["score", "reasoning"],
              "additionalProperties": false
            },
            "documental_evidence": {
              "type": "object",
              "properties": {
                "score": {
                  "type": "number",
                  "description": "0.0 (nenhuma evidencia) a 1.0 (amplamente documentado)"
                },
                "evidence_types": {
                  "type": "array",
                  "items": {
                    "type": "string",
                    "enum": ["document_number", "law_reference", "court_ruling", "official_statement", "financial_record", "none"]
                  },
                  "description": "Tipos de evidencia documental encontrados no texto"
                },
                "reasoning": {
                  "type": "string",
                  "description": "1 frase justificando o score"
                }
              },
              "required": ["score", "evidence_types", "reasoning"],
              "additionalProperties": false
            },
            "emotional_language": {
              "type": "object",
              "properties": {
                "score": {
                  "type": "number",
                  "description": "0.0 (neutro/factual) a 1.0 (altamente emocional)"
                },
                "reasoning": {
                  "type": "string",
                  "description": "1 frase justificando o score"
                }
              },
              "required": ["score", "reasoning"],
              "additionalProperties": false
            }
          },
          "required": ["narrative_consistency", "documental_evidence", "emotional_language"],
          "additionalProperties": false
        },
        "severity": {
          "type": "object",
          "properties": {
            "level": {
              "type": "string",
              "enum": ["critical", "high", "medium", "low"],
              "description": "Nivel de severidade baseado SOMENTE no conteudo deste artigo"
            },
            "reasoning": {
              "type": "string",
              "description": "1 frase justificando a classificacao"
            }
          },
          "required": ["level", "reasoning"],
          "additionalProperties": false
        },
        "politicians": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "name": {
                "type": "string",
                "description": "Nome completo como aparece no texto do artigo"
              },
              "role_in_article": {
                "type": "string",
                "enum": ["subject", "mentioned", "related"],
                "description": "subject = protagonista da noticia, mentioned = citado mas nao e o foco, related = tangencial"
              },
              "current_role": {
                "type": ["string", "null"],
                "description": "Cargo atual se mencionado no texto. null se nao mencionado."
              },
              "party": {
                "type": ["string", "null"],
                "description": "Sigla do partido se mencionada no texto. null se nao mencionada."
              },
              "state": {
                "type": ["string", "null"],
                "description": "UF (2 letras) se mencionada no texto. null se nao mencionada."
              },
              "context": {
                "type": "string",
                "description": "1 frase descrevendo o que o artigo diz sobre este politico"
              }
            },
            "required": ["name", "role_in_article", "current_role", "party", "state", "context"],
            "additionalProperties": false
          },
          "description": "Politicos explicitamente citados no texto. Lista vazia se nenhum."
        },
        "entities": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "name": {
                "type": "string",
                "description": "Nome da entidade como aparece no texto"
              },
              "entity_type": {
                "type": "string",
                "enum": ["company", "organization", "lobby", "ngo", "government_body", "court"],
                "description": "Tipo da entidade"
              },
              "role_in_article": {
                "type": "string",
                "description": "1 frase descrevendo o papel da entidade no contexto do artigo"
              }
            },
            "required": ["name", "entity_type", "role_in_article"],
            "additionalProperties": false
          },
          "description": "Entidades nao-politicas mencionadas. NAO incluir partidos politicos."
        },
        "relationships": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "source_name": {
                "type": "string",
                "description": "Nome do politico ou entidade de origem"
              },
              "source_type": {
                "type": "string",
                "enum": ["politician", "entity"],
                "description": "Tipo da origem"
              },
              "target_name": {
                "type": "string",
                "description": "Nome do alvo da relacao"
              },
              "target_type": {
                "type": "string",
                "enum": ["politician", "entity", "party"],
                "description": "Tipo do alvo"
              },
              "relationship_type": {
                "type": "string",
                "enum": ["business", "political", "family", "legal", "financial"],
                "description": "Tipo da relacao"
              },
              "description": {
                "type": "string",
                "description": "1 frase descrevendo a relacao conforme explicitada no texto"
              }
            },
            "required": ["source_name", "source_type", "target_name", "target_type", "relationship_type", "description"],
            "additionalProperties": false
          },
          "description": "Relacoes EXPLICITAMENTE descritas no texto. Coocorrencia NAO e relacao."
        },
        "milestones": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "title": {
                "type": "string",
                "description": "Titulo do evento, max 100 caracteres"
              },
              "milestone_type": {
                "type": "string",
                "enum": ["inquiry", "complaint", "conviction", "acquittal", "arrest", "impeachment", "plea_deal", "fine"],
                "description": "Tipo do evento juridico/politico"
              },
              "occurred_at": {
                "type": "string",
                "description": "Data do evento no formato YYYY-MM-DD. Se nao explicita, usar data de publicacao."
              },
              "description": {
                "type": "string",
                "description": "1-2 frases descrevendo o evento"
              },
              "politician_name": {
                "type": "string",
                "description": "Nome do politico associado ao milestone"
              }
            },
            "required": ["title", "milestone_type", "occurred_at", "description", "politician_name"],
            "additionalProperties": false
          },
          "description": "Eventos juridicos/politicos EXPLICITAMENTE descritos com evidencia. Lista vazia se nenhum."
        },
        "keywords": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "description": "Max 10 palavras-chave extraidas do vocabulario do artigo"
        },
        "extraction_confidence": {
          "type": "object",
          "properties": {
            "politicians_confidence": {
              "type": "number",
              "description": "0.0-1.0: confianca na extracao de politicos"
            },
            "entities_confidence": {
              "type": "number",
              "description": "0.0-1.0: confianca na extracao de entidades"
            },
            "milestones_confidence": {
              "type": "number",
              "description": "0.0-1.0: confianca na extracao de milestones"
            },
            "overall_confidence": {
              "type": "number",
              "description": "0.0-1.0: confianca geral da extracao"
            }
          },
          "required": ["politicians_confidence", "entities_confidence", "milestones_confidence", "overall_confidence"],
          "additionalProperties": false
        }
      },
      "required": ["article", "veracity_signals", "severity", "politicians", "entities", "relationships", "milestones", "keywords", "extraction_confidence"],
      "additionalProperties": false
    }
  }
}
```

---

## 4. Few-Shot Examples

### 4.1. Artigo Completo com Multiplas Entidades (HIGH confidence)

**Input (user prompt):**

```
Analise o artigo abaixo e extraia as informacoes estruturadas conforme o schema JSON especificado.

METADADOS DA FONTE:
- Nome da fonte: Folha de S.Paulo
- Dominio: folha.uol.com.br
- Reputacao da fonte: 0.90/1.0
- URL original: https://folha.uol.com.br/poder/2026/07/pf-indicia-deputado-carlos-mendes-por-desvio-de-emendas.shtml
- Data de coleta: 2026-07-20T10:00:00Z

INSTRUCOES CONTEXTUAIS:
- Se o artigo tiver menos de 100 palavras, retorne confidence geral <= 0.3 e arrays de politicians/entities/milestones/relationships vazios se nao houver informacao clara.
- Se o artigo estiver truncado (termina abruptamente ou menciona paywall), indique no reasoning de narrative_consistency e reduza o confidence geral proporcionalmente.
- Se o artigo nao trata de politica brasileira, retorne category "other", severity "low", e arrays vazios.

--- INICIO DO ARTIGO ---
PF indicia deputado Carlos Mendes por desvio de R$ 8 milhoes em emendas parlamentares

A Policia Federal indiciou nesta quarta-feira (17) o deputado federal Carlos Mendes (PP-GO) por peculato e lavagem de dinheiro. Segundo o inquerito IPL 1234/2026, o parlamentar teria desviado R$ 8 milhoes em emendas parlamentares entre 2023 e 2025, direcionando recursos para a construtora Alfa Engenharia, de propriedade de seu cunhado Roberto Alves.

O Ministerio Publico Federal informou que vai analisar o indiciamento para decidir sobre o oferecimento de denuncia. A defesa do deputado disse que ele e inocente e que os recursos foram aplicados corretamente.

A senadora Lucia Ferreira (MDB-GO), presidente da Comissao de Fiscalizacao, declarou que vai convocar o deputado para prestar esclarecimentos. O Tribunal de Contas da Uniao ja havia apontado irregularidades na execucao das emendas em relatorio de 2025.
--- FIM DO ARTIGO ---
```

**Output esperado:**

```json
{
  "article": {
    "title_normalized": "PF indicia deputado Carlos Mendes por desvio de R$ 8 milhoes em emendas parlamentares",
    "summary": "A Policia Federal indiciou o deputado federal Carlos Mendes (PP-GO) por peculato e lavagem de dinheiro, por suposto desvio de R$ 8 milhoes em emendas parlamentares entre 2023 e 2025. Os recursos teriam sido direcionados a construtora de propriedade de seu cunhado.",
    "published_at": "2026-07-17",
    "language": "pt-BR",
    "category": "investigation"
  },
  "veracity_signals": {
    "narrative_consistency": {
      "score": 0.90,
      "reasoning": "Narrativa linear com datas, valores e fontes oficiais consistentes ao longo do texto."
    },
    "documental_evidence": {
      "score": 0.85,
      "evidence_types": ["document_number", "financial_record", "official_statement"],
      "reasoning": "Cita numero do inquerito IPL 1234/2026, valores financeiros especificos e declaracoes oficiais do MPF e defesa."
    },
    "emotional_language": {
      "score": 0.10,
      "reasoning": "Linguagem predominantemente factual e neutra, tipica de reportagem investigativa."
    }
  },
  "severity": {
    "level": "high",
    "reasoning": "Indiciamento formal pela PF com inquerito instaurado, envolvendo desvio de R$ 8 milhoes, mas sem denuncia aceita pelo judiciario ainda."
  },
  "politicians": [
    {
      "name": "Carlos Mendes",
      "role_in_article": "subject",
      "current_role": "Deputado Federal",
      "party": "PP",
      "state": "GO",
      "context": "Indiciado pela PF por peculato e lavagem de dinheiro por suposto desvio de R$ 8 milhoes em emendas parlamentares."
    },
    {
      "name": "Lucia Ferreira",
      "role_in_article": "mentioned",
      "current_role": "Senadora",
      "party": "MDB",
      "state": "GO",
      "context": "Presidente da Comissao de Fiscalizacao, declarou que vai convocar o deputado para esclarecimentos."
    }
  ],
  "entities": [
    {
      "name": "Alfa Engenharia",
      "entity_type": "company",
      "role_in_article": "Construtora de propriedade do cunhado do deputado que teria recebido os recursos desviados."
    },
    {
      "name": "Policia Federal",
      "entity_type": "government_body",
      "role_in_article": "Orgao que conduziu o inquerito e realizou o indiciamento do deputado."
    },
    {
      "name": "Ministerio Publico Federal",
      "entity_type": "government_body",
      "role_in_article": "Vai analisar o indiciamento para decidir sobre oferecimento de denuncia."
    },
    {
      "name": "Tribunal de Contas da Uniao",
      "entity_type": "government_body",
      "role_in_article": "Havia apontado irregularidades na execucao das emendas em relatorio de 2025."
    }
  ],
  "relationships": [
    {
      "source_name": "Carlos Mendes",
      "source_type": "politician",
      "target_name": "Alfa Engenharia",
      "target_type": "entity",
      "relationship_type": "financial",
      "description": "Deputado teria direcionado R$ 8 milhoes em emendas para a Alfa Engenharia, empresa de seu cunhado."
    },
    {
      "source_name": "Carlos Mendes",
      "source_type": "politician",
      "target_name": "Roberto Alves",
      "target_type": "politician",
      "relationship_type": "family",
      "description": "Roberto Alves e cunhado do deputado Carlos Mendes e proprietario da Alfa Engenharia."
    }
  ],
  "milestones": [
    {
      "title": "Indiciamento pela PF por desvio de emendas",
      "milestone_type": "inquiry",
      "occurred_at": "2026-07-17",
      "description": "PF indiciou Carlos Mendes no inquerito IPL 1234/2026 por peculato e lavagem de dinheiro envolvendo R$ 8 milhoes em emendas parlamentares.",
      "politician_name": "Carlos Mendes"
    }
  ],
  "keywords": ["emendas parlamentares", "indiciamento", "policia federal", "peculato", "lavagem de dinheiro", "construtora", "PP", "Goias"],
  "extraction_confidence": {
    "politicians_confidence": 0.95,
    "entities_confidence": 0.90,
    "milestones_confidence": 0.92,
    "overall_confidence": 0.92
  }
}
```

---

### 4.2. Artigo Ambiguo/Curto (LOW confidence)

**Input (user prompt):**

```
Analise o artigo abaixo e extraia as informacoes estruturadas conforme o schema JSON especificado.

METADADOS DA FONTE:
- Nome da fonte: Portal Noticias Regional
- Dominio: noticiasregional.com.br
- Reputacao da fonte: 0.45/1.0
- URL original: https://noticiasregional.com.br/politica/vereador-acusado
- Data de coleta: 2026-08-10T08:00:00Z

INSTRUCOES CONTEXTUAIS:
- Se o artigo tiver menos de 100 palavras, retorne confidence geral <= 0.3 e arrays de politicians/entities/milestones/relationships vazios se nao houver informacao clara.
- Se o artigo estiver truncado (termina abruptamente ou menciona paywall), indique no reasoning de narrative_consistency e reduza o confidence geral proporcionalmente.
- Se o artigo nao trata de politica brasileira, retorne category "other", severity "low", e arrays vazios.

--- INICIO DO ARTIGO ---
Vereador e acusado de irregularidades

Um vereador da cidade seria responsavel por supostas irregularidades na licitacao de obras publicas, segundo fontes que preferiram nao se identificar. A oposicao pede investigacao. Mais detalhes em breve.
--- FIM DO ARTIGO ---
```

**Output esperado:**

```json
{
  "article": {
    "title_normalized": "Vereador e acusado de irregularidades em licitacao",
    "summary": "Vereador nao identificado e acusado por fontes anonimas de irregularidades em licitacao de obras publicas. Oposicao pede investigacao.",
    "published_at": null,
    "language": "pt-BR",
    "category": "misconduct"
  },
  "veracity_signals": {
    "narrative_consistency": {
      "score": 0.30,
      "reasoning": "Texto muito curto, sem detalhes, sem datas, sem identificacao dos envolvidos. Indica que havera continuacao."
    },
    "documental_evidence": {
      "score": 0.05,
      "evidence_types": ["none"],
      "reasoning": "Nenhuma referencia a documentos, processos ou decisoes oficiais."
    },
    "emotional_language": {
      "score": 0.25,
      "reasoning": "Linguagem relativamente neutra mas generica, com uso de 'supostas' como unico qualificador."
    }
  },
  "severity": {
    "level": "low",
    "reasoning": "Acusacoes sem evidencia documental, fontes anonimas, sem formalizacao de processo ou investigacao."
  },
  "politicians": [],
  "entities": [],
  "relationships": [],
  "milestones": [],
  "keywords": ["vereador", "licitacao", "irregularidades", "obras publicas"],
  "extraction_confidence": {
    "politicians_confidence": 0.10,
    "entities_confidence": 0.10,
    "milestones_confidence": 0.05,
    "overall_confidence": 0.15
  }
}
```

**Por que arrays vazios:** O artigo nao nomeia o vereador, nao identifica a cidade, nao menciona nenhuma entidade especifica e nao descreve nenhum evento juridico formal. Extrair dados seria alucinacao.

---

### 4.3. Artigo Sem Relevancia Politica

**Input (user prompt):**

```
Analise o artigo abaixo e extraia as informacoes estruturadas conforme o schema JSON especificado.

METADADOS DA FONTE:
- Nome da fonte: G1
- Dominio: g1.globo.com
- Reputacao da fonte: 0.85/1.0
- URL original: https://g1.globo.com/economia/noticia/2026/08/selic-cai-para-10-porcento.ghtml
- Data de coleta: 2026-08-20T16:00:00Z

INSTRUCOES CONTEXTUAIS:
- Se o artigo tiver menos de 100 palavras, retorne confidence geral <= 0.3 e arrays de politicians/entities/milestones/relationships vazios se nao houver informacao clara.
- Se o artigo estiver truncado (termina abruptamente ou menciona paywall), indique no reasoning de narrative_consistency e reduza o confidence geral proporcionalmente.
- Se o artigo nao trata de politica brasileira, retorne category "other", severity "low", e arrays vazios.

--- INICIO DO ARTIGO ---
Copom reduz taxa Selic para 10% ao ano

O Comite de Politica Monetaria (Copom) do Banco Central decidiu nesta quarta-feira (18) reduzir a taxa basica de juros de 10,5% para 10% ao ano. A decisao foi unanime entre os nove membros do colegiado. Segundo o comunicado, a reducao reflete a melhora no cenario inflacionario e a consolidacao das expectativas de inflacao dentro da meta. Economistas ouvidos pela reportagem esperam mais um corte na proxima reuniao, em outubro.
--- FIM DO ARTIGO ---
```

**Output esperado:**

```json
{
  "article": {
    "title_normalized": "Copom reduz taxa Selic para 10% ao ano",
    "summary": "O Copom decidiu reduzir a taxa Selic de 10,5% para 10% ao ano em decisao unanime, refletindo melhora no cenario inflacionario. Economistas esperam novo corte em outubro.",
    "published_at": "2026-08-18",
    "language": "pt-BR",
    "category": "other"
  },
  "veracity_signals": {
    "narrative_consistency": {
      "score": 0.95,
      "reasoning": "Narrativa factual, coerente, com dados numericos precisos e fonte oficial citada."
    },
    "documental_evidence": {
      "score": 0.80,
      "evidence_types": ["official_statement"],
      "reasoning": "Cita comunicado oficial do Copom com decisao e justificativa."
    },
    "emotional_language": {
      "score": 0.05,
      "reasoning": "Linguagem estritamente tecnica e factual."
    }
  },
  "severity": {
    "level": "low",
    "reasoning": "Artigo sobre politica monetaria, sem envolvimento de politico especifico em irregularidade ou polemica."
  },
  "politicians": [],
  "entities": [
    {
      "name": "Banco Central",
      "entity_type": "government_body",
      "role_in_article": "Instituicao cujo Copom decidiu a reducao da taxa Selic."
    }
  ],
  "relationships": [],
  "milestones": [],
  "keywords": ["selic", "copom", "banco central", "juros", "politica monetaria", "inflacao"],
  "extraction_confidence": {
    "politicians_confidence": 0.95,
    "entities_confidence": 0.90,
    "milestones_confidence": 0.95,
    "overall_confidence": 0.92
  }
}
```

**Por que politicians vazio e confidence alto:** O modelo tem CERTEZA de que nao ha politicos neste artigo. Confidence alto em politicians significa "estou confiante de que extrair corretamente — e o correto aqui e lista vazia".

---

## 5. Edge Cases

Os seguintes edge cases devem ser tratados pelo prompt e/ou pela validacao pos-processamento:

### 5.1. Artigo em Outro Idioma

Se o artigo esta em espanhol (ex: cobertura de midia argentina sobre politico brasileiro), o modelo deve:
- Definir `language: "es"`
- Extrair normalmente em portugues (nomes, resumo, keywords)
- Se o artigo esta em ingles, `language: "en"`
- Se o artigo esta em idioma nao suportado, `language: "pt"` (fallback) + `overall_confidence <= 0.3`

### 5.2. Artigo sobre Politica sem Politico Especifico

Exemplo: "Congresso aprova nova lei de licitacoes". O modelo deve:
- `politicians: []` (nenhum politico nomeado)
- `entities: [{"name": "Congresso Nacional", "entity_type": "government_body", ...}]`
- `category: "legislation"`
- `severity: "low"` (sem envolvimento individual em irregularidade)
- `politicians_confidence: 0.85` (confiante de que nao ha politico, mas score um pouco menor por se tratar de contexto politico)

### 5.3. Artigo com Informacoes Contraditorias

Exemplo: "A defesa diz que o deputado nao recebeu dinheiro. O MP afirma que ha provas de pagamento de R$ 500 mil." O modelo deve:
- `narrative_consistency.score` reduzido (0.40-0.60)
- `narrative_consistency.reasoning` deve mencionar a contradicao
- `severity` baseada no que ha de mais grave com evidencia documental
- NAO resolver a contradicao — apenas reportar ambos os lados no summary

### 5.4. Paywall / Conteudo Truncado

Se o artigo termina com "Leia mais assinando..." ou corta abruptamente:
- `narrative_consistency.score` reduzido proporcionalmente
- `narrative_consistency.reasoning`: "Texto truncado por paywall, informacoes possivelmente incompletas."
- `overall_confidence` reduzido em pelo menos 0.20
- Extrair apenas o que esta disponivel — NAO completar

### 5.5. Artigo Longo com Multiplos Politicos (>5)

Para artigos que mencionam muitos politicos (ex: votacao em plenario):
- Listar todos os politicos mencionados
- `role_in_article`: usar "subject" apenas para quem e foco central, "mentioned" para os demais
- Keywords: priorizar termos do tema principal, nao listar nomes de politicos como keywords

### 5.6. Artigo Repetido / Nota de Agencia

Notas curtas de agencia (2-3 frases apenas) que repetem informacao de outro artigo:
- Extrair normalmente, mas com confidence proporcional ao conteudo
- Para textos < 100 palavras: `overall_confidence <= 0.3`

---

## 6. Codigo Python de Referencia

```python
"""
VotoLimpo - Article Extraction via GPT-4.1-mini
Codigo de referencia para chamada a API OpenAI com structured outputs.
"""

import json
import time
from datetime import datetime, date
from typing import Any

from openai import OpenAI


# --- Configuracao ---

MODEL = "gpt-4.1-mini"
MAX_RETRIES = 1
MAX_CONTENT_CHARS = 15_000  # Truncar artigos muito longos para controlar custos

# System prompt (conteudo completo da secao 1 deste documento)
SYSTEM_PROMPT = """..."""  # Copiar integralmente da secao 1

# JSON Schema (conteudo completo da secao 3 deste documento)
RESPONSE_FORMAT = { ... }  # Copiar integralmente da secao 3

# User prompt template
USER_PROMPT_TEMPLATE = """Analise o artigo abaixo e extraia as informacoes estruturadas conforme o schema JSON especificado.

METADADOS DA FONTE:
- Nome da fonte: {source_name}
- Dominio: {source_domain}
- Reputacao da fonte: {source_reputation}/1.0
- URL original: {original_url}
- Data de coleta: {collected_at}

INSTRUCOES CONTEXTUAIS:
- Se o artigo tiver menos de 100 palavras, retorne confidence geral <= 0.3 e arrays de politicians/entities/milestones/relationships vazios se nao houver informacao clara.
- Se o artigo estiver truncado (termina abruptamente ou menciona paywall), indique no reasoning de narrative_consistency e reduza o confidence geral proporcionalmente.
- Se o artigo nao trata de politica brasileira, retorne category "other", severity "low", e arrays vazios.

--- INICIO DO ARTIGO ---
{raw_content}
--- FIM DO ARTIGO ---"""


def build_user_prompt(
    source_name: str,
    source_domain: str,
    source_reputation: float,
    original_url: str,
    collected_at: str,
    raw_content: str,
) -> str:
    """Monta o user prompt com os metadados da fonte e o conteudo do artigo."""
    # Truncar conteudo se exceder limite
    if len(raw_content) > MAX_CONTENT_CHARS:
        raw_content = raw_content[:MAX_CONTENT_CHARS] + "\n\n[CONTEUDO TRUNCADO POR LIMITE DE TAMANHO]"

    return USER_PROMPT_TEMPLATE.format(
        source_name=source_name,
        source_domain=source_domain,
        source_reputation=source_reputation,
        original_url=original_url,
        collected_at=collected_at,
        raw_content=raw_content,
    )


def extract_article_data(
    client: OpenAI,
    source_name: str,
    source_domain: str,
    source_reputation: float,
    original_url: str,
    collected_at: str,
    raw_content: str,
) -> dict[str, Any]:
    """
    Envia artigo ao GPT-4.1-mini e retorna dados estruturados.

    Retorna:
        dict com campos:
        - "data": JSON parseado do modelo (ou None se falhou)
        - "usage": {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
        - "cost_usd": float estimado
        - "duration_ms": int
        - "retries": int
        - "error": str ou None
    """
    user_prompt = build_user_prompt(
        source_name=source_name,
        source_domain=source_domain,
        source_reputation=source_reputation,
        original_url=original_url,
        collected_at=collected_at,
        raw_content=raw_content,
    )

    last_error = None
    for attempt in range(1 + MAX_RETRIES):
        start = time.monotonic()
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=RESPONSE_FORMAT,
                temperature=0.1,  # Baixa temperatura para extracao factual
                max_tokens=4096,
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            usage = response.usage
            data = json.loads(response.choices[0].message.content)

            # Estimativa de custo GPT-4.1-mini (precos de set/2026)
            # Input: $0.40/1M tokens, Output: $1.60/1M tokens
            cost_usd = (usage.prompt_tokens * 0.40 / 1_000_000) + (
                usage.completion_tokens * 1.60 / 1_000_000
            )

            return {
                "data": data,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                },
                "cost_usd": round(cost_usd, 6),
                "duration_ms": duration_ms,
                "retries": attempt,
                "error": None,
            }

        except Exception as e:
            last_error = str(e)
            duration_ms = int((time.monotonic() - start) * 1000)
            if attempt < MAX_RETRIES:
                time.sleep(1)  # Backoff minimo antes de retry
                continue

    return {
        "data": None,
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "cost_usd": 0.0,
        "duration_ms": duration_ms,
        "retries": 1 + MAX_RETRIES,
        "error": last_error,
    }


def validate_extraction(output: dict, raw_content: str) -> dict:
    """
    Validacao anti-alucinacao pos-processamento.
    Implementa os 11 checks da spec.

    Retorna:
        {"is_valid": bool, "errors": list[str], "warnings": list[str]}
    """
    errors = []
    warnings = []
    raw_lower = raw_content.lower() if raw_content else ""

    # CHECK 1: Schema compliance (campos obrigatorios)
    required = [
        "article", "veracity_signals", "severity", "politicians",
        "entities", "relationships", "milestones", "keywords",
        "extraction_confidence",
    ]
    for field in required:
        if field not in output:
            errors.append(f"Campo obrigatorio ausente: {field}")

    # CHECK 2: Score ranges [0.0, 1.0]
    for signal in ["narrative_consistency", "documental_evidence", "emotional_language"]:
        score = output.get("veracity_signals", {}).get(signal, {}).get("score")
        if score is not None and not (0.0 <= score <= 1.0):
            errors.append(f"Score fora do range [0,1]: {signal}={score}")

    for conf_field in ["politicians_confidence", "entities_confidence",
                       "milestones_confidence", "overall_confidence"]:
        score = output.get("extraction_confidence", {}).get(conf_field)
        if score is not None and not (0.0 <= score <= 1.0):
            errors.append(f"Confidence fora do range [0,1]: {conf_field}={score}")

    # CHECK 3: Datas nao futuras
    today = date.today()
    pub_date = output.get("article", {}).get("published_at")
    if pub_date:
        try:
            if date.fromisoformat(pub_date) > today:
                errors.append(f"Data futura: published_at={pub_date}")
        except ValueError:
            errors.append(f"Data invalida: published_at={pub_date}")

    for ms in output.get("milestones", []):
        ms_date = ms.get("occurred_at")
        if ms_date:
            try:
                if date.fromisoformat(ms_date) > today:
                    errors.append(f"Milestone data futura: {ms_date}")
            except ValueError:
                errors.append(f"Milestone data invalida: {ms_date}")

    # CHECK 4: Nomes de politicos no texto
    for pol in output.get("politicians", []):
        name = pol.get("name", "")
        parts = name.split()
        if parts:
            last_name = parts[-1].lower()
            if len(last_name) > 3 and last_name not in raw_lower:
                warnings.append(f"Sobrenome '{last_name}' nao encontrado no texto (politico: {name})")

    # CHECK 5: Entidades no texto
    for ent in output.get("entities", []):
        name = ent.get("name", "")
        name_parts = name.split()
        found = any(part.lower() in raw_lower for part in name_parts if len(part) > 3)
        if not found and name:
            warnings.append(f"Entidade '{name}' nao encontrada no texto")

    # CHECK 6: Severity enum valido
    valid_severities = {"critical", "high", "medium", "low"}
    severity = output.get("severity", {}).get("level", "")
    if severity not in valid_severities:
        errors.append(f"Severity invalida: {severity}")

    # CHECK 7: Milestone types validos
    valid_ms_types = {"inquiry", "complaint", "conviction", "acquittal",
                      "arrest", "impeachment", "plea_deal", "fine"}
    for ms in output.get("milestones", []):
        if ms.get("milestone_type") not in valid_ms_types:
            errors.append(f"Milestone type invalido: {ms.get('milestone_type')}")

    # CHECK 8: Milestones sem politician_name
    for ms in output.get("milestones", []):
        if not ms.get("politician_name"):
            errors.append(f"Milestone sem politico: {ms.get('title')}")

    # CHECK 9: Titulo length
    title = output.get("article", {}).get("title_normalized", "")
    if len(title) > 200:
        errors.append(f"Titulo excede 200 chars: {len(title)}")
    if not title:
        errors.append("Titulo vazio")

    # CHECK 10: Summary length
    summary = output.get("article", {}).get("summary", "")
    if len(summary) > 500:
        errors.append(f"Summary excede 500 chars: {len(summary)}")

    # CHECK 11: Coerencia severidade vs conteudo
    has_milestone = len(output.get("milestones", [])) > 0
    if severity == "low" and has_milestone:
        warnings.append("Severity 'low' com milestones presentes — verificar coerencia")
    if severity == "critical":
        doc_score = output.get("veracity_signals", {}).get("documental_evidence", {}).get("score", 0)
        if doc_score < 0.5:
            warnings.append("Severity 'critical' com documental_evidence < 0.5 — verificar se ha evidencia suficiente")

    # Checks adicionais
    valid_categories = {"corruption", "investigation", "trial", "legislation",
                        "scandal", "misconduct", "acquittal", "other"}
    category = output.get("article", {}).get("category", "")
    if category not in valid_categories:
        errors.append(f"Category invalida: {category}")

    valid_roles = {"subject", "mentioned", "related"}
    for pol in output.get("politicians", []):
        if pol.get("role_in_article") not in valid_roles:
            errors.append(f"Role invalida: {pol.get('role_in_article')} (politico: {pol.get('name')})")

    keywords = output.get("keywords", [])
    if len(keywords) > 10:
        warnings.append(f"Keywords excede 10: {len(keywords)} — sera truncado")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


# --- Exemplo de uso ---

if __name__ == "__main__":
    client = OpenAI()  # Usa OPENAI_API_KEY do env

    result = extract_article_data(
        client=client,
        source_name="Folha de S.Paulo",
        source_domain="folha.uol.com.br",
        source_reputation=0.90,
        original_url="https://folha.uol.com.br/exemplo",
        collected_at=datetime.utcnow().isoformat() + "Z",
        raw_content="Conteudo do artigo aqui...",
    )

    if result["data"]:
        validation = validate_extraction(result["data"], "Conteudo do artigo aqui...")
        print(f"Valido: {validation['is_valid']}")
        print(f"Erros: {validation['errors']}")
        print(f"Warnings: {validation['warnings']}")
        print(f"Custo: ${result['cost_usd']:.6f}")
        print(f"Tokens: {result['usage']['total_tokens']}")
        print(f"Duracao: {result['duration_ms']}ms")
    else:
        print(f"Erro: {result['error']}")
```

---

## 7. Estimativa de Tokens

### 7.1. Composicao por Chamada

| Componente | Tokens Estimados | Observacao |
|-----------|-----------------|------------|
| System prompt | ~1.800 | Fixo — inclui todas as regras, ENUMs e criterios de severidade |
| User prompt (template + metadados) | ~120 | Fixo — variaveis preenchidas |
| Conteudo do artigo (raw_content) | ~1.000-3.000 | Variavel — media de 2.000 |
| **Total input** | **~3.000-5.000** | Media: ~3.900 |
| Output JSON | ~500-1.200 | Variavel — artigo com muitas entidades gera output maior |
| **Total output** | **~800** | Media estimada |

### 7.2. Custo por Chamada

Precos GPT-4.1-mini (referencia set/2026):
- Input: $0.40 / 1M tokens
- Output: $1.60 / 1M tokens

| Cenario | Input tokens | Output tokens | Custo |
|---------|-------------|---------------|-------|
| Artigo curto (< 500 palavras) | ~2.500 | ~500 | ~$0.0018 |
| Artigo medio (500-1500 palavras) | ~3.900 | ~800 | ~$0.0028 |
| Artigo longo (1500-3000 palavras) | ~5.500 | ~1.200 | ~$0.0041 |
| **Media ponderada** | **~3.900** | **~800** | **~$0.0028** |

### 7.3. Projecao Mensal

| Volume | Custo Estimado |
|--------|---------------|
| 1.000 artigos/mes | ~$2.80 |
| 5.000 artigos/mes | ~$14.00 |
| 10.000 artigos/mes | ~$28.00 |
| 50.000 artigos/mes | ~$140.00 |

**Nota:** Custo nao inclui retries (~3% dos artigos) nem geracao de bio/resumo IA (custo adicional marginal).

---

## 8. Notas de Design

### 8.1. Por que Structured Outputs em vez de prompt livre + parsing?

O `response_format: json_schema` com `strict: true` garante que o modelo SEMPRE retorna JSON valido conforme o schema, eliminando:
- Erros de parsing (JSON malformado)
- Campos faltantes
- Tipos incorretos (string onde deveria ser number)
- Valores fora do ENUM

Isso reduz a taxa de retry para praticamente zero em relacao ao formato, permitindo que a validacao foque em conteudo (anti-alucinacao).

### 8.2. Por que temperature 0.1?

Extracao factual requer consistencia e determinismo. Temperature 0.1 (nao zero, para evitar degeneration em modelos especificos) minimiza a variabilidade entre execucoes do mesmo artigo.

### 8.3. Por que o system prompt inclui criterios de severidade em vez de delegar ao pos-processamento?

O modelo precisa DECIDIR a severidade durante a extracao. Se delegamos ao pos-processamento, perdemos o reasoning do modelo (a justificativa de porque classificou daquela forma). Os criterios no prompt garantem calibracao consistente e o reasoning permite auditoria.

### 8.4. Por que few-shot examples no documento e nao no prompt?

Incluir 3 few-shot examples no prompt adicionaria ~3.000 tokens por chamada (custo +$0.0012/artigo, ~$12/mes extra em 10k artigos). Para GPT-4.1-mini com structured outputs, o schema + regras detalhadas ja sao suficientes para extracao precisa. Os examples servem como referencia para validacao humana e para fine-tuning futuro.

Se a taxa de erro em producao ultrapassar 5%, considerar adicionar 1 few-shot example (o caso 4.1) ao prompt como fallback.

### 8.5. Por que truncar artigos em 15.000 caracteres?

Artigos maiores que ~15.000 caracteres (equivalente a ~3.000-4.000 tokens) aumentam custo sem ganho proporcional de qualidade — a maioria das informacoes relevantes esta nos primeiros paragrafos. O truncamento adiciona a marcacao `[CONTEUDO TRUNCADO POR LIMITE DE TAMANHO]` para que o modelo ajuste o confidence.

### 8.6. Por que a regra R6 limita confidence > 0.8 para textos curtos?

Textos com menos de 300 palavras nao fornecem contexto suficiente para extracao confiavel. Sem esta regra, o modelo tende a retornar confidence alto em textos curtos simplesmente porque "nao encontrou problemas" — quando na verdade nao havia informacao suficiente para avaliar.

### 8.7. Relacao entre campos do JSON e colunas do banco

| Campo JSON | Tabela.coluna PostgreSQL | Transformacao |
|-----------|--------------------------|---------------|
| `article.title_normalized` | `articles.title` | Direto |
| `article.summary` | `articles.summary` | Direto |
| `article.published_at` | `articles.published_at` | ISO string -> TIMESTAMPTZ |
| `article.category` | `articles.category` | Direto |
| `veracity_signals.narrative_consistency.score` | `articles.narrative_consistency` | Direto |
| `veracity_signals.documental_evidence.score` | `articles.documental_evidence` | Direto |
| `veracity_signals.emotional_language.score` | `articles.emotional_language` | Direto |
| `severity.level` | `articles.severity` | Direto (ENUM) |
| `keywords` | `articles.keywords` | Direto (TEXT[]) |
| `politicians[].name` | Resolve contra `politicians.name` (pg_trgm) | Fuzzy match |
| `politicians[].role_in_article` | `politician_articles.role` | Direto (ENUM) |
| `entities[].name` | Resolve contra `entities.name` (pg_trgm) | Fuzzy match |
| `relationships[]` | `relationships` + `relationship_evidence` | Resolve IDs + upsert |
| `milestones[]` | `milestones` | Dedup (politico + tipo + data +-7 dias) |
| `extraction_confidence.overall_confidence` | `processing_logs.output_json` | Armazenado no log |

---

*Documento gerado por PROMPT-ENGINEER para o projeto VotoLimpo.*
*Referencia: `processing-pipeline.md` secoes 1, 8, 9 + `processing-spec.md` secoes 2-6.*
