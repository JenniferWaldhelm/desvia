# RAPP/IBAMA no Paraná (19/11/2026)

- Linhas do Paraná: 232648
- Empresas (CNPJ) do Paraná: 9329
- Já estão no Desvia: 70 (45 com categorias que faltam no cadastro)
- Recebem resíduo de terceiros e não estão no Desvia: 273
- Recebem cinza (destinador, armazenador ou reciclador): 51

## Avisos

- pilhas-fabricante-destinacao: sem coluna de UF ou município; base ignorada

## Colunas reconhecidas em cada base

Confira se cada campo caiu na coluna certa. Se não, ajuste CAMPOS ou NAO_SAO no script.

### destinador (destinador)

- Arquivo: 73.5 MB, separador `;`, codificação utf-8-sig
- Linhas: 170400; no Paraná: 13141
- Campos: cnpj → `CNPJ do destinador`; razao → `Razão Social do destinador`; uf → `Estado`; municipio → `Município`; codigo_residuo → `Cód. Resíduo`; residuo → `Desc. Resíduo`; ano → `Ano - destinação`; unidade → `Unidade`; destinacao → `Tipo de destinação`; outro_cnpj → `CNPJ do gerador do resíduo`
- Cabeçalho completo: `CNPJ do destinador` | `Razão Social do destinador` | `Estado` | `Município` | `Código da Categoria` | `Categoria de Atividade` | `Código do Detalhe` | `Detalhe` | `CNPJ do gerador do resíduo` | `Raz soc do gerador do resíduo` | `Cód. Resíduo` | `Desc. Resíduo` | `Ano - destinação` | `Quant. destinada` | `Unidade` | `Tipo de destinação` | `Situação Cadastral`

### armazenador (armazenador)

- Arquivo: 10.6 MB, separador `;`, codificação utf-8-sig
- Linhas: 27681; no Paraná: 841
- Campos: cnpj → `CNPJ do armazenador`; razao → `Razão Social do Armazenador`; uf → `Estado`; municipio → `Município`; codigo_residuo → `Cód. Resíduo`; residuo → `Desc. Resíduo`; ano → `Ano da destinação`; quantidade → `Qtd armaz/enviada p/dest final`; unidade → `Unidade`; destinacao → `Tipo de armazenamento/destin.`
- Cabeçalho completo: `CNPJ do armazenador` | `Razão Social do Armazenador` | `Estado` | `Município` | `CNPJ da emp. ger. do resíduo` | `Raz. soc. da emp. ger. do res.` | `Cód. Resíduo` | `Desc. Resíduo` | `Ano da destinação` | `CNPJ Armazenamento/Destinação` | `Raz. soc. empresa Armaz./Dest.` | `Qtd armaz/enviada p/dest final` | `Unidade` | `Tipo de armazenamento/destin.` | `Situação` | `Situação Cadastral`

### gerador (gerador)

- Arquivo: 825.9 MB, separador `;`, codificação utf-8-sig
- Linhas: 2811397; no Paraná: 215787
- Campos: cnpj → `CNPJ do gerador`; razao → `Razão Social do gerador`; uf → `Estado`; municipio → `Município`; codigo_residuo → `Cód. Resíduo`; residuo → `Tipo de Resíduo`; classe → `Classificação Resíduo`; ano → `Ano da geração`; quantidade → `Quantidade Gerada`; unidade → `Unidade`
- Cabeçalho completo: `CNPJ do gerador` | `Razão Social do gerador` | `Estado` | `Município` | `Código da Categoria` | `Categoria de Atividade` | `Código do Detalhe` | `Detalhe` | `Ano da geração` | `Cód. Resíduo` | `Tipo de Resíduo` | `Quantidade Gerada` | `Unidade` | `Classificação Resíduo` | `Situação Cadastral`

### produtos-reciclados (reciclador)

- Arquivo: 4.9 MB, separador `;`, codificação utf-8-sig
- Linhas: 23161; no Paraná: 2060
- Campos: cnpj → `CNPJ`; razao → `Razão Social`; uf → `Estado`; municipio → `Município`; residuo → `Tipo de Resíduo`; ano → `Ano`; quantidade → `Quantidade`; unidade → `Unidade de Medida`
- Cabeçalho completo: `CNPJ` | `Razão Social` | `Estado` | `Município` | `Ano` | `Tipo de Resíduo` | `Método de Reciclagem` | `Quantidade` | `Unidade de Medida` | `Empresa Destinadora do Resíduo` | `Situação Cadastral`

### pilhas-reciclador (reciclador)

- Arquivo: 0.9 MB, separador `;`, codificação utf-8-sig
- Linhas: 5586; no Paraná: 819
- Campos: cnpj → `CNPJ`; razao → `Razão_Social`; uf → `ESTADO`; municipio → `MUNICÍPIO`; residuo → `TIPO_DE_PILHA`; ano → `ANO`; quantidade → `QUANTIDADE_RECEBIDA`; destinacao → `TIPO_DE_DESTINAÇÃO`
- Cabeçalho completo: `CNPJ` | `Razão_Social` | `ESTADO` | `MUNICÍPIO` | `ANO` | `TIPO_DE_PILHA` | `MODELO` | `Peso_Unitário(kg)` | `QUANTIDADE_RECEBIDA` | `Peso_Total(kg)` | `CNPJ_ATERRO` | `TIPO_DE_DESTINAÇÃO` | `EMPRESA_FORNECEDORA`

### pilhas-fabricante-destinacao (destinador)

- Arquivo: 0.0 MB, separador `;`, codificação utf-8-sig
- Linhas: ?; no Paraná: ?
- Campos: cnpj → `CNPJ do destinador`; ano → `Ano do relatório`; destinacao → `Método de destinação e tratamento`
- Cabeçalho completo: `CNPJ` | `Ano do relatório` | `CNPJ do destinador` | `Número da licença de operação` | `Validade da licença de operação` | `Atividades constantes na licença de operação` | `Método de destinação e tratamento`
