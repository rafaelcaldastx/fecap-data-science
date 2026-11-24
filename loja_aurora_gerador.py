"""
Loja Aurora — gerador da base sintética do Módulo 8 (FECAP)
Versionamento e Governança de Produtos de IA

Gera 5 tabelas usadas nas 7 aulas:
  clientes, produtos, lojas            -> dimensões
  transacoes                           -> Case A: prevenção a fraude (classificação)
  vendas_semanais                      -> Case B: previsão de vendas (regressão)

Uso:
  from loja_aurora_gerador import gerar_base
  tabelas = gerar_base(seed=42)          # base oficial da disciplina (v1)
  tabelas = gerar_base(seed=None)        # base diferente a cada execução (lição de reprodutibilidade)

Requer apenas numpy e pandas (já instalados no Colab e no Databricks).
Todos os dados são fictícios.
"""

import hashlib
import numpy as np
import pandas as pd

VERSAO_GERADOR = "1.0.0"
DATA_INICIO = pd.Timestamp("2024-01-01")
DATA_CORTE = pd.Timestamp("2026-10-31 23:59:59")   # "hoje" dentro da base

UFS = ["SP", "RJ", "MG", "PR", "RS", "BA", "PE", "SC", "GO", "DF"]
PESO_UF = np.array([0.38, 0.13, 0.11, 0.07, 0.06, 0.06, 0.05, 0.05, 0.05, 0.04])

CATEGORIAS = {
    # categoria: (n_produtos, preco_min, preco_max, margem, sazonal_natal)
    "Eletrônicos": (20, 199, 4999, 0.18, 1.9),
    "Casa Inteligente": (12, 89, 1499, 0.30, 1.6),
    "Eletrodomésticos": (16, 149, 3999, 0.22, 1.4),
    "Moda": (24, 39, 399, 0.55, 1.7),
    "Beleza": (18, 19, 249, 0.50, 1.8),
    "Esporte": (14, 49, 1299, 0.40, 1.3),
    "Brinquedos": (16, 29, 599, 0.45, 2.6),
}


def _rng(seed):
    return np.random.default_rng(seed)


def _datas_aleatorias(rng, n, inicio, fim, pesos_mensais=None):
    """Sorteia datas-hora entre inicio e fim, com crescimento e picos sazonais."""
    dias = pd.date_range(inicio.normalize(), fim.normalize(), freq="D")
    t = np.arange(len(dias)) / len(dias)
    peso = 1 + 0.6 * t                                    # crescimento da operação
    mes, dia = dias.month.values, dias.day.values
    peso = peso * np.where(mes == 12, 1.6, 1.0)            # Natal
    bf = np.zeros(len(dias), dtype=bool)
    for ano in (2024, 2025, 2026):                          # semana da Black Friday
        bf_dia = pd.Timestamp(f"{ano}-11-01") + pd.offsets.Week(weekday=4) * 4
        bf |= (dias >= bf_dia - pd.Timedelta(days=3)) & (dias <= bf_dia + pd.Timedelta(days=3))
    peso = peso * np.where(bf, 3.0, 1.0)
    peso = peso * np.where((mes == 5) & (dia <= 12), 1.3, 1.0)   # Dia das Mães
    peso = peso / peso.sum()
    idx = rng.choice(len(dias), size=n, p=peso)
    # hora do dia: pico 10h-22h, cauda de madrugada
    horas = rng.choice(24, size=n, p=_perfil_horas())
    minutos = rng.integers(0, 60, n)
    segundos = rng.integers(0, 60, n)
    return (pd.to_datetime(dias.values[idx]) + pd.to_timedelta(horas, "h")
            + pd.to_timedelta(minutos, "m") + pd.to_timedelta(segundos, "s"))


def _perfil_horas():
    p = np.array([1.2, 0.8, 0.5, 0.4, 0.4, 0.6, 1.2, 2.2, 3.5, 4.8, 5.8, 6.2,
                  6.5, 6.3, 6.0, 5.9, 6.0, 6.4, 6.9, 7.3, 7.6, 7.0, 5.0, 2.9])
    return p / p.sum()


