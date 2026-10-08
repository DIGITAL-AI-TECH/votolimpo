# Feature Specification: Help Core Platform

**Feature Branch**: `001-helpcore-platform`
**Created**: 2026-10-08
**Status**: Draft
**Input**: Interface visual para acompanhamento do processamento de 108K artigos do Help Bradesco

## User Scenarios & Testing *(mandatory)*

### User Story 1 - ETL de Ingestao de Artigos (Priority: P1)

Como engenheiro da Digital AI, quero rodar um script que leia os arquivos .txt exportados do SharePoint e insira na tabela `help_core.articles`, para popular a base de dados antes de iniciar o processamento e permitir que a plataforma exiba conteudo.

**Why this priority**: Sem os artigos no banco, nenhum dos outros modulos funciona. O ETL e o alicerce de tudo — popula a tabela `articles` que alimenta o Help Browser, o Dashboard e o Visualizador.

**Independent Test**: Pode ser testado executando o script contra um diretorio de 100 .txt de amostra e verificando que os registros foram inseridos corretamente no banco com todos os campos preenchidos.

**Acceptance Scenarios**:

1. **Given** um diretorio com arquivos .txt do Help Bradesco, **When** o ETL e executado, **Then** cada arquivo e parseado (header: area, titulo, iid, modified_date) e inserido na tabela `help_core.articles` com `source_url` no formato `bradesco-help://<AREA>/<IID>`.
2. **Given** arquivos duplicados (mesmo conteudo, nomes diferentes), **When** o ETL encontra `content_hash` duplicado, **Then** o artigo duplicado e ignorado e contabilizado no relatorio final.
3. **Given** um batch de 108K arquivos, **When** o ETL e executado, **Then** insere em batches de 500 com barra de progresso no terminal e gera relatorio final (total inserido, duplicatas ignoradas, erros).
4. **Given** um arquivo .txt com header malformado ou vazio, **When** o ETL tenta parsear, **Then** o arquivo e logado como erro e o processamento continua com os demais.

---

### User Story 2 - Dashboard de Progresso (Priority: P1)

Como gestor de projeto da Ello, quero ver um painel com o progresso do processamento dos artigos em tempo real, para saber quantos ja foram processados, quanto custou e quanto tempo falta.

**Why this priority**: O Dashboard e o principal entregavel para o cliente — da visibilidade imediata sobre o processamento sem precisar de SQL. Junto com o ETL, forma o MVP minimo viavel.

**Independent Test**: Pode ser testado acessando a pagina /dashboard e verificando que as metricas refletem o estado real do banco (contagens, custos, status).

**Acceptance Scenarios**:

1. **Given** artigos no banco com diferentes status de processamento, **When** o usuario acessa /dashboard, **Then** ve barra de progresso geral (processados / total) com porcentagem.
2. **Given** artigos processados com custo registrado, **When** o usuario ve o dashboard, **Then** o custo acumulado em USD e exibido com breakdown por status (pending, processing, processed, error).
3. **Given** artigos distribuidos em 26 areas operacionais, **When** o dashboard carrega, **Then** mostra progresso por area operacional em grafico de barras empilhadas ou treemap.
4. **Given** processamento em andamento, **When** o dashboard e visualizado, **Then** exibe estimativa de tempo restante baseada na velocidade media de processamento.
5. **Given** o dashboard aberto, **When** 30 segundos passam, **Then** os dados sao atualizados automaticamente sem recarregar a pagina.

---

### User Story 3 - Help Browser: Navegar e Ler Artigos (Priority: P1)

Como gestor de conteudo da Ello, quero navegar os artigos organizados por area operacional e ler o conteudo original de cada um, para entender a distribuicao e validar o conteudo exportado.

**Why this priority**: Permite ao cliente ver o que tem na base, entender a distribuicao por area, e ler artigos individuais. E a interface basica de navegacao da plataforma.

**Independent Test**: Pode ser testado acessando /browse, clicando numa area, vendo a lista de artigos, e abrindo um artigo individual para leitura.

**Acceptance Scenarios**:

1. **Given** artigos inseridos no banco pelo ETL, **When** o usuario acessa /browse, **Then** ve sidebar com as 26 areas operacionais e contagem de artigos por area.
2. **Given** o usuario clica numa area, **When** a lista carrega, **Then** mostra artigos daquela area com titulo, subcategoria e data de modificacao, paginados (50 por pagina).
3. **Given** o usuario clica num artigo, **When** a pagina de detalhe carrega, **Then** exibe titulo, area, subcategoria, data de modificacao, classificacao (TEXTUAL/LINK_ONLY/SHORT_TEXT) e conteudo original formatado.

