"""Valida inicialização e interações reais do Streamlit, usando snapshot BIS local."""
import unittest
from streamlit.testing.v1 import AppTest
from pipeline import ler_snapshot


class TesteAplicacao(unittest.TestCase):
    def test_fluxo_do_dashboard(self):
        app = AppTest.from_file('app.py', default_timeout=30).run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual(len(app.tabs), 5)
        self.assertEqual(len(app.metric), 5)
        app.multiselect(key='filtro_economias').set_value(['BR']).run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual(app.metric[0].value, '1')
        app.selectbox(key='ranking_indicador').set_value('inflacao_12m').run()
        self.assertEqual(list(app.exception), [])
        app.number_input(key='sim_nominal').set_value(3.5)
        app.number_input(key='sim_inflacao').set_value(22.0).run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual(app.metric[4].value, '-15,16%')
        app.multiselect(key='historico_economias').set_value([]).run()
        self.assertEqual(list(app.exception), [])
        # Período inicial de menor cobertura e sem as seleções usuais.
        app.selectbox(key='mes').set_value(ler_snapshot()[0]['mes'].min()).run()
        self.assertEqual(list(app.exception), [])


if __name__ == '__main__':
    unittest.main()
