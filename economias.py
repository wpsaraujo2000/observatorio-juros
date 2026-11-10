"""Nomes das economias e códigos cartográficos, sem replicar o agregado do euro."""
import pycountry

NOMES = {
    'AR': 'Argentina', 'AT': 'Áustria', 'AU': 'Austrália', 'BE': 'Bélgica',
    'BR': 'Brasil', 'CA': 'Canadá', 'CH': 'Suíça', 'CL': 'Chile', 'CN': 'China',
    'CO': 'Colômbia', 'CZ': 'Tchéquia', 'DE': 'Alemanha', 'DK': 'Dinamarca',
    'ES': 'Espanha', 'FR': 'França', 'GB': 'Reino Unido', 'GR': 'Grécia',
    'HK': 'Hong Kong', 'HR': 'Croácia', 'HU': 'Hungria', 'ID': 'Indonésia',
    'IL': 'Israel', 'IN': 'Índia', 'IS': 'Islândia', 'IT': 'Itália', 'JP': 'Japão',
    'KR': 'Coreia do Sul', 'KW': 'Kuwait', 'MA': 'Marrocos', 'MK': 'Macedônia do Norte',
    'MX': 'México', 'MY': 'Malásia', 'NL': 'Países Baixos', 'NO': 'Noruega',
    'NZ': 'Nova Zelândia', 'PE': 'Peru', 'PH': 'Filipinas', 'PL': 'Polônia',
    'PT': 'Portugal', 'RO': 'Romênia', 'RS': 'Sérvia', 'RU': 'Rússia',
    'SA': 'Arábia Saudita', 'SE': 'Suécia', 'TH': 'Tailândia', 'TR': 'Turquia',
    'TW': 'Taiwan', 'US': 'Estados Unidos', 'XK': 'Kosovo', 'XM': 'Zona do Euro',
    'ZA': 'África do Sul',
}


def pais_nome(codigo):
    if codigo in NOMES:
        return NOMES[codigo]
    pais = pycountry.countries.get(alpha_2=codigo)
    return pais.name if pais else codigo


def iso3(codigo):
    pais = pycountry.countries.get(alpha_2=codigo)
    return pais.alpha_3 if pais else None
