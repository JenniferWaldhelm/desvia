# Localizadores de logística reversa: como ler os dados

Anotado em 17/11/2026, na busca de Sarandi (skill desvia-localizadores). Todos foram lidos pelo Chrome da Jen.

| Programa | Página | Como os dados chegam | Observação |
|---|---|---|---|
| EcoMed (medicamentos, agulhas e seringas) | https://ecomed.eco.br/mapa | `GET /api/geo/cidades?q=<cidade>` devolve a cidade e o número de pontos. Os pontos vêm do servidor (Next.js) e ficam no estado do React. Ler com JavaScript: subir pelo `__reactFiber` do `.leaflet-container` até achar a lista com `name, address, city, state, latitude, longitude, phone, residueTypes`. Filtrar por `city`. | Na busca, digitar só o nome da cidade e escolher a sugestão com seta para baixo + Enter. |
| Reciclanip (pneus) | https://www.reciclanip.org.br/pontos-de-coleta/coleta-no-brasil/ | `POST /ajax/pontos.php` ao escolher o estado no select `#uf`. A lista do estado inteiro aparece como texto na página (cidade, telefone, endereço, CEP). | PR: 114 pontos em 17/11/2026. Sarandi: nenhum. |
| Green Eletron, pilhas e baterias | https://sistema.reciclelog.com.br/info/green | Formulário GET `?search_state=PR&search_city=SARANDI&button=` (página da Ambipar). Resultado em tabela HTML. | O nome da cidade vai em maiúsculas, como no select. |
| Green Eletron, eletroeletrônicos (inclui pontos ABREE) | https://greeneletron.org.br/onde-descartar/ | Busca por endereço (Google Maps) e `POST https://green.care-br.com/busca_empresa.php`. Lista lateral com nome, endereço, CEP e distância. | Pontos da ABREE aparecem com "- Abree" no nome. |
| Reciclus (lâmpadas) | https://reciclus.org.br/lista-pontos-entrega/ | Select `estado` (PR) carrega o select `cidade` (Sarandi = 319). A lista aparece como texto (nome, endereço, CEP). | |
| inpEV (embalagens de agrotóxico) | https://www.inpev.org.br | Não lido: a unidade da região fica em Maringá (regra da sede). | Na página da cidade, só orientação e botão. |

## Atualização em 18/11/2026 (Apucarana)

- Reciclanip: `POST /ajax/pontos.php` com corpo `uf=PR` devolve JSON (razao_social, nome_comercial, endereco, cidade, cep, telefone). Em 18/11/2026: 57 pontos no PR, nenhum em Apucarana. Dá para pôr na ação do GitHub.
- Reciclus: Apucarana = código 180 no select `cidade`; 8 pontos.
- Green Eletron pilhas (reciclelog): `search_city=APUCARANA`, 9 pontos.
- EcoMed: depois de buscar a cidade, a lista fica nas props do React (procurar no fiber de qualquer elemento um array com `latitude` e `address`); 30 pontos (UBS e farmácias). Coordenadas -23.55000, -51.46350 repetidas = centro da cidade, não usar.
- Jogue Limpo (PEVs, PR): nenhum em Apucarana.
- inpEV: página de unidades deu erro no navegador em 18/11/2026.
- Prolata: o mapa do Brasil não abriu a lista do PR pelo clique; não lido.
- Resultado salvo em `coleta/apucarana-localizadores.csv`.
