"""Observatório Global de Juros — aplicação interativa com dados oficiais BIS."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from economias import pais_nome, iso3
from pipeline import carregar_painel, fisher, mes_recomendado

st.set_page_config(page_title='Observatório Global de Juros', page_icon='◎', layout='wide')
INDICADORES = {'juros_reais': 'Juros reais', 'juros_nominais': 'Juros nominais', 'inflacao_12m': 'Inflação em 12 meses'}
CORES = ['#087f8c', '#d5883b', '#5762a5', '#d45e6a', '#557c55']
ROTULOS = {'mes': 'Mês', 'pais': 'Economia', 'juros_reais': 'Juros reais (%)',
           'juros_nominais': 'Juros nominais (%)', 'inflacao_12m': 'Inflação 12m (%)'}
px.defaults.template = 'plotly_white'
px.defaults.color_discrete_sequence = CORES
st.markdown('''<style>
.stApp {background:#f5f7fa; color:#172b40;}
.block-container {padding-top:4.5rem; padding-bottom:2rem; max-width:1500px;}
h1,h2,h3 {color:#152c43; letter-spacing:-.035em;}
[data-testid="stSidebar"] {background:#eaf0f4;}
[data-testid="stMetric"] {background:white; border:1px solid #e0e7ed; padding:18px; border-radius:12px;}
[data-testid="stMetricLabel"] {color:#607589;}
[data-testid="stMetricValue"] {color:#087f8c;}
.kicker {font-size:12px; letter-spacing:3px; color:#087f8c; font-weight:700; margin-bottom:8px;}
</style>''', unsafe_allow_html=True)


def porcentagem(valor):
    return f'{valor:,.2f}%'.replace(',', '_').replace('.', ',').replace('_', '.')


def figura_layout(fig, altura=480):
    fig.update_layout(height=altura, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      font=dict(family='Arial', color='#172b40'), margin=dict(l=20, r=20, t=35, b=30),
                      legend_title_text='', hovermode='closest')
    return fig


def csv(df):
    return df.to_csv(index=False, sep=';', decimal=',', date_format='%Y-%m-%d').encode('utf-8-sig')


@st.cache_data(ttl=12 * 3600, show_spinner='Consultando séries oficiais do BIS…')
def carregar_dados():
    painel, meta = carregar_painel()
    painel['pais'] = painel['pais_codigo'].map(pais_nome)
    painel['iso3'] = painel['pais_codigo'].map(iso3)
    return painel, meta


st.markdown('<div class="kicker">ECONOMIA INTERNACIONAL · DADOS ABERTOS</div>', unsafe_allow_html=True)
st.title('Observatório Global de Juros')
st.markdown('Explore como **juros e inflação** se combinam em diferentes economias. Compare o mesmo mês, acompanhe ciclos e calcule a taxa real.')

with st.sidebar:
    st.markdown('### ◎ Observatório')
    st.caption('POLÍTICA MONETÁRIA GLOBAL')
    atualizar = st.button('↻ Atualizar dados do BIS', use_container_width=True)
    if atualizar:
        with st.spinner('Baixando e validando as duas bases…'):
            try:
                _, status = carregar_painel(forcar=True)
                carregar_dados.clear()
                if status['modo'] == 'offline':
                    st.warning('Fonte indisponível. A cópia anterior foi preservada.')
            except Exception:
                st.error('Não foi possível atualizar. Confira a conexão e tente novamente.')

try:
    dados, meta = carregar_dados()
except Exception as erro:
    st.error('Não foi possível consultar o BIS e não há cópia local válida. Verifique a conexão e clique em atualizar.')
    with st.expander('Detalhes técnicos'):
        st.code(str(erro))
    st.stop()

consulta = pd.Timestamp(meta['consultado_em']).tz_convert('America/Fortaleza')
if meta['modo'] == 'offline':
    st.warning(f"Fonte indisponível. Exibindo cópia local consultada em {consulta:%d/%m/%Y às %H:%M} (Fortaleza). Os dados podem estar desatualizados.")

with st.sidebar:
    st.divider()
    meses = sorted(dados['mes'].unique(), reverse=True)
    padrao = mes_recomendado(dados)
    mes = pd.Timestamp(st.selectbox('Mês de referência', meses, index=meses.index(padrao),
                                   format_func=lambda m: pd.Timestamp(m).strftime('%m/%Y'), key='mes'))
    st.caption('O mês inicial preserva pelo menos 80% da maior cobertura nos últimos 12 meses disponíveis.')
    disponiveis = sorted(dados.loc[dados['mes'].eq(mes), 'pais_codigo'], key=pais_nome)
    filtro = st.multiselect('Filtrar economias do panorama', disponiveis, format_func=pais_nome,
                            placeholder='Todas as economias do mês', key='filtro_economias')
    st.caption('Filtro aplicado ao panorama, ranking e mapa. O histórico possui seleção própria.')
    st.divider()
    st.caption(f'Consulta ao BIS: {consulta:%d/%m/%Y · %H:%M} (Fortaleza)')
    st.caption(f"Último mês conjunto na base: {dados['mes'].max():%m/%Y}")
    st.caption('Cache de 12 horas · sem preenchimento de lacunas')
    st.link_button('Abrir fonte oficial ↗', 'https://data.bis.org/topics/CBPOL')

recorte_total = dados.loc[dados['mes'].eq(mes)].copy()
recorte = recorte_total.loc[recorte_total['pais_codigo'].isin(filtro)].copy() if filtro else recorte_total.copy()
recorte = recorte.sort_values('juros_reais', ascending=False)
st.subheader(f'Panorama internacional · {mes:%m/%Y}')
st.caption(f'{len(recorte)} de {len(recorte_total)} economias com juros e inflação observados neste mês. Taxas em % a.a.; inflação acumulada em 12 meses.')
c1, c2, c3, c4 = st.columns(4)
c1.metric('Economias', len(recorte), help='Economias comparáveis no mês e filtro selecionados.')
c2.metric('Juro nominal', porcentagem(recorte['juros_nominais'].median()), help='Mediana sem ponderação das taxas nominais selecionadas.')
c3.metric('Inflação 12m', porcentagem(recorte['inflacao_12m'].median()), help='Mediana sem ponderação da inflação em 12 meses.')
c4.metric('Juro real', porcentagem(recorte['juros_reais'].median()), help='Mediana sem ponderação dos juros reais de Fisher.')
st.caption('Medianas sem ponderação das economias selecionadas. Juros reais calculados com inflação passada; não medem o grau de restrição em relação à taxa neutra.')

ranking_tab, mapa_tab, historico_tab, simulador_tab, metodo_tab = st.tabs(
    ['Ranking internacional', 'Mapa global', 'Análise histórica', 'Simulador de Fisher', 'Metodologia e cobertura'])

with ranking_tab:
    indicador = st.selectbox('Comparar por', list(INDICADORES), format_func=INDICADORES.get, key='ranking_indicador')
    ordem = st.toggle('Mostrar menores taxas primeiro', value=False)
    ranking = recorte.sort_values(indicador, ascending=ordem).reset_index(drop=True)
    ranking['posição'] = ranking.index + 1
    barras = ranking.sort_values(indicador, ascending=not ordem)
    fig = px.bar(barras, x=indicador, y='pais', orientation='h', color=indicador,
                 color_continuous_scale=['#c46c55', '#e8ecef', '#087f8c'], color_continuous_midpoint=0,
                 hover_data={'juros_nominais': ':.2f', 'inflacao_12m': ':.2f', 'juros_reais': ':.2f'}, labels=ROTULOS)
    fig.update_layout(coloraxis_showscale=False, yaxis_title=None, xaxis_title='Taxa (%)')
    fig.add_vline(x=0, line_color='#93a4b4', line_width=1)
    st.plotly_chart(figura_layout(fig, max(400, len(ranking) * 25)), use_container_width=True)
    st.dataframe(ranking[['posição', 'pais', 'pais_codigo', 'juros_nominais', 'inflacao_12m', 'juros_reais']],
                 column_config={'posição': 'Posição', 'pais': 'Economia', 'pais_codigo': 'Código BIS',
                    **{c: st.column_config.NumberColumn(ROTULOS[c], format='%.2f') for c in INDICADORES}},
                 hide_index=True, use_container_width=True)
    st.download_button('↓ Exportar ranking em CSV', csv(ranking.drop(columns='iso3')),
                       file_name=f'ranking_juros_{mes:%Y_%m}.csv', mime='text/csv')

with mapa_tab:
    st.markdown('#### A geografia dos juros reais')
    no_mapa = recorte.dropna(subset=['iso3'])
    if not no_mapa.empty:
        limite = max(1.0, float(no_mapa['juros_reais'].abs().max()))
        fig = px.choropleth(no_mapa, locations='iso3', color='juros_reais', hover_name='pais',
                            hover_data={'iso3': False, 'juros_nominais': ':.2f', 'inflacao_12m': ':.2f', 'juros_reais': ':.2f'},
                            labels=ROTULOS, color_continuous_scale=['#c46c55', '#f1f3f5', '#087f8c'],
                            range_color=(-limite, limite), projection='natural earth')
        fig.update_geos(showframe=False, showcoastlines=False, showcountries=True, countrycolor='white',
                        showland=True, landcolor='#dce3e9', bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(figura_layout(fig, 560), use_container_width=True)
    else:
        st.info('Nenhuma economia selecionada pode ser representada por um país no mapa.')
    st.caption('Cinza indica ausência de dados neste mês. A Zona do Euro é um agregado e não é pintada nos países membros. A escala é simétrica em torno de zero.')

with historico_tab:
    codigos = sorted(dados['pais_codigo'].unique(), key=pais_nome)
    selecao = st.multiselect('Compare até cinco economias', codigos, default=[c for c in ['BR', 'US', 'XM'] if c in codigos],
                            format_func=pais_nome, max_selections=5, key='historico_economias')
    indicador_hist = st.radio('Indicador histórico', list(INDICADORES), format_func=INDICADORES.get, horizontal=True)
    minimo = dados['mes'].min().date()
    maximo = mes.date()
    inicio_padrao = max(minimo, (mes - pd.DateOffset(years=10)).date())
    periodo = st.date_input('Intervalo de análise', value=(inicio_padrao, maximo), min_value=minimo,
                            max_value=maximo, format='DD/MM/YYYY')
    if len(periodo) == 2 and selecao:
        inicio = pd.Timestamp(periodo[0]).to_period('M').to_timestamp()
        fim = pd.Timestamp(periodo[1]).to_period('M').to_timestamp()
        serie = dados.loc[dados['pais_codigo'].isin(selecao) & dados['mes'].between(inicio, fim)].copy()
        if not serie.empty:
            # Reindexa para que o gráfico interrompa a linha em meses sem observação.
            grade = pd.MultiIndex.from_product([selecao, pd.date_range(inicio, fim, freq='MS')], names=['pais_codigo', 'mes'])
            grafico = serie.set_index(['pais_codigo', 'mes']).reindex(grade).reset_index()
            grafico['pais'] = grafico['pais_codigo'].map(pais_nome)
            fig = px.line(grafico, x='mes', y=indicador_hist, color='pais', labels=ROTULOS)
            fig.update_traces(connectgaps=False)
            fig.update_layout(hovermode='x unified', yaxis_title='Taxa (%)', xaxis_title=None)
            st.plotly_chart(figura_layout(fig), use_container_width=True)
            st.markdown('#### Variação em pontos percentuais')
            st.caption('Diferença contra exatamente 3, 6 e 12 meses antes, no último mês observado de cada economia dentro do intervalo. Lacunas aparecem sem valor.')
            linhas = []
            for codigo in selecao:
                historico = dados.loc[dados['pais_codigo'].eq(codigo)].set_index('mes').sort_index()
                trecho = historico.loc[(historico.index >= inicio) & (historico.index <= fim)]
                if trecho.empty:
                    continue
                ultimo = trecho.index.max()
                valor = historico.at[ultimo, indicador_hist]
                linha = {'Economia': pais_nome(codigo), 'Referência': ultimo.strftime('%m/%Y'), 'Taxa (%)': valor}
                for n in [3, 6, 12]:
                    passado = historico[indicador_hist].get(ultimo - pd.DateOffset(months=n))
                    linha[f'{n} meses (p.p.)'] = valor - passado if passado is not None else None
                linhas.append(linha)
            st.dataframe(pd.DataFrame(linhas), hide_index=True, use_container_width=True)
            st.download_button('↓ Exportar séries selecionadas', csv(serie.drop(columns='iso3')),
                               file_name='series_historicas_juros.csv', mime='text/csv')
        else:
            st.info('Não há observações para as economias e o intervalo selecionados.')
    else:
        st.info('Selecione uma economia e as duas datas do intervalo para visualizar as séries.')

with simulador_tab:
    st.markdown('#### O que a inflação faz com os juros?')
    st.caption('Cenário hipotético, independente das cotações do ranking.')
    a, b, c = st.columns(3)
    nominal = a.number_input('Juros nominais (% a.a.)', value=12.0, min_value=-99.0, max_value=10000.0, step=0.25, key='sim_nominal')
    inflacao = b.number_input('Inflação em 12 meses (%)', value=5.0, min_value=-99.99, max_value=100000.0, step=0.25, key='sim_inflacao')
    real = fisher(nominal, inflacao)
    c.metric('Juros reais · Fisher', porcentagem(real))
    st.latex(r'r = \left(\frac{1+i/100}{1+\pi/100}-1\right)\times100')
    st.write(f'A subtração simples resulta em **{porcentagem(nominal - inflacao)}**. Fisher considera a razão entre os fatores de juros e inflação.')
    cenarios = pd.DataFrame({'inflacao_12m': [inflacao + x / 10 for x in range(-100, 101) if inflacao + x / 10 > -100]})
    cenarios['juros_reais'] = fisher(nominal, cenarios['inflacao_12m'])
    fig = px.line(cenarios, x='inflacao_12m', y='juros_reais', labels=ROTULOS)
    fig.add_hline(y=0, line_dash='dot', line_color='#93a4b4')
    fig.add_scatter(x=[inflacao], y=[real], mode='markers', marker=dict(size=12, color='#d5883b'), name='Seu cenário')
    st.plotly_chart(figura_layout(fig, 350), use_container_width=True)
    st.caption('Mantendo os juros nominais fixos, o gráfico varia a inflação em até 10 pontos percentuais ao redor do cenário escolhido.')

with metodo_tab:
    st.markdown('''
#### Como ler o observatório
- **Juros nominais:** taxa de política monetária BIS (`WS_CBPOL`), frequência mensal, fim do período. O instrumento e o tratamento de bandas variam por economia.
- **Inflação:** variação do IPC em 12 meses (`WS_LONG_CPI`, unidade `771`), sem ajuste sazonal. O índice e a cobertura podem variar entre países.
- **Juros reais:** equação exata de Fisher, combinando juros nominais e inflação passada no mesmo mês. É uma aproximação retrospectiva, não um retorno efetivo de investimento nem uma previsão.
- **Interpretação:** um valor real mais alto não basta para concluir que a política é mais restritiva. Isso exige comparar com a taxa real neutra de cada economia, que não integra esta versão.

#### Regras de comparação
Não há interpolação nem carregamento do último valor. Ranking e mapa usam o mesmo mês. Duplicatas idênticas são removidas; valores conflitantes interrompem a atualização. Séries históricas nacionais anteriores ao euro podem aparecer quando existem nas duas bases; a taxa do BCE não é replicada para os membros atuais.

O mês inicial exige pelo menos 80% da maior cobertura dos últimos 12 meses disponíveis. Você pode selecionar meses com menor cobertura; a quantidade de economias aparece no panorama. A data de consulta é diferente do mês de referência e da data de publicação pelo BIS.

#### Fontes oficiais
[BIS · Política monetária](https://data.bis.org/topics/CBPOL) ·
[BIS · Preços ao consumidor](https://data.bis.org/topics/CPI) ·
[Downloads](https://data.bis.org/bulkdownload) ·
[Termos de uso](https://data.bis.org/help/legal)

Plataforma independente e educacional, sem afiliação ou endosso do BIS. Fonte: Bank for International Settlements.
''')
    st.markdown('#### Cobertura ao longo do tempo')
    cobertura = dados.groupby('mes')['pais_codigo'].nunique().rename('Economias').reset_index()
    st.plotly_chart(figura_layout(px.area(cobertura, x='mes', y='Economias', labels={'mes': 'Mês'}), 280), use_container_width=True)
    qualidade = dados.groupby(['pais_codigo', 'pais']).agg(primeiro_mes=('mes', 'min'), ultimo_mes=('mes', 'max'), observacoes=('mes', 'count')).reset_index()
    st.dataframe(qualidade, hide_index=True, use_container_width=True)
    st.download_button('↓ Exportar cobertura', csv(qualidade), file_name='cobertura_bis.csv', mime='text/csv')
    st.download_button('↓ Exportar painel completo', csv(dados.drop(columns='iso3')), file_name='painel_bis_completo.csv', mime='text/csv')

st.divider()
st.caption('OBSERVATÓRIO GLOBAL DE JUROS · Fonte: BIS · Dados mensais observados')
