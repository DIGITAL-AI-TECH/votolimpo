# Spec: Interface Frontend do Voto Limpo

**Feature**: Interface web publica para consulta de historico de polemicas e corrupcao de politicos brasileiros
**Branch**: `feature/1-votolimpo-frontend`
**Status**: Draft
**Created**: 2026-09-04

---

## Problem Statement

O eleitor brasileiro nao tem acesso facil e consolidado ao historico de polemicas e corrupcao de politicos que disputam as eleicoes presidenciais de 2026. As informacoes estao dispersas em centenas de portais de noticia. O cidadao precisa de uma interface unica, aberta e sem cadastro, que consolide essas informacoes com score de veracidade e grafos de relacionamento — permitindo votar com informacao real.

## User Personas

### P1 — Eleitor Consciente
Cidadao brasileiro (18-60 anos) que quer consultar rapidamente o historico negativo de um politico antes de votar. Acessa pelo celular, vindo de link compartilhado no WhatsApp ou busca no Google. Nao quer criar conta.

### P2 — Jornalista / Pesquisador
Profissional que precisa de dados estruturados, grafos de relacionamento entre politicos e links para fontes originais. Acessa pelo desktop, explora filtros avancados e exporta dados.

### P3 — Cidadao Casual
Recebeu um link no WhatsApp com o perfil de um politico. Abre, le o resumo, vê o score e sai. Tempo de visita: 30-90 segundos.

## Functional Requirements

### FR-01: Pagina Inicial (Home)

**R-01.1**: A pagina inicial exibe uma barra de busca centralizada em destaque (hero) onde o usuario digita o nome de um politico e recebe sugestoes em tempo real (autocomplete).

**R-01.2**: Abaixo da busca, a home exibe um ranking dos 10 politicos com maior volume de noticias negativas, atualizado diariamente, mostrando: foto, nome, partido, estado e score consolidado.

**R-01.3**: A home exibe cards de "casos recentes" — os 6 clusters de noticias mais recentes com maior repercussao, mostrando titulo do caso, politicos envolvidos e data.

**R-01.4**: A home exibe contadores globais: total de politicos catalogados, total de noticias processadas e total de fontes monitoradas.

### FR-02: Perfil do Politico

**R-02.1**: Cada politico tem uma pagina de perfil com URL amigavel (`/politico/{slug}`). O perfil exibe: foto oficial (TSE), nome completo, partido atual (com logo), cargo atual, estado, score consolidado de polemicas.

**R-02.2**: O perfil exibe uma timeline cronologica vertical com todas as noticias/clusters de noticias associados ao politico, ordenados do mais recente ao mais antigo. Cada item da timeline mostra: titulo, resumo gerado por IA (2-3 frases), score de veracidade (semaforo colorido), data, fonte(s) e link para noticia original.

**R-02.3**: O score de veracidade de cada noticia e exibido como badge colorido com icone e label:
- Verde (0.8-1.0): "Alta confiabilidade"
- Azul (0.6-0.8): "Confiavel"
- Amarelo (0.4-0.6): "Verificar fontes"
- Laranja (0.2-0.4): "Baixa confiabilidade"
- Vermelho (0.0-0.2): "Possivel desinformacao"

**R-02.4**: O perfil exibe um mini-grafo de relacionamentos mostrando as entidades mais conectadas ao politico (outros politicos, partidos, empresas). Clicar em um no do grafo navega para o perfil da entidade correspondente.

**R-02.5**: O perfil exibe uma secao de estatisticas: total de noticias, distribuicao por severidade (low/medium/high/critical), fontes mais frequentes, periodo coberto (primeira a ultima noticia).

**R-02.6**: O perfil possui botao de compartilhamento que gera link com Open Graph tags (titulo, descricao, imagem do politico) para preview rico no WhatsApp, Twitter, Facebook.

### FR-03: Pagina de Busca

**R-03.1**: A pagina de busca oferece busca full-text por nome de politico com resultados instantaneos (< 500ms).

**R-03.2**: A busca oferece filtros combinaveis: partido (dropdown multi-select), estado (dropdown com todos os UFs), cargo (presidente, governador, senador, deputado federal, deputado estadual), periodo (de-ate), severidade minima.

**R-03.3**: Os resultados da busca sao exibidos como cards com: foto, nome, partido, estado, cargo, score consolidado e numero de noticias. Cards sao clicaveis e levam ao perfil.

**R-03.4**: Os resultados suportam ordenacao por: relevancia (padrao), score (maior primeiro), numero de noticias (maior primeiro), nome (A-Z).