# ----------------------------------------------------------------------------
# Dimensões
# ----------------------------------------------------------------------------
def gerar_lojas():
    return pd.DataFrame({
        "id_loja": ["L01", "L02", "L03", "L04", "L05", "L06", "ECOM"],
        "nome_loja": ["Aurora Paulista", "Aurora Campinas", "Aurora Barra", "Aurora Savassi",
                      "Aurora Curitiba", "Aurora Salvador", "Aurora Digital (site + app)"],
        "cidade": ["São Paulo", "Campinas", "Rio de Janeiro", "Belo Horizonte", "Curitiba",
                   "Salvador", "Nacional"],
        "uf": ["SP", "SP", "RJ", "MG", "PR", "BA", "BR"],
        "tipo": ["física"] * 6 + ["digital"],
        "data_inauguracao": pd.to_datetime(["2015-03-10", "2018-08-22", "2016-11-05", "2019-04-17",
                                            "2021-09-30", "2023-06-12", "2017-01-15"]),
    })


def gerar_produtos(rng):
    linhas, i = [], 1
    for cat, (n, pmin, pmax, margem, _) in CATEGORIAS.items():
        precos = np.exp(rng.uniform(np.log(pmin), np.log(pmax), n)).round(-1) - 0.10
        for p in precos:
            linhas.append({
                "id_produto": f"P{i:04d}",
                "categoria": cat,
                "nome_produto": f"{cat} — item {i:04d}",
                "preco_lista": float(max(p, 9.90)),
                "custo_unitario": float(round(max(p, 9.90) * (1 - margem * rng.uniform(0.8, 1.2)), 2)),
                "data_lancamento": (DATA_INICIO - pd.Timedelta(days=int(rng.integers(0, 900)))
                                    if rng.random() < 0.8 else
                                    DATA_INICIO + pd.Timedelta(days=int(rng.integers(30, 900)))),
            })
            i += 1
    return pd.DataFrame(linhas)


def gerar_clientes(rng, n=30000):
    data_cad = _datas_aleatorias(rng, n, pd.Timestamp("2019-01-01"), DATA_CORTE - pd.Timedelta(days=1)).normalize()
    segmento = rng.choice(["novo", "recorrente", "vip"], size=n, p=[0.45, 0.45, 0.10])
    faixa_renda = rng.choice(["até 3 SM", "3 a 6 SM", "6 a 10 SM", "acima de 10 SM"], size=n,
                             p=[0.35, 0.33, 0.20, 0.12]).astype(object)
    faixa_renda[rng.random(n) < 0.08] = None                 # dado faltante (qualidade de dados)
    return pd.DataFrame({
        "id_cliente": [f"C{i:06d}" for i in range(1, n + 1)],
        "data_cadastro": data_cad,
        "uf": rng.choice(UFS, size=n, p=PESO_UF),
        "faixa_etaria": rng.choice(["18-24", "25-34", "35-44", "45-59", "60+"], size=n,
                                   p=[0.14, 0.31, 0.27, 0.20, 0.08]),
        "canal_aquisicao": rng.choice(["orgânico", "mídia paga", "indicação", "marketplace", "loja física"],
                                      size=n, p=[0.28, 0.30, 0.12, 0.10, 0.20]),
        "segmento": segmento,
        "faixa_renda": faixa_renda,
        "aceita_comunicacao": rng.random(n) < 0.62,
    })


