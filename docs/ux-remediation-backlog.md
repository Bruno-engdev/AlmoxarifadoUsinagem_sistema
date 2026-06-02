# Backlog de remediacao UX e confiabilidade

Data: 2026-06-02

## Diagnostico

O sistema tem uma base boa de UX operacional, especialmente nas telas de dashboard financeiro, ferramentas e movimentacoes, mas ainda existem rupturas que afetam confianca, leitura e previsibilidade. Os maiores problemas atuais nao sao apenas esteticos: ha divergencia entre o que a interface promete e o que o backend realmente filtra, ordenacoes que parecem globais mas operam apenas na pagina visivel, uma grade de ferramentas com dado operacional exibido de forma incorreta e lacunas de acessibilidade na shell principal.

Usuario principal:

- operador de almoxarifado nas rotinas de consulta e movimentacao
- gestor ou lider de usinagem nas leituras de dashboard e consumo
- administrativo em consultas historicas, filtros e auditoria operacional

Decisoes apoiadas por esta funcionalidade:

- liberar ou bloquear uso de item com base em estoque real
- interpretar consumo, disponibilidade critica e ociosidade com filtro coerente
- consultar movimentacoes por periodo, ferramenta e contexto sem perda de estado

Restricoes tecnicas observadas:

- stack server-rendered com FastAPI, Jinja2, SQLAlchemy e assets estaticos servidos pela app
- coexistencia de filtros por GET, ordenacao client-side e alguns fluxos AJAX parciais
- ambiente com possibilidade de uso em rede interna, o que torna dependencia de CDN um risco real
- ausencia de suite automatizada visivel para proteger regressao de UX e de integridade tabular

## Proposta consolidada

A recomendacao e atacar o problema em cinco frentes progressivas e reversiveis: primeiro corrigir confiabilidade visual e semantica nas telas que podem induzir erro operacional; depois estabilizar a shell compartilhada; na sequencia unificar o modelo de consulta das grades; em seguida consolidar o contrato do dashboard principal; e por fim adicionar observabilidade e testes de fumaca para que a UX nao volte a degradar a cada nova entrega.

Essa ordem foi escolhida porque combina impacto operacional, custo de implementacao e risco de regressao. A prioridade nao e "deixar mais bonito". A prioridade e fazer a interface dizer a verdade, responder de forma previsivel e manter coerencia entre rota, query string, filtro, tabela e graficos.

## Decisoes por agente

| Agente | Decisao principal | Justificativa |
|---|---|---|
| Arquiteto de Sistema | Migrar ordenacao e paginacao criticas para o backend e reduzir estado duplicado entre template e JavaScript | Hoje a UX quebra porque o contrato de dados nao e consistente entre pagina, filtro e script |
| UX / Product Designer | Padronizar shell, feedback de consulta, acessibilidade e hierarquia de filtros antes de novas expansoes visuais | O principal gargalo e previsibilidade operacional, nao falta de componentes |
| Analista de Dados | Garantir que dashboard e tabelas mostrem sempre o mesmo recorte, com indicadores e contagens rastreaveis | Sem coerencia de recorte, KPI vira decoracao e nao apoio real a decisao |
| Revisor Critico | Tratar como prioridade maxima tudo que induz erro de leitura ou falsa interpretacao de ordenacao e filtro | Os maiores riscos sao de confianca e tomada de decisao errada, nao de acabamento visual |

## Riscos criticos

| Severidade | Risco | Impacto | Ajuste minimo |
|---|---|---|---|
| Bloqueante | Coluna de estoque em Ferramentas mostra valor de maximo em vez de estoque atual | Operador pode tomar decisao com base em dado visual errado | Corrigir binding da coluna e padronizar formatacao monetaria |
| Alto | Dashboard promete recalculo amplo, mas parte dos widgets ignora filtros ativos | Gestor interpreta a tela como consistente quando nao esta | Unificar contrato do filtro ou restringir a promessa visual |
| Alto | Ordenacao nas grades e local a pagina atual, mas a interface sugere ordenacao global | Usuario acredita estar vendo o topo do conjunto completo | Levar sort para query string e backend |
| Medio | Shell tem lacunas de acessibilidade e falhas silenciosas em notificacoes | Menor previsibilidade para teclado e sem feedback em erro de rede | Tornar controles semanticos e explicitar erro ao usuario |
| Medio | Dependencia de CDN externo para CSS, icones e graficos | Ambiente interno pode renderizar app quebrado mesmo com backend saudavel | Internalizar assets em static |

## Plano de execucao

### Fase 1 - Correcao de confiabilidade operacional

