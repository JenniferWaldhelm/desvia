# Coleta automática por cidade

Ação do GitHub **Buscar empresas de uma cidade** (aba Actions > Buscar empresas de uma cidade > Run workflow).
Digite o município com acento (ex.: `Ibiporã`). Em poucos minutos aparecem aqui:

- `<cidade>.csv`: empresas de resíduos no formato da aba Pontos, mais `Situação CNPJ` e `Já na base`
- `<cidade>-resumo.md`: contagens e avisos

Fontes: IAT GeoPR (licenças estaduais e coordenadas), CTF/IBAMA (dados abertos) e Receita Federal (BrasilAPI).
Ficam de fora autorizações automáticas (geradores), transporte sem resíduos e serviços de água e esgoto.
Nada aqui muda o site: a revisão e a cópia para a planilha mestra continuam manuais.
