"""Dados oficiais BIS: normalização SDMX, alinhamento mensal e cache auditável."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

URLS = {
    "juros": "https://data.bis.org/static/bulk/WS_CBPOL_csv_flat.zip",
    "inflacao": "https://data.bis.org/static/bulk/WS_LONG_CPI_csv_flat.zip",
}
COLUNAS = {"FREQ", "REF_AREA", "TIME_PERIOD", "OBS_VALUE"}
CACHE = Path(__file__).resolve().parent / "data" / "painel_bis.zip"
SCHEMA = 1


def _coluna(nome: str) -> str:
    return str(nome).lstrip("\ufeff").split(":", 1)[0].strip().upper()


def _codigo(serie: pd.Series) -> pd.Series:
    return serie.astype("string").str.split(":", n=1).str[0].str.strip()


def _cabecalhos(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=_coluna).copy()
    if not df.columns.is_unique:
        raise ValueError("Cabeçalhos BIS ambíguos após normalização.")
    if not COLUNAS.issubset(df.columns):
        raise ValueError(f"Colunas ausentes: {sorted(COLUNAS.difference(df.columns))}")
    return df


def ler_zip_bis(conteudo: bytes) -> pd.DataFrame:
    """Aceita CSV flat com códigos simples ou códigos acompanhados de rótulos."""
    with ZipFile(BytesIO(conteudo)) as arquivo:
        for nome in sorted(arquivo.namelist()):
            if not nome.lower().endswith(".csv"):
                continue
            with arquivo.open(nome) as entrada:
                colunas = pd.read_csv(entrada, nrows=0, encoding="utf-8-sig").columns
            if not COLUNAS.issubset({_coluna(c) for c in colunas}):
                continue
            manter = COLUNAS | {"UNIT_MEASURE", "UNIT_MULT", "OBS_STATUS"}
            with arquivo.open(nome) as entrada:
                df = pd.read_csv(entrada, usecols=lambda c: _coluna(c) in manter,
                                 dtype="string", encoding="utf-8-sig")
            df = _cabecalhos(df)
            return df.loc[_codigo(df["FREQ"]).eq("M")].copy()
    raise ValueError("O ZIP não contém o CSV de observações esperado.")


def obter_csv_bis(tipo: str) -> pd.DataFrame:
    if tipo not in URLS:
        raise ValueError(f"Tipo não reconhecido: {tipo}")
    with requests.Session() as sessao:
        repeticoes = Retry(total=2, backoff_factor=0.5,
                           status_forcelist=[429, 500, 502, 503, 504])
        sessao.mount("https://", HTTPAdapter(max_retries=repeticoes))
        resposta = sessao.get(URLS[tipo], timeout=(15, 90),
                              headers={"User-Agent": "ObservatorioGlobalJuros/1.0"})
        resposta.raise_for_status()
        return ler_zip_bis(resposta.content)


def _normalizar_mensal(df: pd.DataFrame) -> pd.DataFrame:
    df = _cabecalhos(df)
    df = df.loc[_codigo(df["FREQ"]).eq("M")].copy()
    df["pais_codigo"] = _codigo(df["REF_AREA"]).str.upper()
    periodos = df["TIME_PERIOD"].astype("string").str.strip()
    df["mes"] = pd.to_datetime(periodos.where(periodos.str.fullmatch(r"\d{4}-\d{2}")),
                                format="%Y-%m", errors="coerce")
    df["valor"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    if "UNIT_MULT" in df:
        mult = pd.to_numeric(_codigo(df["UNIT_MULT"]), errors="coerce")
        if mult.isna().any():
            raise ValueError("Multiplicador de unidade ausente ou inválido.")
        df["valor"] *= 10.0 ** mult
    validos = (df["pais_codigo"].str.fullmatch(r"[A-Z]{2}", na=False)
               & np.isfinite(df["valor"].astype(float)))
    return df.loc[validos].dropna(subset=["mes", "valor"])


def fisher(juros, inflacao):
    """Entradas e saída em porcentagem; inflação deve ser maior que -100%."""
    if np.any(np.asarray(inflacao) <= -100):
        raise ValueError("Inflação deve ser maior que -100%.")
    if not np.all(np.isfinite(juros)) or not np.all(np.isfinite(inflacao)):
        raise ValueError("Taxas devem ser finitas.")
    return ((1 + juros / 100) / (1 + inflacao / 100) - 1) * 100


def _serie_unica(df: pd.DataFrame, indicador: str) -> pd.DataFrame:
    df = df[["pais_codigo", "mes", "valor"]].drop_duplicates()
    if df.duplicated(["pais_codigo", "mes"]).any():
        raise ValueError(f"Valores conflitantes para a mesma economia/mês em {indicador}.")
    return df.rename(columns={"valor": indicador})


def construir_painel(juros_brutos: pd.DataFrame, inflacao_bruta: pd.DataFrame) -> pd.DataFrame:
    juros = _cabecalhos(juros_brutos)
    if "UNIT_MEASURE" in juros:
        juros = juros.loc[_codigo(juros["UNIT_MEASURE"]).eq("368")]
    cpi = _cabecalhos(inflacao_bruta)
    if "UNIT_MEASURE" not in cpi:
        raise ValueError("A base de inflação não tem a dimensão UNIT_MEASURE.")
    cpi = cpi.loc[_codigo(cpi["UNIT_MEASURE"]).eq("771")]
    juros = _serie_unica(_normalizar_mensal(juros), "juros_nominais")
    cpi = _serie_unica(_normalizar_mensal(cpi), "inflacao_12m")
    painel = juros.merge(cpi, on=["pais_codigo", "mes"], how="inner", validate="one_to_one")
    painel = painel.loc[painel["inflacao_12m"] > -100].copy()
    painel["juros_reais"] = fisher(painel["juros_nominais"], painel["inflacao_12m"])
    painel["spread_simples"] = painel["juros_nominais"] - painel["inflacao_12m"]
    return painel.sort_values(["mes", "pais_codigo"]).reset_index(drop=True)


def mes_recomendado(painel: pd.DataFrame) -> pd.Timestamp:
    """Último mês com ao menos 80% da cobertura máxima dos últimos 12 meses."""
    cobertura = painel.groupby("mes")["pais_codigo"].nunique().sort_index()
    if cobertura.empty:
        raise ValueError("Painel sem observações compatíveis.")
    recente = cobertura.loc[cobertura.index >= cobertura.index.max() - pd.DateOffset(months=11)]
    return recente.loc[recente >= recente.max() * 0.8].index.max()


def ler_snapshot(caminho: Path = CACHE) -> tuple[pd.DataFrame, dict]:
    with ZipFile(caminho) as arquivo:
        meta = json.loads(arquivo.read("metadados.json"))
        if meta.get("schema") != SCHEMA:
            raise ValueError("Versão de cache incompatível.")
        painel = pd.read_csv(arquivo.open("painel.csv"), parse_dates=["mes"])
    if painel.empty or not {"pais_codigo", "mes", "juros_nominais", "inflacao_12m", "juros_reais"}.issubset(painel):
        raise ValueError("Snapshot inválido.")
    return painel, meta


def atualizar_snapshot(caminho: Path = CACHE) -> tuple[pd.DataFrame, dict]:
    juros = obter_csv_bis("juros")
    inflacao = obter_csv_bis("inflacao")
    painel = construir_painel(juros, inflacao)
    if painel.empty:
        raise ValueError("As bases BIS não possuem observações mensais compatíveis.")
    meta = {"schema": SCHEMA, "consultado_em": datetime.now(timezone.utc).isoformat(),
            "fontes": URLS, "observacoes": len(painel),
            "ultimo_mes": painel["mes"].max().strftime("%Y-%m"),
            "economias": int(painel["pais_codigo"].nunique())}
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".tmp")
    try:
        with ZipFile(temporario, "w", ZIP_DEFLATED) as arquivo:
            arquivo.writestr("painel.csv", painel.to_csv(index=False))
            arquivo.writestr("metadados.json", json.dumps(meta, ensure_ascii=False, indent=2))
        temporario.replace(caminho)
    finally:
        temporario.unlink(missing_ok=True)
    return painel, meta


def carregar_painel(forcar: bool = False, caminho: Path = CACHE) -> tuple[pd.DataFrame, dict]:
    anterior = None
    try:
        anterior = ler_snapshot(caminho)
        idade = (datetime.now(timezone.utc) - datetime.fromisoformat(anterior[1]["consultado_em"])).total_seconds()
        if not forcar and 0 <= idade < 12 * 3600:
            return anterior[0], {**anterior[1], "modo": "cache", "aviso": None}
    except (OSError, ValueError, KeyError, BadZipFile):
        pass
    try:
        painel, meta = atualizar_snapshot(caminho)
        return painel, {**meta, "modo": "online", "aviso": None}
    except (requests.RequestException, OSError, ValueError, BadZipFile) as erro:
        if anterior is None:
            raise
        return anterior[0], {**anterior[1], "modo": "offline", "aviso": str(erro)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atualizar", action="store_true", help="Ignora o cache de 12 horas")
    args = parser.parse_args()
    _, resultado = carregar_painel(forcar=args.atualizar)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    if resultado["modo"] == "offline":
        raise SystemExit(1)