**R-03.5**: A busca suporta paginacao com scroll infinito em mobile e paginacao numerada em desktop.

### FR-04: Grafo de Relacionamentos Global

**R-04.1**: A pagina de grafo exibe uma visualizacao interativa force-directed de todas as entidades e seus relacionamentos. Nos coloridos por tipo: politicos (azul), partidos (vermelho), empresas (cinza), organizacoes (amarelo).

**R-04.2**: O tamanho de cada no e proporcional ao score de polemicas (politicos) ou ao numero de conexoes (demais entidades). A espessura de cada aresta e proporcional ao peso do relacionamento (numero de noticias compartilhadas).

**R-04.3**: Hover em um no exibe tooltip com nome, tipo e resumo. Click em um no abre painel lateral com detalhes + lista das noticias que fundamentam as conexoes daquele no.

**R-04.4**: O grafo suporta zoom, pan, e filtro por tipo de entidade e periodo temporal.

**R-04.5**: Para performance, o grafo limita a exibicao a 200 nos por vez. O usuario pode buscar e centralizar um politico especifico no grafo.

### FR-05: Pagina de Ranking

**R-05.1**: A pagina de ranking exibe uma tabela ordenavel de politicos com colunas: posicao, foto, nome, partido, estado, cargo, total de noticias negativas, score consolidado, severidade maxima.

**R-05.2**: O ranking suporta filtros: por partido, estado, cargo. E ordenacao por qualquer coluna.

**R-05.3**: O ranking exibe badges visuais para os top 3 (ouro, prata, bronze) e destaque para politicos com noticias de severidade "critical".

### FR-06: Navegacao e Layout

**R-06.1**: O layout utiliza um header fixo com: logo "Voto Limpo", barra de busca compacta, navegacao (Home, Busca, Grafo, Ranking) e badge com total de politicos catalogados.

**R-06.2**: O footer exibe: disclaimer legal ("Plataforma agrega noticias de fontes publicas. Nao produz conteudo editorial."), links para repositorio open source, creditos e metodologia de score.

**R-06.3**: O layout e responsivo mobile-first. Em mobile: navegacao via bottom bar com icones. Em desktop: sidebar ou top navigation.

**R-06.4**: A interface utiliza tema escuro como padrao, com paleta sobria e accent color verde (representando transparencia).

### FR-07: SEO e Compartilhamento

**R-07.1**: Cada pagina de politico e renderizada server-side (SSR) para indexacao pelo Google. Inclui meta tags, Schema.org (Person, Article), sitemap.xml automatico e robots.txt.

**R-07.2**: Cada pagina de politico inclui Open Graph tags (og:title, og:description, og:image) para preview rico ao compartilhar no WhatsApp, Twitter e Facebook.

**R-07.3**: URLs amigaveis para todos os politicos: `votolimpo.com.br/politico/jose-da-silva-pt-sp`.

## User Scenarios & Testing

### Scenario 1: Eleitor busca politico pelo nome
1. Usuario acessa votolimpo.com.br
2. Digita "Fulano" na barra de busca hero
3. Autocomplete sugere correspondencias apos 2 caracteres
4. Seleciona o politico desejado
5. E redirecionado para o perfil do politico com timeline de noticias
**Resultado esperado**: Perfil carrega em < 2s com timeline cronologica completa

### Scenario 2: Eleitor verifica score de veracidade
1. No perfil do politico, usuario ve timeline de noticias
2. Cada noticia exibe badge de veracidade colorido (verde a vermelho)
3. Usuario clica no link da fonte original
4. Link abre em nova aba o artigo no portal de noticias
**Resultado esperado**: Todos os links de fontes originais sao validos e abrem corretamente

### Scenario 3: Jornalista explora grafo de relacionamentos
1. Usuario acessa pagina /grafo
2. Ve visualizacao force-directed com nos e arestas
3. Busca "Politico X" e o grafo centraliza naquele no
4. Clica em aresta entre Politico X e Empresa Y
5. Painel lateral abre mostrando noticias que fundamentam a conexao
**Resultado esperado**: Grafo renderiza com interatividade completa em < 3s

### Scenario 4: Cidadao casual via WhatsApp
1. Usuario recebe link `votolimpo.com.br/politico/fulano-pt-sp` no WhatsApp
2. WhatsApp exibe preview rico: foto do politico, nome, score
3. Usuario abre o link no celular
4. Pagina carrega rapido, ve resumo do politico e timeline
5. Navega pela timeline scrollando verticalmente
**Resultado esperado**: Preview do WhatsApp exibe titulo + descricao + imagem. Pagina mobile carrega em < 2s