# ----------------------------------------------------------------------------
# Case A — transações (prevenção a fraude)
# ----------------------------------------------------------------------------
def gerar_transacoes(rng, clientes, produtos, n=180000):
    dt = _datas_aleatorias(rng, n, DATA_INICIO, DATA_CORTE)
    dt = pd.Series(dt).sort_values().reset_index(drop=True)

    # clientes: VIP e recorrentes compram mais
    peso_cli = clientes["segmento"].map({"novo": 1.0, "recorrente": 2.2, "vip": 4.0}).values
    idx_cli = rng.choice(len(clientes), size=n, p=peso_cli / peso_cli.sum())
    cli = clientes.iloc[idx_cli].reset_index(drop=True)
    # cliente só compra depois de se cadastrar: ajusta cadastro quando necessário
    cadastro = np.minimum(cli["data_cadastro"].values, (dt.dt.normalize() - pd.Timedelta(days=1)).values)
    idade_conta_dias = ((dt.dt.normalize().values - cadastro) / np.timedelta64(1, "D")).astype(int)

    canal = rng.choice(["app", "site", "loja física"], size=n, p=[0.46, 0.30, 0.24])
    fisica = canal == "loja física"
    meio = np.where(fisica,
                    rng.choice(["cartão de crédito", "cartão de débito", "Pix"], size=n, p=[0.55, 0.25, 0.20]),
                    rng.choice(["cartão de crédito", "Pix", "boleto"], size=n, p=[0.62, 0.30, 0.08]))
    cat_principal = rng.choice(list(CATEGORIAS), size=n, p=[0.16, 0.10, 0.12, 0.22, 0.16, 0.10, 0.14])
    preco_med_cat = produtos.groupby("categoria")["preco_lista"].median().reindex(cat_principal).values
    seg_mult = cli["segmento"].map({"novo": 0.85, "recorrente": 1.0, "vip": 1.9}).values
    qtd_itens = 1 + rng.poisson(0.9, n)
    valor = (preco_med_cat * seg_mult * rng.lognormal(0, 0.55, n) * (0.7 + 0.3 * qtd_itens)).round(2)
    parcelas = np.where(meio == "cartão de crédito",
                        np.clip(np.round(valor / rng.uniform(150, 600, n)), 1, 12), 1).astype(int)

    hora = dt.dt.hour.values
    madrugada = (hora >= 0) & (hora <= 5)
    dispositivo_novo = np.where(fisica, False, rng.random(n) < 0.07)
    end_alterado_24h = np.where(fisica, False, rng.random(n) < 0.03)
    distancia_km = np.where(fisica, rng.exponential(6, n), rng.exponential(18, n)).round(1)
    tentativas_pagto = 1 + rng.poisson(0.15, n)

    # confundidor: VIP recebe mais cupom E gasta mais (cupom não causa gasto) -> aula 3
    p_cupom = cli["segmento"].map({"novo": 0.18, "recorrente": 0.25, "vip": 0.55}).values
    usou_cupom = rng.random(n) < p_cupom

    # --- probabilidade de fraude (log-odds) ---
    pos_drift = (dt >= pd.Timestamp("2026-07-01")).values      # novo golpe a partir de jul/2026
    z = (-5.9
         + 1.60 * dispositivo_novo
         + 1.20 * madrugada
         + 0.75 * np.log1p(valor / 500)
         + 1.10 * (idade_conta_dias < 30)
         + 0.50 * (tentativas_pagto > 1)
         + 0.35 * (distancia_km > 60)
         + 0.55 * ((meio == "cartão de crédito") & (parcelas >= 10))
         + 0.40 * end_alterado_24h
         + np.where(cat_principal == "Eletrônicos", 0.65, 0.0)
         - 2.2 * fisica)
    # concept drift (jul/2026): golpe via Pix em conta antiga invadida, de dia, no aparelho já conhecido.
    # Os sinais antigos perdem força e surgem sinais novos -> o modelo treinado antes envelhece.
    z = z + pos_drift * (2.6 * end_alterado_24h + 1.6 * (meio == "Pix") * ~fisica
                         - 1.3 * dispositivo_novo - 1.0 * madrugada
                         - 0.9 * (idade_conta_dias < 30) - 0.5 * np.log1p(valor / 500))
    p = 1 / (1 + np.exp(-z))
    fraude = rng.random(n) < p

    # maturação do rótulo: contestação chega de 3 a 120 dias depois
    atraso = np.clip(rng.gamma(2.2, 14, n), 3, 120).astype(int)
    data_confirmacao = dt.dt.normalize() + pd.to_timedelta(atraso, "D")
    confirmada = fraude & (data_confirmacao.values <= DATA_CORTE.normalize())
    data_confirmacao = data_confirmacao.where(confirmada, pd.NaT)

    # ARMADILHA (target leakage): status do pedido só é conhecido DEPOIS do fato
    status = np.where(confirmada, "cancelado_chargeback",
                      np.where(rng.random(n) < 0.04, "cancelado_cliente", "entregue"))
    status = np.where(confirmada & (rng.random(n) < 0.08), "entregue", status)  # ruído realista

    df = pd.DataFrame({
        "id_transacao": [f"T{i:07d}" for i in range(1, n + 1)],
        "data_hora": dt.values,
        "id_cliente": cli["id_cliente"].values,
        "canal": canal,
        "meio_pagamento": meio,
        "parcelas": parcelas,
        "categoria_principal": cat_principal,
        "qtd_itens": qtd_itens,
        "valor_total": valor,
        "usou_cupom": usou_cupom,
        "idade_conta_dias": idade_conta_dias,
        "dispositivo_novo": dispositivo_novo,
        "endereco_alterado_24h": end_alterado_24h,
        "distancia_entrega_km": distancia_km,
        "tentativas_pagamento": tentativas_pagto,
        "uf_entrega": np.where(fisica, cli["uf"].values,
                               np.where(rng.random(n) < 0.9, cli["uf"].values, rng.choice(UFS, n, p=PESO_UF))),
        "status_pedido": status,                       # LEAKAGE
        "fraude_confirmada": confirmada.astype(int),    # TARGET (Case A)
        "data_confirmacao_fraude": data_confirmacao.values,
    })

    # ARMADILHA (vazamento temporal): contagem de contestações do cliente usando TODO o histórico
    contest = df.groupby("id_cliente")["fraude_confirmada"].transform("sum")
    df["qtd_contestacoes_cliente"] = contest.astype(int)        # LEAKAGE temporal

    # ARMADILHA (qualidade): ~0,3% de linhas duplicadas por reenvio de integração
    dup = df.sample(frac=0.003, random_state=int(rng.integers(0, 1_000_000)))
    df = pd.concat([df, dup]).sort_values(["data_hora", "id_transacao"]).reset_index(drop=True)
    return df


