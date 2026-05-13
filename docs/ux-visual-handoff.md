# Handoff tecnico - melhorias visuais e UX

Data: 2026-05-13

Objetivo: orientar uma rodada de refinamento visual coerente para dashboard, ferramentas e movimentacoes, preservando o padrao operacional flat e full-width ja adotado nas telas transacionais.

## 1. Mapa do sistema

- A aplicacao e um FastAPI server-rendered com Jinja2, sessao por cookie e assets estaticos montados no proprio app. O entrypoint centraliza middleware, templates, static e routers em `app/main.py`.
- A infraestrutura de banco usa SQLAlchemy com suporte a SQLite e PostgreSQL, sessao por request e ciclo de schema orientado por Alembic fora do processo web em `app/database.py`.
- A autenticacao e baseada em sessao e guardas de acesso, com papel de admin tratado no backend em `app/auth.py`.
- As dependencias principais do backend estao em `requirements.txt`: FastAPI, SQLAlchemy, Jinja2, OpenPyXL, Alembic e Psycopg. No frontend, a shell usa Bootstrap, Bootstrap Icons e Chart.js carregados na base.
- A shell visual compartilhada vive em `app/templates/base.html` e no tema global de `app/static/css/style.css`. E ali que estao topbar, drawer, tokens de cor, tabelas, toolbars e o styling ja pronto de paginacao.
- A tela de Ferramentas organiza a navegacao com subheader estrutural, barra de acoes e busca em `app/templates/tools/index.html`, e o browse full-width comeca no mesmo arquivo.
- A tela de Movimentacoes usa tabs de categoria em `app/templates/movements/index.html`, toolbar de filtros e busca no mesmo template e browse full-width logo abaixo.
- O dashboard ja segue uma linguagem mais sofisticada, com hero analitico e paineis dedicados em `app/templates/dashboard.html` e estilos especificos em `app/static/css/style.css`.
- O backend de Ferramentas faz listagem, busca, exportacao e movimentacao por modal, com a funcao `tools_list` e a delegacao de mutacoes para o servico de movimentos em `app/routers/tools.py`.
- O backend de Movimentacoes faz listagem filtrada, criacao manual, edicao, devolucao e exclusao, concentrando a view principal em `movements_list` em `app/routers/movements_router.py`.
- Os fluxos principais relevantes para UI sao:
	- Ferramentas: subheader operacional, busca, browse tabular, acao inline por linha, modal de movimentacao.
	- Movimentacoes: selecao de contexto por categoria, filtros compostos, browse tabular, modais administrativos.
	- Dashboard: visao analitica com identidade mais rica que as telas transacionais.

## 2. Achados

- O pedido e amplo demais para uma unica alteracao segura. A melhor divisao e em tres fases: linguagem visual compartilhada das telas operacionais, refinamento das duas listagens e paginacao real com estado persistente.
- Ferramentas e Movimentacoes ja tem uma base boa de UX operacional, mas ainda parecem uma segunda familia visual em relacao ao dashboard. O contraste entre `app/templates/dashboard.html` e os padroes flat de `app/templates/tools/index.html` e `app/templates/movements/index.html` sugere dois niveis de acabamento no mesmo produto.
- A linguagem operacional atual e coerente e deve ser preservada. O subheader full-width e o browse achatado sao sustentados por `app/static/css/style.css`. Isso aponta para refinamento de densidade, hierarquia e feedback, nao para reintroducao de cards envolventes nas paginas transacionais.
- A tela de Ferramentas tem um browse visualmente forte, mas as acoes por linha estao densas demais. As tres acoes inline ficam todas expostas na mesma linha da tabela e competem com a leitura de nome, status e estoque.
- A tela de Movimentacoes tem a melhor organizacao mental inicial por causa das tabs de categoria, mas a toolbar concentra contexto, filtro, limpeza, busca e acao administrativa no mesmo bloco. O resultado tende a ficar pesado e heterogeneo.
- O styling de paginacao existe, mas o componente real nao esta implantado. Ha tema para `page-link` em `app/static/css/style.css`, porem as listagens continuam carregando tudo com `.all()` em `app/routers/tools.py` e `app/routers/movements_router.py`.
- As telas inspecionadas ainda nao oferecem feedback visual suficiente sobre estado da consulta: quantidade de resultados, intervalo mostrado, filtros ativos removiveis e leitura clara de contexto. Isso e uma lacuna mais visivel em Ferramentas, onde a busca existe, mas o retorno visual da consulta e minimo.
- Ha uma oportunidade clara de transformar o que hoje e um browse competente em um sistema visual de consulta mais maduro sem mexer na arquitetura principal: a base estrutural ja existe e esta concentrada em poucos templates e em um unico arquivo de estilos compartilhados.

## 3. Fila de tasks

### Task 1

Titulo: Fase 1 - Unificar a linguagem visual das telas operacionais

Objetivo: alinhar Ferramentas e Movimentacoes em uma mesma gramatica visual de gestao, preservando o padrao flat e full-width ja adotado.