---

### User Story 4 - Autenticacao Basica (Priority: P1)

Como gestor da Ello, quero que a plataforma exija autenticacao para acessar, para impedir que pessoas nao autorizadas vejam a base de conhecimento do Bradesco.

**Why this priority**: Requerimento de seguranca basico — a base de conhecimento do Bradesco nao pode ser publica. Sem auth, a plataforma nao pode ser publicada.

**Independent Test**: Pode ser testado tentando acessar qualquer pagina sem estar logado e verificando o redirect para /login.

**Acceptance Scenarios**:

1. **Given** um usuario nao autenticado, **When** acessa qualquer pagina da plataforma, **Then** e redirecionado para /login.
2. **Given** o usuario na tela de login, **When** insere a senha correta, **Then** e autenticado e redirecionado para /dashboard com cookie de sessao (expiracao 7 dias).
3. **Given** o usuario na tela de login, **When** insere senha incorreta, **Then** ve mensagem de erro sem revelar detalhes tecnicos.
4. **Given** o usuario autenticado, **When** clica em Logout, **Then** o cookie e removido e e redirecionado para /login.
5. **Given** um cookie de sessao expirado (>7 dias), **When** o usuario tenta acessar uma pagina, **Then** e redirecionado para /login.

---

### User Story 5 - Visualizador de Resultados Processados (Priority: P2)

Como gestor de conteudo, quero acessar os 33 campos extraidos pelo LLM para cada artigo processado, para validar se a classificacao, os scores e os passos estao corretos.

**Why this priority**: Complementa o Help Browser com os dados do processamento. E essencial para validacao mas depende de artigos ja processados (Sprint 2).

**Independent Test**: Pode ser testado acessando o detalhe de um artigo processado e verificando que todos os campos do LLM sao exibidos corretamente.

**Acceptance Scenarios**:

1. **Given** um artigo com processing_output completo, **When** o usuario acessa a pagina de detalhe, **Then** ve secao "Inventario" com doc_type, category, subcategory, target_audience, key_topics, area_operacional.
2. **Given** um artigo processado, **When** o usuario ve a secao Qualidade, **Then** ve radar chart com os 5 scores (clarity, structure, completeness, accuracy_signals, readability) + overall_score numerico + badge de priority_level colorido.
3. **Given** um artigo com steps extraidos, **When** o usuario ve a secao Passos, **Then** ve os steps em formato de checklist visual ordenada.
4. **Given** um artigo processado, **When** o usuario ve a secao Sugestoes, **Then** ve improvement_suggestions e actionable_items listados.

---

### User Story 6 - Diff Visual (Antes vs Depois) (Priority: P2)

Como gestor de conteudo, quero ver lado a lado o conteudo original e a versao processada/reescrita pelo LLM, para entender exatamente o que mudou e decidir se aprovo.

**Why this priority**: Funcionalidade de alto valor para validacao humana, mas depende de artigos processados com markdown_content gerado.

**Independent Test**: Pode ser testado acessando /articles/[id]/diff e verificando que as diferencas entre original e processado sao destacadas visualmente.

**Acceptance Scenarios**:

1. **Given** um artigo com conteudo original e markdown processado, **When** o usuario acessa o diff, **Then** ve layout side-by-side (original a esquerda, processado a direita) com diferencas destacadas em cores.
2. **Given** o diff exibido, **When** o usuario clica em "Inline", **Then** alterna para modo diff inline (uma coluna com adicionado/removido).
3. **Given** o diff exibido, **When** o usuario ve as metricas, **Then** mostra word_count original vs reescrito e delta percentual.

---

### User Story 7 - Busca Full-Text e Filtros (Priority: P2)

Como gestor de conteudo, quero buscar artigos por palavra-chave e filtrar por qualidade, area e categoria, para encontrar e priorizar artigos especificos.

**Why this priority**: Essencial para navegacao eficiente em 108K artigos mas nao bloqueia o MVP.

**Independent Test**: Pode ser testado buscando uma palavra-chave e verificando que os resultados sao relevantes com highlight nos trechos.

**Acceptance Scenarios**:

