# Observatório Global de Juros

Dashboard de pesquisa econômica em **Python + Streamlit + Plotly**, com taxas de política monetária, inflação em 12 meses e juros reais retrospectivos. Fonte exclusiva desta versão: BIS.

## Abrir no Windows

Com Python 3.11 ou mais recente instalado, dê dois cliques em **iniciar_windows.bat**. O iniciador cria um ambiente isolado em `.venv`, instala as dependências e abre o dashboard. Se o navegador não abrir, acesse http://localhost:8501. Mantenha a janela do terminal aberta enquanto usa o painel; `Ctrl+C` encerra a aplicação.

A primeira consulta precisa de internet. Depois de uma coleta bem-sucedida, o painel guarda uma cópia local e consegue exibi-la quando o BIS fica indisponível, com aviso e data de consulta visíveis.

## Instalação manual

No PowerShell, dentro desta pasta:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

No Linux/macOS, crie o ambiente com `python3 -m venv .venv` e use `.venv/bin/python` nos comandos seguintes.

## O que está implementado

- Panorama do mês com cobertura e medianas sem ponderação.
- Ranking de juros reais, juros nominais e inflação; filtro por economia e exportação CSV.
- Mapa com escala de juros reais centrada em zero e indicação de ausência de dados.
- Histórico de até cinco economias, seleção de intervalo e variações em 3, 6 e 12 meses, em pontos percentuais.
- Simulador de Fisher com cenário hipotético e sensibilidade à inflação.
- Metodologia, cobertura por economia, exportação do painel completo e data da consulta.
- Cache persistente de 12 horas, atualização manual e preservação da última coleta válida.

CSVs usam UTF-8 com BOM, separador `;` e vírgula decimal para facilitar a abertura no Excel em português. Taxas nos arquivos continuam sendo números em porcentagem, e não frações decimais.

## Fontes e metodologia

- [BIS · Central bank policy rates](https://data.bis.org/topics/CBPOL), conjunto `WS_CBPOL`: frequência mensal, taxa de fim do período, unidade `368` (% ao ano).
- [BIS · Consumer prices](https://data.bis.org/topics/CPI), conjunto `WS_LONG_CPI`: frequência mensal, unidade `771` (variação em 12 meses).
- [Arquivos oficiais](https://data.bis.org/bulkdownload).

Os CSVs flat atuais incluem códigos acompanhados de descrições, por exemplo `FREQ:Frequency` e `M: Monthly`. O importador aceita esse formato e o formato com códigos simples, respeita o multiplicador de unidade, elimina valores ausentes/não finitos e verifica a unicidade por economia/mês. Duplicatas idênticas são removidas; valores conflitantes interrompem a atualização.

A taxa real usa Fisher:

```text
real (%) = 100 * ((1 + nominal / 100) / (1 + inflação_12m / 100) - 1)
```

A inflação deve ser maior que -100%. Não há interpolação ou uso do último dado disponível para preencher outro mês. Ranking e mapa comparam exclusivamente observações do mesmo mês. O mês inicial é o mais recente com pelo menos 80% da maior cobertura nos últimos 12 meses disponíveis.

O histórico interrompe as linhas nos meses sem observação. As variações usam exatamente 3, 6 e 12 meses anteriores à última observação da economia dentro do intervalo; não substituem lacunas. Essa tabela pode ter meses finais diferentes por economia, explicitados na coluna de referência, e não deve ser confundida com o ranking mensal.

A Zona do Euro (`XM`) é um agregado e não é desenhada como um país. As séries nacionais anteriores ao euro permanecem quando oferecidas pelo BIS; não se replica a taxa do BCE para os membros atuais.

**Limitações:** juros reais calculados com inflação passada são uma aproximação retrospectiva, não uma projeção de retorno. Comparar o grau de restrição monetária exige também estimativas de taxa real neutra. Instrumentos de política monetária e índices de preços diferem entre economias. Medianas não representam uma taxa mundial. Esta versão não inclui expectativas do FMI nem estima juros neutros.

## Atualização e armazenamento

```powershell
.\.venv\Scripts\python.exe pipeline.py --atualizar
```

Esse comando consulta as duas bases, valida o painel e substitui `data/painel_bis.zip` apenas após sucesso. O ZIP contém `painel.csv` e `metadados.json` com URLs de origem, instante de consulta em UTC, cobertura e último mês conjunto. A interface exibe o instante de consulta no fuso de Fortaleza. A data de consulta não é a data de publicação pelo BIS.

Se a atualização falhar e houver snapshot válido, a interface usa a cópia anterior e avisa. O comando de atualização retorna código 1 nesse caso, para permitir detectar a falha em execuções agendadas. Sem snapshot válido, o app exibe o erro e não produz valores substitutos. O botão de atualização ignora ambos os caches.

Os dados locais e o ambiente virtual estão fora do Git. O gráfico de mapa pode precisar de internet no navegador para obter a geometria geográfica usada pelo Plotly; tabelas e cálculos continuam disponíveis com o snapshot local.

## Verificação

Com as dependências instaladas, faça uma coleta e execute:

```powershell
.\.venv\Scripts\python.exe pipeline.py --atualizar
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes de pipeline usam dados sintéticos pequenos, incluindo o formato real de cabeçalhos do BIS. O teste de interface utiliza o snapshot local e verifica filtros, períodos e simulador via Streamlit AppTest; ele requer uma primeira coleta válida.

## Estrutura

```text
app.py                  Interface e gráficos
pipeline.py             Download, normalização, cálculo e snapshots
economias.py            Nomes em português e códigos de mapa
requirements.txt        Dependências de execução e testes
iniciar_windows.bat     Ambiente isolado e inicialização no Windows
.streamlit/config.toml  Tema e configuração
tests/                  Testes do pipeline e da interface
data/                   Cache local (ignorado pelo Git)
```

## Publicação

Para hospedar em um serviço compatível com Streamlit, configure `app.py` como entrada e instale `requirements.txt`. A hospedagem precisa de acesso HTTPS aos arquivos BIS. O disco pode ser efêmero: nesse caso o snapshot é recriado na próxima coleta. Esta entrega prepara a execução local; nenhuma publicação externa foi feita.

## Próximas etapas

1. Acrescentar expectativas de inflação e separar claramente a medida prospectiva da retrospectiva.
2. Ampliar cobertura com fontes oficiais adicionais e resolver diferenças metodológicas.
3. Analisar volatilidade, correlações e episódios monetários com escolhas estatísticas documentadas.
4. Configurar coleta agendada e histórico de revisões em armazenamento durável.

## Atribuição

Dados: **Bank for International Settlements (BIS)**. Projeto independente e educacional, sem afiliação ou endosso institucional. Consulte os [termos de uso do BIS](https://data.bis.org/help/legal) antes de redistribuir dados ou publicar derivados.