Evidencia no codigo: a shell operacional esta distribuida entre o subheader de `app/templates/tools/index.html`, a toolbar de `app/templates/movements/index.html`, e os estilos compartilhados de `app/static/css/style.css`. O dashboard ja usa uma linguagem mais refinada em `app/templates/dashboard.html` e no mesmo `style.css`.

Arquivos ou simbolos afetados: `app/templates/tools/index.html`, `app/templates/movements/index.html`, `app/static/css/style.css`, `app/templates/base.html`.

Mudanca esperada: padronizar hierarquia de titulos secundarios, respiros, agrupamento de controles, estados de foco e linguagem visual dos toolbars, sem introduzir wrappers em card nas paginas de gestao.

Criterios de aceite:
- Ferramentas e Movimentacoes devem parecer partes do mesmo produto.
- Os toolbars precisam ter o mesmo ritmo visual.
- O browse continua full-width e sem caixinhas envolventes.
- O comportamento em mobile deve manter ordem logica dos controles.

Dependencias: nenhuma.

Risco: baixo.

Prioridade sugerida: alta.

### Task 2

Titulo: Fase 1 - Adicionar faixa de contexto e feedback de consulta nas listagens

Objetivo: tornar o estado da busca e dos filtros visivel antes da leitura da tabela.

Evidencia no codigo: a busca em Ferramentas esta concentrada em `app/templates/tools/index.html` e os filtros compostos de Movimentacoes em `app/templates/movements/index.html`, mas nao ha resumo consistente de resultados, contexto atual ou filtros ativos nas versoes atuais inspecionadas.

Arquivos ou simbolos afetados: `app/templates/tools/index.html`, `app/templates/movements/index.html`, `app/static/css/style.css`.

Mudanca esperada: incluir faixa leve de contexto logo abaixo do toolbar com total de resultados, escopo ativo, filtros aplicados em chips removiveis e acao clara de limpar estado.

Criterios de aceite:
- Ao aplicar busca, categoria, ferramenta ou data, o usuario deve enxergar imediatamente o que esta filtrando e quantos registros sobraram.
- A remocao de filtros deve ser possivel sem reabrir seletores.
- O componente deve funcionar nas duas telas com a mesma linguagem.

Dependencias: Task 1.

Risco: baixo.

Prioridade sugerida: alta.

### Task 3

Titulo: Fase 2 - Reequilibrar densidade e prioridade das acoes por linha em Ferramentas

Objetivo: devolver protagonismo aos dados da linha e reduzir ruido operacional sem perder velocidade de uso.

Evidencia no codigo: a linha de Ferramentas concentra tres acoes inline em `app/templates/tools/index.html`, sobre um grid denso e achatado sustentado por `app/static/css/style.css`.

Arquivos ou simbolos afetados: `app/templates/tools/index.html`, `app/static/css/style.css`, modal de movimentacao em `app/templates/tools/index.html`.

Mudanca esperada: reduzir o peso visual das acoes secundarias, agrupar comandos correlatos, revisar icones e estados de hover e manter apenas a acao mais critica em destaque visivel, se isso nao comprometer a operacao.

Criterios de aceite:
- A leitura de nome, status e estoque deve ser mais rapida que a leitura das acoes.
- A altura da linha nao pode crescer de forma significativa.
- Todos os comandos continuam acessiveis.
- O foco por teclado continua claro.

Dependencias: Task 1.

Risco: medio, porque altera um padrao de uso repetido.

Prioridade sugerida: alta.

### Task 4

Titulo: Fase 2 - Reestruturar a barra de filtros de Movimentacoes em dois niveis de leitura

Objetivo: separar contexto operacional de filtro analitico e reduzir a sensacao de barra apertada.

Evidencia no codigo: a selecao de categoria esta em `app/templates/movements/index.html` e o restante dos controles fica condensado no mesmo template logo abaixo. O grid principal comeca na mesma view, o que torna a entrada na tela visualmente abrupta.

Arquivos ou simbolos afetados: `app/templates/movements/index.html`, `app/static/css/style.css`.

Mudanca esperada: dividir a interface em um bloco de contexto primario e um bloco de filtro e busca, com melhor agrupamento visual entre categoria, ferramenta, datas, busca e acao administrativa.

Criterios de aceite:
- A categoria continua sendo o primeiro contexto percebido.
- A barra de filtros deixa de parecer um conjunto de formularios independentes.
- A visualizacao em telas menores deve empilhar controles em ordem previsivel.
- Nenhum filtro atual pode perder persistencia ao submeter outro.

Dependencias: Task 1.

Risco: medio.

Prioridade sugerida: alta.

### Task 5

Titulo: Fase 3 - Implantar paginacao real compartilhada e conectar o tema visual ja existente

Objetivo: transformar o styling de paginacao ja pronto em componente funcional real nas duas listagens.

Evidencia no codigo: o tema visual da paginacao existe em `app/static/css/style.css`, mas Ferramentas e Movimentacoes ainda carregam todos os registros com `.all()` em `app/routers/tools.py` e `app/routers/movements_router.py`.

Arquivos ou simbolos afetados: `app/routers/tools.py`, `app/routers/movements_router.py`, `app/templates/tools/index.html`, `app/templates/movements/index.html`, `app/static/css/style.css`.