1. **Given** artigos indexados, **When** o usuario busca por "cartao credito", **Then** ve resultados relevantes com highlight do termo no titulo e trecho do conteudo.
2. **Given** resultados de busca, **When** o usuario aplica filtro por area + priority_level, **Then** os resultados sao filtrados em combinacao.
3. **Given** filtros aplicados, **When** o usuario aplica filtro adicional por faixa de overall_score (slider 0-100), **Then** os resultados sao refinados mantendo todos os filtros.

---

### User Story 8 - Fila de Revisao (Human-in-the-Loop) (Priority: P3)

Como gestor de conteudo, quero aprovar, rejeitar ou pedir revisao de reescritas propostas pelo LLM, para controlar a qualidade antes de publicar a versao melhorada.

**Why this priority**: Valor alto mas depende de reescritas existentes (pipeline helpcore-rewrite, fora do escopo atual). Sprint 2+.

**Independent Test**: Pode ser testado acessando /review, vendo a fila de pendentes, e aprovando/rejeitando uma reescrita.

**Acceptance Scenarios**:

1. **Given** artigos com reescrita pendente de revisao, **When** o usuario acessa /review, **Then** ve fila ordenada por priority_level (critical primeiro) com contagem total.
2. **Given** uma reescrita na fila, **When** o usuario clica "Aprovar", **Then** o status muda para `approved` no banco.
3. **Given** uma reescrita na fila, **When** o usuario clica "Rejeitar", **Then** campo de notas e obrigatorio e o status muda para `rejected`.

---

### User Story 9 - Analytics de Distribuicao (Priority: P3)

Como gestor de projeto, quero ver a distribuicao dos artigos por categoria, doc_type, target_audience e area, para entender a composicao da base e planejar priorizacao.

**Why this priority**: Nice-to-have para o Sprint 1 — entrega valor analitico mas o Dashboard basico ja cobre o essencial.

**Independent Test**: Pode ser testado acessando /dashboard e verificando que os graficos de distribuicao renderizam corretamente.

**Acceptance Scenarios**:

1. **Given** artigos processados com classificacao, **When** o usuario ve analytics, **Then** ve donut para distribuicao por categoria e doc_type.
2. **Given** artigos com overall_score, **When** analytics carrega, **Then** mostra histograma de overall_score e tabela de areas ranqueadas por qualidade media.

---

### Edge Cases

- O que acontece quando um artigo nao tem processing_output (ainda nao processado)? A pagina de detalhe mostra apenas o conteudo original com indicador "Aguardando processamento".
- O que acontece quando o ETL encontra um .txt com encoding diferente de UTF-8? O ETL tenta decodificar com fallbacks (latin-1, cp1252) e loga warning.
- O que acontece quando o banco esta inacessivel? A plataforma exibe pagina de erro amigavel "Sistema temporariamente indisponivel" sem expor detalhes tecnicos.
- O que acontece quando o cookie de sessao e manipulado? O middleware rejeita cookies invalidos e redireciona para /login.
- O que acontece quando dois gestores aprovam/rejeitam o mesmo artigo simultaneamente? O ultimo a submeter vence (last-write-wins); o historico preserva ambas as acoes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE permitir login com senha fixa configurada via variavel de ambiente, sem sistema de usuarios.
- **FR-002**: O sistema DEVE redirecionar usuarios nao autenticados para a tela de login em qualquer rota protegida.
- **FR-003**: O sistema DEVE exibir dashboard de progresso com contagens por status (pending, processing, processed, error), custo acumulado e estimativa de tempo restante.
- **FR-004**: O sistema DEVE permitir navegacao dos artigos organizados por area operacional com paginacao server-side (50 por pagina).
- **FR-005**: O sistema DEVE exibir conteudo original de cada artigo formatado em pagina de detalhe.
- **FR-006**: O sistema DEVE exibir os 33 campos do LLM para artigos processados, incluindo radar chart de qualidade.
- **FR-007**: O sistema DEVE permitir busca full-text nos artigos com highlight nos resultados.
- **FR-008**: O sistema DEVE permitir filtros combinados por area, priority_level, overall_score, categoria e doc_type.
- **FR-009**: O sistema DEVE exibir diff visual (side-by-side e inline) entre conteudo original e processado.
- **FR-010**: O sistema DEVE permitir aprovar, rejeitar ou pedir revisao de reescritas com campo de notas obrigatorio em rejeicao.
- **FR-011**: O ETL DEVE parsear headers dos .txt, gerar content_hash SHA-256 para dedup, e inserir em batches de 500 com barra de progresso.
- **FR-012**: O sistema DEVE atualizar dados do dashboard automaticamente a cada 30 segundos sem recarregar a pagina.
- **FR-013**: O sistema DEVE exibir graficos de distribuicao por categoria, doc_type, area e histograma de overall_score.
- **FR-014**: O cookie de sessao DEVE ter expiracao de 7 dias e flags httpOnly, Secure, SameSite=Strict.

