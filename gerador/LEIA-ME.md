# Gerador de páginas "Onde descartar"

Cria uma página para cada combinação de cidade e tipo de resíduo, a partir da
aba **Pontos** da planilha *Desvia - Base Mestra*.

```
dados/pontos.csv                     cópia da aba Pontos
gerador/gerar.py                     o gerador
gerador/estilo.css                   estilo das páginas (cores do Desvia)
residuos/                            páginas geradas (não editar à mão)
.github/workflows/atualizar-paginas.yml  atualização automática
```

## Rodar à mão

```
python3 gerador/gerar.py
```

## Publicar uma cidade nova

1. A cidade é processada e aprovada na planilha (status "Verificado").
2. Acrescente a cidade em `CIDADES` no topo de `gerador/gerar.py`.
3. Rode o gerador (ou a ação "Atualizar páginas de resíduos" no GitHub).

Só vira página a combinação cidade × resíduo que tem pelo menos uma opção.

## Atualização automática pela planilha

1. Na planilha: Arquivo > Compartilhar > Publicar na Web > aba **Pontos** > formato **CSV** > Publicar. Copie o link.
2. No GitHub: Settings > Secrets and variables > Actions > aba Variables > New variable.
   Nome `PLANILHA_CSV_URL`, valor = o link copiado.
3. Toda segunda a ação baixa a planilha, regenera as páginas e publica se algo mudou.
   Também dá para rodar na hora em Actions > Atualizar páginas de resíduos > Run workflow.

Só a aba Pontos fica pública. Fila de cidades, Fontes e Pendências continuam privadas.

## Regras de texto das licenças

- Licença válida: tipo, número, órgão e validade. Aparece primeiro.
- Sem licença encontrada: "Licença não localizada nas bases consultadas em [data]". Nunca "sem licença".
- Licença prévia ou de instalação: aviso de que não autoriza a operação.
- CNPJ inapto ou baixado: aviso com a data da consulta.
- Pessoa física sem CNPJ: o endereço não é publicado.

## Página da cidade (mapa com filtros)

`residuos/<cidade>/` é a ferramenta: mapa, busca, filtros por tipo de atendimento e por resíduo,
"só com licença válida" e "só com sede na cidade", mais a seção de obrigações das empresas.
O conteúdo dessa seção fica em `gerador/hub.py` (partes comuns + `LOCAL` por município).
As páginas de cada resíduo têm o link "Abrir no mapa com filtros", que abre a ferramenta já filtrada (`?r=pneus`).

## IndexNow (Bing)

A ação avisa o Bing pelo IndexNow sempre que as páginas mudam (e quando é rodada à mão).
A chave fica em `gerador/indexnow_key.txt` e o arquivo de verificação na raiz do site (`<chave>.txt`).
Não apague esses dois arquivos.

## llms.txt e WebMCP (assistentes de IA)

- `llms.txt` (raiz do site) é gerado a cada atualização: resumo do Desvia, cidades, páginas por resíduo e guias.
- `residuos/webmcp.js` registra duas ferramentas WebMCP (`navigator.modelContext`) na página inicial e nas páginas de cidade:
  `buscar_onde_descartar` (resíduo, cidade, quem, só licença válida) e `listar_residuos_e_cidades`.
  O formulário de busca da página inicial também tem os atributos declarativos (`toolname`, `tooldescription`).
  Em navegadores sem WebMCP, nada acontece.
- Para valer em produção no Chrome, cadastre o site no teste de origem do WebMCP e cole o token em
  `<meta http-equiv="origin-trial" content="TOKEN">` (constante `ORIGIN_TRIAL` em `gerador/gerar.py`).
