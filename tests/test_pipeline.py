import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pandas as pd
import requests

from pipeline import (construir_painel, fisher, ler_zip_bis, carregar_painel,
                      atualizar_snapshot, ler_snapshot, mes_recomendado)


def bases():
    juros = pd.DataFrame({'FREQ': ['M', 'M', 'D'], 'REF_AREA': ['BR', 'US', 'US'],
                          'TIME_PERIOD': ['2026-09', '2026-09', '2026-09-30'], 'OBS_VALUE': [12, 5, 50]})
    cpi = pd.DataFrame({'FREQ': ['M'] * 4, 'REF_AREA': ['BR', 'US', 'US', 'FR'],
                       'TIME_PERIOD': ['2026-09', '2026-09', '2026-09', '2026-08'],
                       'OBS_VALUE': [5, 2, 200, 2], 'UNIT_MEASURE': ['771', '771', '628', '771']})
    return juros, cpi


class TestePainel(unittest.TestCase):
    def test_fisher_e_mes_em_comum(self):
        painel = construir_painel(*bases())
        self.assertEqual(set(painel.pais_codigo), {'BR', 'US'})
        br = painel.loc[painel.pais_codigo.eq('BR')].iloc[0]
        self.assertAlmostEqual(br.juros_reais, (1.12 / 1.05 - 1) * 100)
        self.assertEqual(br.mes.strftime('%Y-%m'), '2026-09')

    def test_formato_rotulado_real_do_bis(self):
        juros, cpi = bases()
        for df in [juros, cpi]:
            for c in ['FREQ', 'REF_AREA', 'UNIT_MEASURE']:
                if c in df:
                    df[c] = df[c].astype(str) + ': Descrição'
            df.rename(columns={c: c + ': Rótulo' for c in df.columns}, inplace=True)
        self.assertEqual(len(construir_painel(juros, cpi)), 2)

    def test_duplicatas_conflitantes_interrompem(self):
        juros, cpi = bases()
        juros = pd.concat([juros, juros.iloc[[0]].assign(OBS_VALUE=99)])
        with self.assertRaisesRegex(ValueError, 'conflitantes'):
            construir_painel(juros, cpi)

    def test_duplicatas_identicas_sao_removidas(self):
        juros, cpi = bases()
        self.assertEqual(len(construir_painel(pd.concat([juros, juros]), cpi)), 2)

    def test_inflacao_invalida_e_valores_ausentes(self):
        juros, cpi = bases()
        cpi.loc[0, 'OBS_VALUE'] = -100
        juros['OBS_VALUE'] = juros['OBS_VALUE'].astype(float)
        juros.loc[1, 'OBS_VALUE'] = float('inf')
        self.assertTrue(construir_painel(juros, cpi).empty)

    def test_periodos_malformados_nao_viram_meses(self):
        juros, cpi = bases()
        juros.loc[0, 'TIME_PERIOD'] = '2026-09-10'
        juros.loc[1, 'REF_AREA'] = None
        self.assertTrue(construir_painel(juros, cpi).empty)

    def test_meses_nao_sao_carregados(self):
        juros, cpi = bases()
        cpi.loc[0, 'TIME_PERIOD'] = '2026-08'
        self.assertEqual(set(construir_painel(juros, cpi).pais_codigo), {'US'})

    def test_multiplicador_de_unidade(self):
        juros, cpi = bases()
        juros['UNIT_MULT'] = '1: Tens'
        self.assertEqual(construir_painel(juros, cpi).iloc[0].juros_nominais, 120)

    def test_zip_bis_rotulado(self):
        conteudo = io.BytesIO()
        with ZipFile(conteudo, 'w') as z:
            z.writestr('dados.csv', 'FREQ:Frequency,REF_AREA:Reference area,TIME_PERIOD:Time period,OBS_VALUE:Value\nM: Monthly,BR: Brazil,2026-09,12\nD: Daily,BR: Brazil,2026-09-30,12\n')
        df = ler_zip_bis(conteudo.getvalue())
        self.assertEqual(len(df), 1)
        self.assertIn('FREQ', df)

    def test_fisher_hiperinflacao_deflacao_e_limites(self):
        self.assertAlmostEqual(fisher(3.5, 22), -15.1639344262)
        self.assertAlmostEqual(fisher(-1, -2), (0.99 / 0.98 - 1) * 100)
        for invalido in [-100, -101, float('inf'), float('nan')]:
            with self.assertRaises(ValueError):
                fisher(12, invalido)

    def test_mes_recomendado_evitar_cobertura_parcial(self):
        dados = pd.DataFrame({'mes': [pd.Timestamp('2026-08-01')] * 10 + [pd.Timestamp('2026-09-01')],
                              'pais_codigo': list('ABCDEFGHIJ') + ['A']})
        self.assertEqual(mes_recomendado(dados), pd.Timestamp('2026-08-01'))


class TesteSnapshot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.caminho = Path(self.tmp.name) / 'painel.zip'

    def criar_snapshot(self):
        with patch('pipeline.obter_csv_bis', side_effect=bases()):
            return atualizar_snapshot(self.caminho)

    def test_roundtrip_e_cache_sem_rede(self):
        painel, meta = self.criar_snapshot()
        restaurado, meta2 = ler_snapshot(self.caminho)
        self.assertEqual(len(restaurado), len(painel))
        self.assertEqual(meta2, meta)
        with patch('pipeline.obter_csv_bis') as obter:
            _, resultado = carregar_painel(caminho=self.caminho)
        obter.assert_not_called()
        self.assertEqual(resultado['modo'], 'cache')

    def test_falha_preserva_snapshot_e_exibe_aviso(self):
        self.criar_snapshot()
        original = self.caminho.read_bytes()
        with patch('pipeline.obter_csv_bis', side_effect=requests.ConnectionError('Sem rede')):
            painel, meta = carregar_painel(forcar=True, caminho=self.caminho)
        self.assertEqual(meta['modo'], 'offline')
        self.assertIn('Sem rede', meta['aviso'])
        self.assertEqual(self.caminho.read_bytes(), original)
        self.assertEqual(len(painel), 2)

    def test_sem_cache_erro_nao_inventa_dados(self):
        with patch('pipeline.obter_csv_bis', side_effect=requests.ConnectionError('Sem rede')):
            with self.assertRaises(requests.ConnectionError):
                carregar_painel(caminho=self.caminho)

    def test_cache_corrompido_tenta_rede(self):
        self.caminho.write_bytes(b'arquivo invalido')
        with patch('pipeline.obter_csv_bis', side_effect=bases()):
            _, meta = carregar_painel(caminho=self.caminho)
        self.assertEqual(meta['modo'], 'online')


if __name__ == '__main__':
    unittest.main()