Objetivo: eliminar qualquer leitura errada que possa induzir decisao incorreta.

Task 1.1 - Corrigir grade de Ferramentas

- Decisao apoiada: consulta rapida de disponibilidade e custo
- Arquivos alvo: `app/templates/tools/index.html`
- Mudancas:
- corrigir coluna Estoque para usar estoque atual em vez de maximo
- formatar custo unitario como moeda
- revisar alinhamento visual de campos numericos
- Criterios de aceite:
- a coluna Estoque exibe o valor real do item
- a coluna Max continua exibindo apenas maximo
- custo unitario passa a ter leitura monetaria consistente
- Validacao:
- smoke manual na listagem com itens de estoque diferentes entre current_stock e max_stock
- revisao visual em desktop e notebook

Task 1.2 - Corrigir contrato da filtragem no dashboard principal

- Decisao apoiada: leitura gerencial de consumo, disponibilidade e ociosidade
- Arquivos alvo: `app/templates/dashboard.html`, `app/routers/dashboard.py`, possivelmente `app/services/analytics.py`
- Mudancas:
- escolher entre full reload coerente ou full AJAX coerente
- alinhar copy da tela com o comportamento real
- garantir que widgets afetados usem o mesmo recorte de filtro
- Criterios de aceite:
- nenhum bloco principal do dashboard ignora filtro que a interface diz aplicar
- usuario consegue explicar o recorte atual sem ambiguidade
- estados de loading, empty e erro ficam claros
- Validacao:
- comparar recorte sem filtro versus recorte filtrado por tipo, periodo e nome
- validar query string e navegacao por voltar e avancar do navegador

### Fase 2 - Shell e acessibilidade de uso diario

Objetivo: reforcar previsibilidade da navegacao e confianca de uso em operacao continua.

Task 2.1 - Fortalecer drawer e notificacoes

- Decisao apoiada: navegacao rapida e leitura de alertas
- Arquivos alvo: `app/templates/base.html`, `app/static/js/app.js`
- Mudancas:
- trocar gatilhos interativos nao semanticos por `button`
- implementar foco inicial, trap basico e devolucao de foco no drawer
- remover falhas silenciosas em notificacoes e mostrar feedback de erro
- Criterios de aceite:
- shell inteira pode ser operada por teclado sem perda de foco
- erros de notificacao exibem feedback visivel ao usuario
- nenhum controle principal depende apenas de clique do mouse
- Validacao:
- navegacao por teclado no drawer e na area de notificacoes
- teste com falha de rede simulada nas chamadas de notificacao

Task 2.2 - Internalizar assets criticos do frontend

- Decisao apoiada: disponibilidade da interface em rede interna
- Arquivos alvo: `app/templates/base.html`, `app/static/`, `Dockerfile` se necessario
- Mudancas:
- servir Bootstrap, Bootstrap Icons e Chart.js localmente
- revisar se o build e a imagem copiam corretamente os assets
- Criterios de aceite:
- a shell renderiza sem dependencia de acesso externo
- dashboard e modais continuam funcionando com os assets locais
- Validacao:
- subir app com rede externa indisponivel e conferir renderizacao

### Fase 3 - Modelo unico de consulta para grades operacionais

Objetivo: fazer filtros, ordenacao e paginacao significarem a mesma coisa para usuario e backend.

Task 3.1 - Consolidar filtros de Movimentacoes

- Decisao apoiada: auditoria e busca historica por contexto operacional
- Arquivos alvo: `app/templates/movements/index.html`, `app/routers/movements_router.py`, `app/static/css/style.css`
- Mudancas:
- reduzir fragmentacao dos tres formularios atuais
- centralizar estado na query string
- tornar visivel o resumo do recorte ativo e a acao de limpar
- Criterios de aceite:
- aplicar um filtro nao apaga os demais
- o usuario enxerga claramente ferramenta, periodo, categoria e busca ativos
- o layout continua denso e legivel em telas menores
- Validacao:
- combinacao de filtros multiplos com navegacao entre paginas

Task 3.2 - Levar ordenacao e paginacao de Ferramentas e Movimentacoes para o backend

- Decisao apoiada: leitura correta de ranking, historico e priorizacao operacional
- Arquivos alvo: `app/routers/tools.py`, `app/routers/movements_router.py`, `app/templates/tools/index.html`, `app/templates/movements/index.html`, `app/pagination.py`
- Mudancas:
- substituir sort client-side sobre DOM por sort server-side com query string
- ativar paginacao real nas duas grades
- preservar filtros ao trocar pagina e ordenacao
- Criterios de aceite:
- a coluna ativa e a direcao ficam explicitas
- o topo da grade representa o dataset completo filtrado
- pagina, ordenacao e filtro convivem sem perder estado
- Validacao:
- testes manuais com base extensa e troca de paginas
- conferencia do primeiro item ao alternar asc e desc