# ----------------------------------------------------------------------------
# Case B — vendas semanais (previsão de vendas)
# ----------------------------------------------------------------------------
def gerar_vendas_semanais(rng, produtos, lojas):
    semanas = pd.date_range(DATA_INICIO, DATA_CORTE, freq="W-MON")
    semanas = semanas[semanas + pd.Timedelta(days=6) <= DATA_CORTE]
    P, L, S = len(produtos), len(lojas), len(semanas)
    grade = pd.MultiIndex.from_product([semanas, lojas["id_loja"], produtos["id_produto"]],
                                       names=["semana_inicio", "id_loja", "id_produto"]).to_frame(index=False)
    grade = grade.merge(produtos[["id_produto", "categoria", "preco_lista", "data_lancamento"]], on="id_produto")
    grade = grade.merge(lojas[["id_loja", "uf", "tipo"]], on="id_loja")
    grade = grade[grade["semana_inicio"] >= grade["data_lancamento"]].reset_index(drop=True)
    n = len(grade)

    sem = grade["semana_inicio"]
    t = ((sem - DATA_INICIO).dt.days / 365.25).values
    mes = sem.dt.month.values
    woy = sem.dt.isocalendar().week.values.astype(int)

    base_prod = dict(zip(produtos["id_produto"], rng.lognormal(1.6, 0.7, P)))
    base = grade["id_produto"].map(base_prod).values
    preco_rel = (grade["preco_lista"].values / 500) ** -0.35      # item caro vende menos
    porte_loja = grade["id_loja"].map({"L01": 1.4, "L02": 0.9, "L03": 1.1, "L04": 0.9,
                                       "L05": 0.8, "L06": 0.7, "ECOM": 2.6}).values
    sazonal_natal = grade["categoria"].map({c: v[4] for c, v in CATEGORIAS.items()}).values
    sazonal = 1 + 0.12 * np.sin(2 * np.pi * (woy - 10) / 52)
    sazonal = sazonal * np.where(mes == 12, sazonal_natal, 1.0)

    feriado = np.isin(sem.dt.strftime("%m-%d").values, []) | False
    black_friday = np.zeros(n, dtype=bool)
    for ano in (2024, 2025, 2026):
        bf_dia = pd.Timestamp(f"{ano}-11-01") + pd.offsets.Week(weekday=4) * 4
        black_friday |= (sem.values == (bf_dia - pd.Timedelta(days=bf_dia.weekday())).to_datetime64())
    semana_feriado = np.isin(woy, [1, 8, 15, 17, 36, 41, 44, 46, 47, 52])
    promocao = (rng.random(n) < 0.12) | black_friday
    desconto = np.where(promocao, rng.choice([0.10, 0.15, 0.20, 0.30], size=n, p=[0.35, 0.3, 0.25, 0.10]), 0.0)
    desconto = np.where(black_friday, np.maximum(desconto, 0.25), desconto)
    preco_praticado = (grade["preco_lista"].values * (1 - desconto)).round(2)

    tendencia = 1 + 0.10 * t + np.where(grade["categoria"].values == "Casa Inteligente", 0.22 * t, 0.0)
    efeito_promo = (1 - desconto) ** -2.0                          # elasticidade
    # drift: concorrente entra em ago/2026 e derruba Eletrônicos nas lojas de SP
    choque = np.where((sem.values >= np.datetime64("2026-08-03")) & (grade["categoria"].values == "Eletrônicos")
                      & (grade["uf"].values == "SP"), 0.72, 1.0)
    lam = (base * preco_rel * porte_loja * sazonal * tendencia * efeito_promo
           * np.where(black_friday, 2.4, 1.0) * np.where(semana_feriado, 1.08, 1.0) * choque)
    qtd = rng.negative_binomial(5, 5 / (5 + lam))

    df = pd.DataFrame({
        "semana_inicio": sem.dt.date.values,
        "id_loja": grade["id_loja"].values,
        "id_produto": grade["id_produto"].values,
        "categoria": grade["categoria"].values,
        "preco_lista": grade["preco_lista"].values,
        "preco_praticado": preco_praticado,
        "em_promocao": promocao,
        "desconto_pct": desconto,
        "semana_black_friday": black_friday,
        "semana_com_feriado": semana_feriado,
        "qtd_vendida": qtd,                                             # TARGET 1 (Case B)
        "receita_bruta": (qtd * preco_praticado).round(2),              # TARGET 2 / LEAKAGE p/ qtd
    })
    return df