### Key Entities

- **Article**: Artigo original do Help Bradesco. Atributos: titulo, area operacional, subcategoria, conteudo, content_hash, source_url, data de modificacao, classificacao (TEXTUAL/LINK_ONLY/SHORT_TEXT).
- **AnalysisResult**: Resultado do processamento LLM. Atributos: 33 campos estruturados (inventory, quality, passos, sugestoes), overall_score, priority_level, markdown_content processado.
- **ArticleRelationship**: Relacao entre artigos (duplicata, referencia cruzada). Atributos: artigo origem, artigo destino, tipo de relacao, score de similaridade.
- **ReviewAction**: Acao de revisao humana (aprovar/rejeitar/pedir revisao). Atributos: artigo, status, notas do revisor, data, revisor.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O ETL processa 108K arquivos .txt em menos de 30 minutos com zero perda de dados.
- **SC-002**: O Dashboard exibe metricas de progresso corretas (validadas contra queries SQL diretas) com latencia de atualizacao inferior a 5 segundos.
- **SC-003**: A busca full-text retorna resultados relevantes em menos de 2 segundos para qualquer termo.
- **SC-004**: O time Ello consegue navegar e ler qualquer artigo em menos de 3 cliques a partir do dashboard.
- **SC-005**: O diff visual renderiza corretamente para artigos com ate 10.000 palavras sem degradacao de performance.
- **SC-006**: 100% das rotas sao protegidas por autenticacao — nenhum conteudo acessivel sem login.
- **SC-007**: O gestor de conteudo consegue aprovar ou rejeitar uma reescrita em menos de 60 segundos.
- **SC-008**: O sistema suporta navegacao fluida para 108K artigos sem timeout ou erro de paginacao.

## Assumptions

- Os arquivos .txt ja estao disponiveis no servidor e seguem o formato de header padrao do export SharePoint (area, titulo, iid, modified_date separados por pipe ou tab).
- O PostgreSQL existente (pe-postgres:5432) tem capacidade para as tabelas adicionais do help_core sem impacto de performance nos servicos existentes.
- O processamento dos 108K artigos sera feito separadamente via PE — a plataforma apenas le resultados.
- A senha fixa de acesso sera definida via variavel de ambiente `HELPCORE_AUTH_PASSWORD` — nao ha necessidade de sistema de usuarios ou RBAC.
- Middleware nativo do Next.js (sem NextAuth) e suficiente para a autenticacao, conforme recomendacao HOMELAND.
- Queries live ao banco sao suficientes para o Dashboard no MVP — materialized views serao adicionadas na Fase 2 se necessario.
- O dominio `helpcore.digital-ai.tech` sera configurado via CNAME no Cloudflare apontando para o cluster Docker Swarm.

## Dependencies

- **Migration do banco**: Tabela `help_core.articles` com colunas `content TEXT` e `content_hash TEXT` deve existir antes do ETL.
- **Pipeline helpcore-analysis**: Validado e pronto para processar (ja confirmado com 10/10 artigos).
- **Arquivos .txt**: Disponiveis no servidor ou transferidos antes do ETL.
- **DNS**: CNAME `helpcore.digital-ai.tech` configurado antes do deploy.
- **PE sink whitelist**: `HELPCORE_DATABASE_URL` na whitelist do sink do PE antes de processar artigos.

## Scope Boundaries

### IN-SCOPE

- ETL Python standalone para ingestao de .txt
- Dashboard de progresso com refresh automatico
- Help Browser (navegacao por area + leitura de artigo)
- Visualizador de resultados processados (33 campos)
- Diff visual (side-by-side e inline)
- Busca full-text com filtros combinados
- Fila de revisao (aprovar/rejeitar/pedir revisao)
- Analytics de distribuicao
- Auth simples (senha fixa via middleware)

### OUT-OF-SCOPE

- Disparo/controle do processamento PE (o PE tem API propria)
- Edicao inline de artigos na plataforma
- Sistema de usuarios com RBAC
- Integracao live com SharePoint
- Pipeline de reescrita (helpcore-rewrite) — pipeline separado
- Grafo de relacionamentos (futuro, React Flow)
- Export de dados (CSV, PDF)

### REMOVIDOS

Nenhum item removido — spec inicial.