Task 3.3 - Reequilibrar densidade das acoes por linha em Ferramentas

- Decisao apoiada: operacao rapida sem poluir leitura tabular
- Arquivos alvo: `app/templates/tools/index.html`, `app/static/css/style.css`
- Mudancas:
- priorizar dados da linha sobre a massa de botoes
- reduzir peso visual das acoes secundarias
- manter foco e acessibilidade claros
- Criterios de aceite:
- leitura de nome, status e estoque passa a dominar a linha
- todas as acoes continuam acessiveis em ate um gesto adicional
- Validacao:
- comparacao visual antes e depois com mesma massa de dados

### Fase 4 - Coerencia analitica entre dashboards e tabelas

Objetivo: garantir que KPI, grafico, chips e tabelas falem do mesmo universo de dados.

Task 4.1 - Fechar o contrato do dashboard principal

- Decisao apoiada: analise gerencial confiavel
- Arquivos alvo: `app/templates/dashboard.html`, `app/routers/dashboard.py`, `app/services/analytics.py`
- Mudancas:
- revisar quais widgets devem responder aos filtros globais
- alinhar payloads e atualizacao visual dos blocos
- explicitar quando um componente for deliberadamente global e nao filtrado
- Criterios de aceite:
- cada widget tem comportamento de filtro compreensivel e consistente
- nenhuma legenda ou texto promete mais do que o sistema entrega
- Validacao:
- matriz de verificacao por widget e por filtro

Task 4.2 - Padronizar feedback de consulta nas telas analiticas

- Decisao apoiada: leitura rapida do escopo analitico atual
- Arquivos alvo: `app/templates/dashboard.html`, `app/templates/financials.html`, `app/static/css/style.css`
- Mudancas:
- padronizar chips de escopo, resumo de recorte, erro e empty state
- reaproveitar a estrategia que ja ficou melhor resolvida no dashboard financeiro
- Criterios de aceite:
- o usuario identifica em segundos o recorte ativo
- empty state e erro nao parecem quebra de tela
- Validacao:
- teste manual com filtro sem resultado e com falha de carregamento

### Fase 5 - Qualidade, rollback e observabilidade

Objetivo: impedir regressao silenciosa nas areas de maior impacto de UX.

Task 5.1 - Adicionar smoke tests das rotas e templates criticos

- Decisao apoiada: reduzir risco de regressao em listagens e dashboards
- Arquivos alvo: nova pasta de testes, rotas principais e helpers de template
- Mudancas:
- criar cobertura minima para `/`, `/tools`, `/movements`, `/financials` e tabelas derivadas
- validar status code, render basico e campos essenciais da pagina
- Criterios de aceite:
- falhas de rota, template ausente ou contexto incompleto quebram pipeline local
- Validacao:
- execucao da suite de smoke tests no ambiente local e no container

Task 5.2 - Instrumentar erros de UX e rollback operacional

- Decisao apoiada: manutencao segura apos rollout
- Arquivos alvo: `app/main.py`, logs, scripts de deploy ou documentacao operacional
- Mudancas:
- padronizar logging para falhas AJAX, erros de template e excecoes de endpoints de consulta
- documentar rollback rapido para assets, scripts e templates de alto impacto
- Criterios de aceite:
- falhas relevantes ficam rastreaveis em log
- existe procedimento curto de reversao para mudancas de shell e dashboard
- Validacao:
- simular falha controlada e conferir rastreabilidade

## Sequencia recomendada de entrega

1. Task 1.1
2. Task 1.2
3. Task 2.1
4. Task 3.2
5. Task 3.1
6. Task 3.3
7. Task 2.2
8. Task 4.1
9. Task 4.2
10. Task 5.1
11. Task 5.2

Observacao: a Fase 2.2 pode ser antecipada se o ambiente de deploy tiver historico de instabilidade de rede ou restricao de internet.

## Validacao

Como provar que a solucao funcionou:

- comparar antes e depois das telas criticas com o mesmo dataset
- validar as jornadas principais de operador e gestor sem uso do mouse em pelo menos uma rodada
- conferir preservacao completa de query string em filtro, ordenacao e paginacao
- medir se o usuario consegue identificar o recorte ativo, a coluna ordenada e o total de resultados sem inspecionar o codigo
- executar smoke tests das rotas principais a cada fase entregue
- registrar rollout incremental, com validacao fase a fase em ambiente local e no container