### Scenario 5: Eleitor compara politicos pelo ranking
1. Usuario acessa pagina /ranking
2. Filtra por estado "SP" e cargo "Deputado Federal"
3. Ordena por "score consolidado" decrescente
4. Ve tabela com top politicos de SP por volume de polemicas
5. Clica em um politico para ver perfil detalhado
**Resultado esperado**: Filtros combinam corretamente e ordenacao atualiza instantaneamente

### Scenario 6: Eleitor filtra por partido
1. Na pagina de busca, usuario seleciona partido "PT" no filtro
2. Resultados mostram apenas politicos do PT
3. Adiciona filtro de estado "MG"
4. Resultados refinam para PT + MG
5. Remove filtro de partido, mantendo apenas MG
**Resultado esperado**: Filtros sao combinaveis e removiveis independentemente

## Success Criteria

| ID | Criterio | Metrica |
|----|----------|---------|
| SC-01 | Usuarios encontram o politico desejado rapidamente | 90% das buscas retornam o resultado correto nos primeiros 3 itens |
| SC-02 | Paginas carregam rapido em dispositivos moveis | Largest Contentful Paint < 2 segundos em conexao 4G |
| SC-03 | Conteudo e indexado por mecanismos de busca | 100% das paginas de politicos indexadas pelo Google em 30 dias |
| SC-04 | Compartilhamento gera engajamento | Preview rico (titulo + imagem + descricao) visivel ao compartilhar no WhatsApp e redes sociais |
| SC-05 | Grafo de relacionamentos e compreensivel | Usuarios conseguem identificar conexoes entre politicos em < 30 segundos |
| SC-06 | Score de veracidade e claro para o usuario | 95% dos usuarios entendem o significado das cores/labels sem explicacao adicional |
| SC-07 | Interface acessivel sem cadastro | Zero barreiras de acesso — nenhuma funcionalidade requer login ou cadastro |
| SC-08 | Ranking permite comparacao rapida | Usuarios conseguem comparar 3+ politicos por score em < 15 segundos usando filtros e ordenacao |

## Key Entities

| Entidade | Descricao | Atributos principais |
|----------|-----------|----------------------|
| Politico | Candidato registrado no TSE | Nome, slug, foto, partido, estado, cargo, score |
| Partido | Partido politico registrado | Nome, sigla, logo |
| Noticia | Artigo de noticia coletado e processado | Titulo, resumo, fonte, data, score de veracidade, severidade |
| Cluster | Agrupamento de noticias sobre o mesmo caso | Titulo, resumo consolidado, contagem de artigos, severidade |
| Entidade (grafo) | No do grafo de relacionamentos | Nome, tipo (politico/partido/empresa/organizacao) |
| Relacionamento | Aresta do grafo | Tipo, peso, artigos de evidencia |

## Scope

### In-Scope
- Pagina inicial com busca hero, ranking top 10, casos recentes
- Perfil de politico com timeline, score de veracidade, mini-grafo
- Busca com filtros combinaveis (partido, estado, cargo, periodo)
- Grafo interativo global de relacionamentos
- Ranking ordenavel e filtravel
- SEO completo (SSR, meta tags, Schema.org, sitemap, Open Graph)
- Design responsivo mobile-first com tema escuro
- Compartilhamento com preview rico (WhatsApp, Twitter, Facebook)

### Out-of-Scope
- Backend/API (coberto em spec separada)
- Pipeline de coleta de noticias (Collector Service)
- Pipeline de processamento com IA (Processor Service)
- Login, cadastro ou qualquer forma de autenticacao
- API publica REST (v1.5)
- App mobile nativo
- Internacionalizacao (apenas portugues BR)
- Comparador side-by-side de politicos (v2.0)
- Alertas/notificacoes (v2.0)
- Admin panel ou moderacao de conteudo

## Assumptions

1. Os dados ja estarao disponiveis no banco de dados quando a interface for construida (pipeline de coleta e processamento roda antes)
2. Foto oficial dos politicos sera importada do repositorio do TSE e servida via CDN
3. O score de veracidade ja vem calculado do backend — a interface apenas exibe
4. O grafo de relacionamentos e pre-calculado no backend — a interface recebe os dados e renderiza
5. O trafego sera majoritariamente mobile (70%+), vindo de links compartilhados no WhatsApp
6. O design utiliza tema escuro por padrao sem opcao de tema claro no MVP
7. A busca fulltext e provida pelo backend — a interface envia a query e exibe resultados
8. O dominio votolimpo.com.br sera registrado e configurado antes do lancamento
9. Performance target: suportar ate 10.000 usuarios simultaneos sem degradacao perceptivel

