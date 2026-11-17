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
