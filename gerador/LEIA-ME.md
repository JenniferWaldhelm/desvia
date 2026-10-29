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
