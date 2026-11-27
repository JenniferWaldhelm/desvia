# Levantamento de cidades: fluxo (auditado em 18/11/2026)

Nada aqui muda o site sozinho: a Jen confere e aprova antes de qualquer ponto entrar.

## Etapas

| # | Etapa | Como | Situação |
|---|---|---|---|
| 0 | Arquivo mensal da Receita (PR inteiro, empresas com atividade de resíduo, qualquer situação) | Ação **Receita: arquivo mensal do Paraná**, todo dia 20. Guarda no release `receita-pr` | Feito |
| 1 | IAT GeoPR + CTF/IBAMA + Receita por CNPJ | Ação **Buscar empresas de uma cidade** → `<cidade>.csv` e `<cidade>-resumo.md` | Feito |
| 2 | Receita por atividade (inclusive sem licença) + conferência de licença IAT e CTF | Ação **Buscar empresas na Receita** → `<cidade>-receita.csv`. Lê o arquivo mensal (minutos); sem ele, baixa da Receita (1 a 2 h) | Feito |
| 3 | Checagens automáticas: ponto dentro do limite oficial do município, coordenada repetida, mesmo endereço, nome sem maiúsculas, resíduo em linguagem simples, próximo ID | `coleta/preparar.py` (roda no fim de "Buscar empresas na Receita") → `<cidade>-revisao.csv` | Feito |
| 4 | Nota de confiança (Alta/Média/Baixa): atividade de resíduo principal, palavra de resíduo no nome, licença/CTF, telefone. LP/LI baixa a nota. Recusados antes pela Jen (`recusados.csv`) e serviço de água e esgoto ficam fora | `coleta/preparar.py` | Feito |
| 5 | Localizadores de logística reversa (Reciclanip, Reciclus, Green Eletron pilhas e eletrônicos) do PR inteiro, uma vez por mês | Ação **Localizadores de logística reversa** (dia 21): `coleta/localizadores.py` lê Reciclanip, Green Eletron pilhas, Green Eletron eletroeletrônicos + ABREE, Reciclus, Jogue Limpo, OpenStreetMap e Mapa das OSCs (Ipea) → `localizadores-pr.csv`. Respeita o robots.txt. EcoMed só pelo navegador da Jen (robots.txt proíbe /api); LogMed pelo PDF que a Jen baixa (`coleta/logmed_pdf.py`) | Feito |
| 5a | **Licença também nos pontos dos localizadores** (decisão da Jen em 18/11/2026): achar o CNPJ no arquivo mensal da Receita (nome + endereço na cidade) e conferir IAT e CTF/IBAMA, para todos os pontos, inclusive farmácia e mercado | `coleta/preparar_localizadores.py` (roda na mesma ação): cruza com a base (CNPJ, endereço, nome), propõe "acrescentar resíduo" quando o ponto já existe, acha o CNPJ dos novos no arquivo da Receita (nome tem que bater) e confere IAT e CTF → `<cidade>-localizadores-revisao.csv` | Feito |
| 5b | **Duplicados prováveis** (27/11/2026): compara a base com ela mesma e os candidatos da Revisão com a base, por município. Nome por significado (modelo pequeno que roda no GitHub, sem custo), nome letra a letra, endereço e distância. Ignora palavras genéricas (loja, farmácia, shopping, Ltda) e não junta redes diferentes nem lojas da mesma rede com outro número | Ação **Procurar duplicados na base** (dia 22, ou à mão): `coleta/duplicados.py` → `duplicados.md` e `duplicados.csv`. Só avisa; a Jen decide. Para juntar: a linha mais completa fica, recebe o que só a outra tem, e a outra vira "duplicado" na Situação, com o motivo na Obs | Feito |
| 5c | **Empresa de lista oficial sem CNPJ** (27/11/2026): achar o CNPJ e a licença pelo nome antes de incluir | Ação **Buscar empresa pelo nome (IAT e Receita)**, à mão, com os nomes separados por ";": `coleta/buscar_por_nome.py` → `busca-por-nome.md` (licenças no IAT pelo nome e situação, endereço e telefone na Receita pelo CNPJ achado) | Feito |
| 6 | Verificação da Jen em lote na aba **Revisão** da planilha (Funciona? Recebe resíduo? Nota), só Alta e Média | Aba Revisão (sheetId 97), carregada por IMPORTDATA na aba importar. Quando a Jen terminar, Claude grava os "Sim" na aba Pontos (ID conferido na coluna A) e os "Não" em `recusados.csv` | Feito (gravação dos "Sim" a pedido) |
| 7 | Dados oficiais da cidade (cooperativas, ecopontos, limite de pequeno gerador, lei, canais de denúncia), fonte passada pela Jen | Checklist | Manual |
| 8 | Gravar (aba importar, IMPORTDATA) e publicar (Fila de cidades: Publicar = Sim) | Como na skill desvia-processar-cidade | Feito |

## Selo de licença nos pontos de entrega (PEV privado)

A conferência é feita em todos. No site:
- licença achada: mostra a licença (válida, vencendo ou vencida), como nas empresas;
- licença não achada: farmácia, mercado e loja continuam com o selo "ponto de entrega" (a licença não se aplica ao balcão);
- recicladora, ferro-velho, sucata, borracharia que armazena pneus ou empresa ambiental: não entra como PEV privado; entra como empresa e, sem licença, aparece "licença ambiental não localizada nas bases consultadas".

## Arquivos

- `<cidade>.csv`, `<cidade>-resumo.md`: etapa 1
- `<cidade>-receita.csv`, `<cidade>-receita-resumo.md`: etapa 2
- `localizadores.md`: como cada localizador entrega os dados (base da etapa 5)
- `qualidade.md`: checagem semanal (coordenadas e duplicados)
- `duplicados.md`, `duplicados.csv`: duplicados prováveis por semelhança (etapa 5b)
- `busca-por-nome.md`: última busca de empresa pelo nome (etapa 5c)
- `revisao-AAAA-MM.md`: revisão mensal das licenças