Mudanca esperada: introduzir parametros de pagina e tamanho, calcular total e intervalo mostrado, renderizar componente visual compartilhado de paginacao e preservar todos os filtros e ordenacoes na navegacao.

Criterios de aceite:
- Ambas as telas devem mostrar pagina atual, total de paginas, anterior, proxima e intervalo exibido.
- Trocar de pagina nao pode perder busca, categoria, datas ou ferramenta selecionada.
- O componente deve usar a linguagem visual ja existente e caber no padrao flat das telas de gestao.

Dependencias: Task 1. Recomendada apos Task 2 e Task 4 para integrar a paginacao ao resumo de consulta.

Risco: medio para alto, porque combina backend, URLs e template.

Prioridade sugerida: alta, se a intencao for avaliar UX com base de dados maior. Se a rodada for estritamente visual, mover para a etapa seguinte.

### Task 6

Titulo: Fase 3 - Refinar affordance de ordenacao e estado ativo das colunas

Objetivo: tornar a ordenacao mais legivel e menos dependente de tentativa e erro.

Evidencia no codigo: as duas telas usam ordenacao client-side diretamente nos templates, mas o estado e pouco persistente e a affordance visual fica limitada ao icone generico de cabecalho.

Arquivos ou simbolos afetados: `app/templates/tools/index.html`, `app/templates/movements/index.html`, `app/static/css/style.css`.

Mudanca esperada: destacar melhor coluna ativa, direcao atual, area clicavel e, se a paginacao real entrar no escopo, alinhar a ordenacao ao backend para nao quebrar consistencia entre paginas.

Criterios de aceite:
- O usuario deve saber qual coluna esta ordenando e em qual direcao sem precisar clicar duas vezes.
- A aparencia ativa deve sobreviver a reload quando o estado estiver em query string.
- Hover e focus devem continuar claros.

Dependencias: Task 5, se a ordenacao for promovida para server-side. Sem paginacao real, pode ser executada isoladamente no frontend.

Risco: medio.

Prioridade sugerida: media.

### Task 7

Titulo: Fase 3 - Harmonizar o acabamento visual entre Dashboard e telas de gestao

Objetivo: aproximar a percepcao de produto unico sem diluir a diferenca entre tela analitica e tela transacional.

Evidencia no codigo: o dashboard ja usa uma linguagem mais refinada em `app/templates/dashboard.html` e `app/static/css/style.css`, enquanto as telas operacionais se apoiam em `app/static/css/style.css` e nos templates de listagem.

Arquivos ou simbolos afetados: `app/templates/dashboard.html`, `app/templates/tools/index.html`, `app/templates/movements/index.html`, `app/static/css/style.css`.

Mudanca esperada: compartilhar tokens de tipografia, espacamento, titulos de secao e pequenos elementos de contexto, mantendo o dashboard mais rico e as telas de gestao mais secas.

Criterios de aceite:
- O app passa a parecer um mesmo sistema ao alternar entre Painel, Ferramentas e Movimentacoes.
- O dashboard permanece mais expressivo.
- As telas de gestao nao perdem a leitura densa e operacional.

Dependencias: Task 1.

Risco: baixo.

Prioridade sugerida: media.

## 4. Notas para o proximo agente

- Preservar a premissa ja observada neste repositorio: telas operacionais funcionam melhor com subheaders estruturais, browse full-width e tabelas sem grandes wrappers visuais. O trabalho deve refinar isso, nao trocar por cards de dashboard.
- Nao tratar a paginacao como detalhe cosmetico. O CSS de paginacao ja existe, mas o backend ainda entrega tudo de uma vez. Se o objetivo for avaliar UX com massa de dados real, a task hibrida de paginacao precisa entrar cedo.
- Tomar cuidado com a persistencia de contexto. Em Movimentacoes, categoria, ferramenta, datas, busca e acao administrativa ja se influenciam mutuamente. Qualquer rearranjo visual precisa manter esse estado consistente.
- Em Ferramentas, validar com atencao a reorganizacao das acoes por linha. Essa e a melhoria com maior chance de gerar resistencia do usuario por mexer em velocidade operacional e memoria muscular.

Recomendacoes de validacao:

- Revisar desktop largo, notebook e mobile estreito.
- Validar com base volumosa de ferramentas e movimentacoes.
- Conferir estados de hover, focus e navegacao por teclado.
- Garantir preservacao de query string em busca, filtro, ordenacao e paginacao.
- Conferir empty states, estados sem resultado e combinacao de multiplos filtros.

Restricoes e duvidas em aberto:

- Nao foi possivel confirmar render ao vivo durante a inspecao porque o ambiente usado na validacao nao tinha `uvicorn` disponivel na venv acionada naquele momento.
- Definir se a paginacao entra nesta rodada ou fica como etapa seguinte.
- Definir se as acoes inline de Ferramentas devem continuar expostas por velocidade ou podem ser parcialmente recolhidas.
- Definir se o dashboard deve continuar deliberadamente mais sofisticado que as telas transacionais, o que hoje parece uma decisao coerente.