## Dependencies

| Dependencia | Tipo | Impacto |
|-------------|------|---------|
| Dados de politicos importados do TSE | Dados | Sem dados, interface exibe estado vazio |
| Noticias coletadas e processadas | Dados | Timeline e grafo ficam vazios sem noticias |
| Score de veracidade calculado | Dados | Badges de score nao aparecem sem calculo |
| Grafo de relacionamentos pre-calculado | Dados | Pagina de grafo fica vazia |
| Dominio votolimpo.com.br registrado | Infra | SEO e compartilhamento dependem do dominio final |
| CDN para servir imagens (fotos de politicos) | Infra | Fotos podem nao carregar sem CDN |

## Design Direction

### Paleta de Cores (tema escuro)
- **Background principal**: #0A0A0A (preto profundo)
- **Background cards**: #1A1A2E (azul-escuro sutil)
- **Accent primario**: #10B981 (verde esmeralda — transparencia)
- **Accent secundario**: #3B82F6 (azul — confianca)
- **Texto primario**: #F1F5F9 (branco off-white)
- **Texto secundario**: #94A3B8 (cinza medio)
- **Danger/alerta**: #EF4444 (vermelho para corrupcao critica)
- **Warning**: #F59E0B (amarelo para alertas)

### Tipografia
- Headlines: Inter ou Outfit (sans-serif moderna, forte)
- Body: Inter (legibilidade em telas)
- Monospace: JetBrains Mono (para dados/numeros)

### Inspiracao Visual
- Gravidade e sobriedade de portais de fact-checking (Aos Fatos, Lupa)
- Visualizacao de dados de portais de transparencia (Transparencia Brasil, Serenata de Amor)
- Modernidade e acessibilidade de plataformas de dados abertos

### Componentes-Chave
- **Score Badge**: Circulo com gradiente de cor + icone + label
- **Timeline Card**: Card escuro com borda lateral colorida por severidade
- **Politician Card**: Foto circular + nome + partido badge + score
- **Graph Node**: Circulo com foto/icone, tamanho proporcional ao score
- **Ranking Row**: Linha com foto miniatura, badges de posicao, barras de progresso para score

## Wireframes (descricao textual)

### Home
```
[HEADER: Logo "Voto Limpo" | Busca compacta | Nav: Home Busca Grafo Ranking]

[HERO SECTION]
  "Saiba quem voce esta votando"
  [====== Barra de busca grande com autocomplete ======]
  [Contadores: 5.847 politicos | 523.412 noticias | 47 fontes]

[RANKING TOP 10]
  Cards horizontais scrollaveis com foto+nome+partido+score

[CASOS RECENTES]
  Grid 2x3 de cards com titulo do caso + politicos envolvidos + data

[FOOTER: Disclaimer | GitHub | Metodologia | Creditos]
```

### Perfil do Politico
```
[HEADER]

[HERO DO POLITICO]
  Foto grande | Nome | Partido (badge) | Cargo | Estado
  Score consolidado (circulo grande com numero)
  [Botao: Compartilhar]

[ESTATISTICAS]
  Cards: Total noticias | Severidade critica | Fontes | Periodo

[TABS: Timeline | Grafo | Detalhes]

[TIMELINE] (tab ativa por padrao)
  |--- 2026-08-15 ---
  |  [Card] Titulo da noticia
  |         Resumo por IA (2-3 frases)
  |         [Badge verde: Alta confiabilidade]
  |         Fonte: G1 | [Link externo]
  |
  |--- 2026-07-22 ---
  |  [Card] Titulo de outra noticia
  |         Resumo...
  |         [Badge amarelo: Verificar fontes]
  |         Fontes: Folha, Estadao | [Links]

[GRAFO] (tab)
  Mini-grafo force-directed com nos conectados ao politico

[FOOTER]
```

### Busca
```
[HEADER]

[FILTROS]
  Partido: [Multi-select]  Estado: [Dropdown]  Cargo: [Dropdown]
  Periodo: [De] [Ate]  Severidade: [Dropdown]

[RESULTADOS]
  Grid de Politician Cards (3 colunas desktop, 1 mobile)
  Cada card: Foto | Nome | Partido | Estado | Score | N noticias

[PAGINACAO / Scroll infinito mobile]
```