# ----------------------------------------------------------------------------
def gerar_base(seed=42):
    """Gera todas as tabelas. seed=42 é a versão oficial da disciplina."""
    rng = _rng(seed)
    lojas = gerar_lojas()
    produtos = gerar_produtos(rng)
    clientes = gerar_clientes(rng)
    transacoes = gerar_transacoes(rng, clientes, produtos)
    vendas = gerar_vendas_semanais(rng, produtos, lojas)
    return {"lojas": lojas, "produtos": produtos, "clientes": clientes,
            "transacoes": transacoes, "vendas_semanais": vendas}


def impressao_digital(df):
    """Hash do conteúdo de uma tabela: se mudar um único valor, o hash muda."""
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values.tobytes()).hexdigest()[:16]


def resumo(tabelas):
    linhas = []
    for nome, df in tabelas.items():
        linhas.append({"tabela": nome, "linhas": len(df), "colunas": df.shape[1],
                       "hash": impressao_digital(df)})
    return pd.DataFrame(linhas)


if __name__ == "__main__":
    import os, sys
    destino = sys.argv[1] if len(sys.argv) > 1 else "loja_aurora_v1"
    os.makedirs(destino, exist_ok=True)
    tabs = gerar_base(42)
    for nome, df in tabs.items():
        df.to_csv(os.path.join(destino, f"{nome}.csv"), index=False)
    print(resumo(tabs).to_string(index=False))
