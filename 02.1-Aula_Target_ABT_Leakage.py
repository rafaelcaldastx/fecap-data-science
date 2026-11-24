# Databricks notebook source
# MAGIC %md
# MAGIC # Aula 2 · Construindo a target sem se enganar
# MAGIC **FECAP · Pós em Data Analytics e IA aplicada a Negócios · Módulo 8: Versionamento e Governança de Produtos de IA**
# MAGIC
# MAGIC Laboratório guiado no **Databricks Free Edition** com a base da Loja Aurora criada na Aula 1 (`workspace.loja_aurora`).
# MAGIC
# MAGIC | Parte | O que você vai fazer | Linguagem |
# MAGIC |---|---|---|
# MAGIC | 0 | Conferir se as tabelas da Aula 1 estão no catálogo | SQL |
# MAGIC | 1 | Responder ao enigma de outubro: a maturação do rótulo | SQL |
# MAGIC | 2 | Construir a target `fraude_60d` | SQL |
# MAGIC | 3 | Montar a ABT rascunho e caçar a **coluna espiã** | SQL + Python |
# MAGIC | 4 | Montar a **ABT v1** com o princípio do ponto no tempo | SQL |
# MAGIC | 5 | Gerar as tabelas de **treino, teste e OOT** versionadas | Python + SQL |
# MAGIC | 6 | Viajar no tempo: `DESCRIBE HISTORY` e `VERSION AS OF` | SQL |
# MAGIC | 7 | Dicionário de dados e contrato de dados | SQL |
# MAGIC | B | Trilha do Case B: target e ABT de vendas semanais | SQL |
# MAGIC
# MAGIC > **Antes de começar:** conecte o notebook ao compute **Serverless** (canto superior direito). Rode as células em ordem com **Shift + Enter**.
# MAGIC > Grupos do **Case B** fazem as partes 0, 1 (só leitura), 6 e 7 junto com a turma e a **Trilha B** no lugar das partes 2 a 5.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parte 0 · As tabelas da Aula 1 estão aí?
# MAGIC `SHOW TABLES IN` lista as tabelas de um schema. Você deve ver `clientes`, `lojas`, `produtos`, `transacoes` e `vendas_semanais`.
# MAGIC Se o schema não existir, rode antes o notebook da Aula 1 (`Aula01_Databricks_Loja_Aurora.py`).

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW TABLES IN workspace.loja_aurora

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Conferência rápida: os números devem bater com a turma toda
# MAGIC SELECT count(*)                        AS linhas,
# MAGIC        count(DISTINCT id_transacao)    AS transacoes_unicas,
# MAGIC        count(*) - count(DISTINCT id_transacao) AS linhas_duplicadas,
# MAGIC        round(avg(fraude_confirmada) * 100, 2) AS taxa_fraude_pct
# MAGIC FROM workspace.loja_aurora.transacoes

# COMMAND ----------

# MAGIC %md
# MAGIC ✅ **Esperado:** 180.540 linhas, 180.000 transações únicas, **540 duplicadas** e taxa de 1,20%.
# MAGIC As duplicadas são reenvios da integração: vamos tratá-las na ABT. Anote isso na ficha da target.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parte 1 · O enigma de outubro
# MAGIC Na Aula 1 a taxa de fraude de outubro caiu para cerca de um terço. A pergunta é: **a loja ficou mais segura ou estamos olhando cedo demais?**
# MAGIC
# MAGIC A coluna `data_confirmacao_fraude` diz quando a contestação foi confirmada. A diferença entre essa data e a data da compra é o **tempo de maturação do rótulo**.
# MAGIC
# MAGIC | Comando | O que faz |
# MAGIC |---|---|
# MAGIC | `datediff(fim, inicio)` | Conta os dias entre duas datas |
# MAGIC | `to_date(data_hora)` | Tira a hora e fica só com a data |
# MAGIC | `CASE WHEN ... THEN ... END` | Cria faixas, como um SE do Excel |
# MAGIC | `sum(...) OVER (ORDER BY ...)` | Soma acumulada: vai somando linha a linha |

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Quanto tempo a fraude leva para virar rótulo?
# MAGIC -- Usamos só compras até jun/2026, que já tiveram 120 dias para amadurecer
# MAGIC WITH fraudes AS (
# MAGIC   SELECT datediff(data_confirmacao_fraude, to_date(data_hora)) AS dias_ate_confirmar
# MAGIC   FROM workspace.loja_aurora.transacoes
# MAGIC   WHERE fraude_confirmada = 1
# MAGIC     AND data_hora < '2026-07-01'
# MAGIC ),
# MAGIC faixas AS (
# MAGIC   SELECT CASE WHEN dias_ate_confirmar <= 15  THEN '01 · até 15 dias'
# MAGIC               WHEN dias_ate_confirmar <= 30  THEN '02 · 16 a 30 dias'
# MAGIC               WHEN dias_ate_confirmar <= 45  THEN '03 · 31 a 45 dias'
# MAGIC               WHEN dias_ate_confirmar <= 60  THEN '04 · 46 a 60 dias'
# MAGIC               WHEN dias_ate_confirmar <= 90  THEN '05 · 61 a 90 dias'
# MAGIC               ELSE                                '06 · 91 a 120 dias' END AS faixa
# MAGIC   FROM fraudes
# MAGIC )
# MAGIC SELECT faixa,
# MAGIC        count(*) AS fraudes,
# MAGIC        round(100 * count(*) / sum(count(*)) OVER (), 1)                  AS pct_da_faixa,
# MAGIC        round(100 * sum(count(*)) OVER (ORDER BY faixa)
# MAGIC                  / sum(count(*)) OVER (), 1)                             AS pct_acumulado
# MAGIC FROM faixas
# MAGIC GROUP BY faixa
# MAGIC ORDER BY faixa

# COMMAND ----------

# MAGIC %md
# MAGIC 💡 **Leitura de negócio:** só cerca de **60%** das fraudes estão confirmadas 30 dias depois da compra, **91%** em 60 dias e **98%** em 90 dias.
# MAGIC Uma compra de 15/out tem apenas 16 dias de vida na data de corte (31/10/2026): a maior parte das fraudes dela **ainda não foi contestada**.
# MAGIC Outubro não ficou mais seguro: o rótulo ainda não amadureceu.
# MAGIC
# MAGIC 👉 Clique no ícone de gráfico do resultado e faça um gráfico de barras de `pct_acumulado` por `faixa`. Essa é a **curva de maturação**.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Taxa de fraude por mês da compra e "idade" do mês na data de corte (31/10/2026)
# MAGIC SELECT date_trunc('month', data_hora)                       AS mes,
# MAGIC        datediff(DATE'2026-10-31', max(to_date(data_hora)))  AS dias_desde_o_fim_do_mes,
# MAGIC        count(*)                                             AS transacoes,
# MAGIC        round(avg(fraude_confirmada) * 100, 2)               AS taxa_observada_hoje_pct
# MAGIC FROM workspace.loja_aurora.transacoes
# MAGIC WHERE data_hora >= '2026-01-01'
# MAGIC GROUP BY mes
# MAGIC ORDER BY mes

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parte 2 · Construir a target do Case A
# MAGIC **Definição de negócio (v1):** uma transação é fraude quando a contestação ou o chargeback é **confirmado em até 60 dias** da compra.
# MAGIC
# MAGIC Três decisões que vão para a ficha da target:
# MAGIC 1. **Janela de desempenho (N):** 60 dias. Captura cerca de 91% das fraudes e libera o rótulo 30 dias antes do que uma janela de 90 dias.
# MAGIC 2. **Rótulo maduro:** só compras com pelo menos 60 dias de vida na data de corte têm rótulo confiável. As demais ficam **sem rótulo** (não são "não fraude").
# MAGIC 3. **Duplicadas:** ficamos com uma linha por `id_transacao`.
# MAGIC
# MAGIC | Comando | O que faz |
# MAGIC |---|---|
# MAGIC | `CREATE OR REPLACE TABLE ... AS SELECT` | Cria (ou recria) uma tabela Delta com o resultado da consulta. Cada recriação vira uma **nova versão** |
# MAGIC | `row_number() OVER (PARTITION BY ... ORDER BY ...)` | Numera as linhas dentro de cada grupo: a primeira de cada `id_transacao` recebe 1 |
# MAGIC | `COMMENT` | Documenta a tabela dentro do próprio catálogo |

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE workspace.loja_aurora.target_fraude
# MAGIC COMMENT 'Case A · target v1: fraude_60d = contestação/chargeback confirmado em até 60 dias da compra. Data de corte 31/10/2026.'
# MAGIC AS
# MAGIC WITH sem_duplicadas AS (
# MAGIC   SELECT id_transacao, id_cliente, data_hora, data_confirmacao_fraude,
# MAGIC          row_number() OVER (PARTITION BY id_transacao ORDER BY data_hora) AS ordem
# MAGIC   FROM workspace.loja_aurora.transacoes
# MAGIC )
# MAGIC SELECT id_transacao,
# MAGIC        id_cliente,
# MAGIC        data_hora,
# MAGIC        CASE WHEN data_confirmacao_fraude IS NOT NULL
# MAGIC              AND datediff(data_confirmacao_fraude, to_date(data_hora)) <= 60
# MAGIC             THEN 1 ELSE 0 END                                   AS fraude_60d,
# MAGIC        datediff(DATE'2026-10-31', to_date(data_hora)) >= 60     AS rotulo_maduro
# MAGIC FROM sem_duplicadas
# MAGIC WHERE ordem = 1

# COMMAND ----------

# MAGIC %sql
# MAGIC -- A target por mês: repare onde o rótulo deixa de ser maduro
# MAGIC SELECT date_trunc('month', data_hora)      AS mes,
# MAGIC        count(*)                            AS transacoes,
# MAGIC        sum(fraude_60d)                     AS fraudes_60d,
# MAGIC        round(avg(fraude_60d) * 100, 2)     AS taxa_pct,
# MAGIC        min(rotulo_maduro)                  AS mes_todo_maduro
# MAGIC FROM workspace.loja_aurora.target_fraude
# MAGIC WHERE data_hora >= '2026-01-01'
# MAGIC GROUP BY mes
# MAGIC ORDER BY mes

# COMMAND ----------

# MAGIC %md
# MAGIC ✅ **Esperado:** de janeiro a agosto de 2026, `mes_todo_maduro = true`. Setembro e outubro não.
# MAGIC **Por que isso importa:** se setembro e outubro entrassem no treino como "não fraude", o modelo aprenderia que golpes recentes são compras boas. É o **viés de rótulo imaturo**.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parte 3 · ABT rascunho e a caça à coluna espiã
# MAGIC A **ABT** (*Analytical Base Table*) é a tabela que o modelo lê: **uma linha por decisão** (aqui, por transação), com as pistas (features) e a resposta (target).
# MAGIC
# MAGIC Primeiro vamos fazer do jeito ingênuo: juntar **todas** as colunas da transação com a target. É assim que muito projeto começa, e é aqui que a espiã entra.

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE workspace.loja_aurora.abt_fraude
# MAGIC COMMENT 'RASCUNHO: todas as colunas da transação + target. Não usar para treino.'
# MAGIC AS
# MAGIC SELECT t.*, alvo.fraude_60d, alvo.rotulo_maduro
# MAGIC FROM (
# MAGIC   SELECT *, row_number() OVER (PARTITION BY id_transacao ORDER BY data_hora) AS ordem
# MAGIC   FROM workspace.loja_aurora.transacoes
# MAGIC ) t
# MAGIC JOIN workspace.loja_aurora.target_fraude alvo USING (id_transacao)
# MAGIC WHERE t.ordem = 1

# COMMAND ----------

# MAGIC %md
# MAGIC ### 🕵️ Pista 1 · A taxa de fraude por valor de cada coluna
# MAGIC Uma coluna "boa demais" separa fraude e não fraude quase perfeitamente. Rode e observe a coluna `status_pedido`.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT status_pedido,
# MAGIC        count(*)                          AS transacoes,
# MAGIC        sum(fraude_60d)                   AS fraudes,
# MAGIC        round(avg(fraude_60d) * 100, 2)   AS taxa_fraude_pct
# MAGIC FROM workspace.loja_aurora.abt_fraude
# MAGIC WHERE rotulo_maduro
# MAGIC GROUP BY status_pedido
# MAGIC ORDER BY taxa_fraude_pct DESC

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Pista 2 · Uma coluna numérica que parece inocente
# MAGIC SELECT qtd_contestacoes_cliente,
# MAGIC        count(*)                          AS transacoes,
# MAGIC        round(avg(fraude_60d) * 100, 2)   AS taxa_fraude_pct
# MAGIC FROM workspace.loja_aurora.abt_fraude
# MAGIC WHERE rotulo_maduro
# MAGIC GROUP BY qtd_contestacoes_cliente
# MAGIC ORDER BY qtd_contestacoes_cliente

# COMMAND ----------

# MAGIC %md
# MAGIC ### 🕵️ Pista 2 · O radar de espiãs (Python)
# MAGIC Para cada coluna, medimos o quanto ela **sozinha** separa fraude de não fraude, com a **AUC** que vimos na Aula 1 (0,5 = chute, 1,0 = perfeito).
# MAGIC Em fraude, nenhuma pista honesta sozinha costuma passar de 0,75. **Acima de 0,90, desconfie.**
# MAGIC
# MAGIC | Comando | O que faz |
# MAGIC |---|---|
# MAGIC | `spark.table(...).toPandas()` | Traz a tabela do Databricks para o pandas |
# MAGIC | `roc_auc_score(y, x)` | Calcula a AUC de uma coluna contra a target |
# MAGIC | `pd.factorize(...)` | Transforma texto em números para poder medir |

# COMMAND ----------

import pandas as pd
from sklearn.metrics import roc_auc_score

abt = spark.table("workspace.loja_aurora.abt_fraude").where("rotulo_maduro AND data_hora < '2026-01-01'").toPandas()
y = abt["fraude_60d"]
ignorar = ["fraude_60d", "fraude_confirmada", "rotulo_maduro", "ordem", "id_transacao", "id_cliente", "data_hora"]

radar = []
for coluna in abt.columns.drop(ignorar):
    x = abt[coluna]
    if "datetime" in str(x.dtype):
        x = x.notna().astype(int)          # data: o que importa é "o campo está preenchido?"
    elif not pd.api.types.is_numeric_dtype(x) or pd.api.types.is_bool_dtype(x):
        # texto: usa a taxa de fraude de cada categoria como "nota" da linha
        x = x.astype(str).map(abt.groupby(x.astype(str))["fraude_60d"].mean())
    x = pd.to_numeric(x, errors="coerce").fillna(-1)
    auc = roc_auc_score(y, x)
    radar.append({"coluna": coluna, "auc_sozinha": round(max(auc, 1 - auc), 3)})

radar = pd.DataFrame(radar).sort_values("auc_sozinha", ascending=False)
radar["alerta"] = radar["auc_sozinha"].map(lambda a: "🚨 ESPIÃ?" if a >= 0.90 else ("⚠️ investigar" if a >= 0.75 else ""))
display(radar)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 🕵️ Pista 3 · O teste do tempo (a pergunta que resolve tudo)
# MAGIC Para cada coluna suspeita, pergunte: **no instante do checkout, essa informação já existia?**
# MAGIC
# MAGIC | Coluna | Quando o valor passa a existir | Veredito |
# MAGIC |---|---|---|
# MAGIC | `status_pedido` | Vira `cancelado_chargeback` **depois** que a fraude é confirmada | 🚨 target leakage |
# MAGIC | `data_confirmacao_fraude` | Só existe **depois** da contestação | 🚨 target leakage |
# MAGIC | `qtd_contestacoes_cliente` | Conta contestações de **todo o histórico**, inclusive as que aconteceram depois da compra | 🚨 vazamento temporal |
# MAGIC | `fraude_confirmada` | É a target bruta (sem janela) | ❌ não é feature |
# MAGIC
# MAGIC ### O tamanho do estrago
# MAGIC Treinamos o mesmo modelo com e sem a espiã. O treino vai até dez/2025 e o teste é jan–jun/2026.

# COMMAND ----------

from sklearn.ensemble import HistGradientBoostingClassifier

base = spark.table("workspace.loja_aurora.abt_fraude").where("rotulo_maduro").toPandas()
honestas = ["valor_total", "parcelas", "qtd_itens", "idade_conta_dias", "distancia_entrega_km", "tentativas_pagamento"]
base["dispositivo_novo"] = base["dispositivo_novo"].astype(int)
base["endereco_alterado_24h"] = base["endereco_alterado_24h"].astype(int)
base["hora"] = pd.to_datetime(base["data_hora"]).dt.hour
honestas += ["dispositivo_novo", "endereco_alterado_24h", "hora"]
base["espia_status"] = (base["status_pedido"] == "cancelado_chargeback").astype(int)

treino = base[base["data_hora"] < "2026-01-01"]
teste  = base[(base["data_hora"] >= "2026-01-01") & (base["data_hora"] < "2026-07-01")]

def auc_modelo(colunas):
    m = HistGradientBoostingClassifier(max_iter=200, random_state=42).fit(treino[colunas], treino["fraude_60d"])
    return round(roc_auc_score(teste["fraude_60d"], m.predict_proba(teste[colunas])[:, 1]), 3)

print("AUC sem a espiã :", auc_modelo(honestas))
print("AUC COM a espiã :", auc_modelo(honestas + ["espia_status"]))
print("AUC com contestações do histórico todo:", auc_modelo(honestas + ["qtd_contestacoes_cliente"]))

# COMMAND ----------

# MAGIC %md
# MAGIC 💡 **Lição:** com a espiã, a AUC salta para perto de 0,98. Parece um modelo genial, mas no checkout real o `status_pedido` sempre é "entregue" ou vazio: o modelo **não serviria para nada** em produção.
# MAGIC Resultado bom demais é sintoma, não conquista.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parte 4 · ABT v1 com o princípio do ponto no tempo
# MAGIC Regra de ouro: **cada linha só pode usar o que se sabia no momento da decisão** (o checkout).
# MAGIC
# MAGIC O que muda em relação ao rascunho:
# MAGIC - Escolhemos as colunas **uma a uma** (lista de permissões), em vez de `SELECT *`.
# MAGIC - Criamos pistas do **histórico do cliente** olhando **só para trás**: `h.data_hora < t.data_hora`.
# MAGIC - Fraudes anteriores do cliente só contam se **já estavam confirmadas** antes da compra atual: `h.data_confirmacao_fraude < t.data_hora`.
# MAGIC
# MAGIC | Comando | O que faz |
# MAGIC |---|---|
# MAGIC | `LEFT JOIN ... ON h.id_cliente = t.id_cliente AND h.data_hora < t.data_hora` | Junta cada compra com as compras **anteriores** do mesmo cliente |
# MAGIC | `count(...) FILTER (WHERE ...)` | Conta só as linhas que atendem à condição, como um CONT.SE |
# MAGIC | `t.data_hora - INTERVAL 30 DAYS` | Volta 30 dias no tempo a partir da compra |
# MAGIC | `unix_timestamp(...)` | Converte data e hora em segundos, para calcular diferenças |
# MAGIC
# MAGIC > Repare: vamos **recriar** a tabela `abt_fraude`. O Delta guarda a versão anterior (o rascunho com a espiã). Isso vai ser útil na Parte 6.

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE workspace.loja_aurora.abt_fraude
# MAGIC COMMENT 'Case A · ABT v1 · uma linha por transação · features no ponto no tempo do checkout · target fraude_60d'
# MAGIC AS
# MAGIC WITH tx AS (
# MAGIC   SELECT id_transacao, id_cliente, data_hora, canal, meio_pagamento, parcelas, categoria_principal,
# MAGIC          qtd_itens, valor_total, usou_cupom, idade_conta_dias, dispositivo_novo, endereco_alterado_24h,
# MAGIC          distancia_entrega_km, tentativas_pagamento, uf_entrega, data_confirmacao_fraude
# MAGIC   FROM (
# MAGIC     SELECT *, row_number() OVER (PARTITION BY id_transacao ORDER BY data_hora) AS ordem
# MAGIC     FROM workspace.loja_aurora.transacoes
# MAGIC   ) WHERE ordem = 1
# MAGIC ),
# MAGIC historico AS (
# MAGIC   -- só compras ANTERIORES do mesmo cliente (h.data_hora < t.data_hora)
# MAGIC   SELECT t.id_transacao,
# MAGIC          count(h.id_transacao) FILTER (WHERE h.data_hora >= t.data_hora - INTERVAL 1 DAYS)   AS cli_qtd_compras_24h,
# MAGIC          count(h.id_transacao) FILTER (WHERE h.data_hora >= t.data_hora - INTERVAL 30 DAYS)  AS cli_qtd_compras_30d,
# MAGIC          avg(h.valor_total)    FILTER (WHERE h.data_hora >= t.data_hora - INTERVAL 90 DAYS)  AS cli_valor_medio_90d,
# MAGIC          (unix_timestamp(t.data_hora) - unix_timestamp(max(h.data_hora))) / 86400.0          AS cli_dias_desde_ultima,
# MAGIC          -- fraude anterior só conta se JÁ estava confirmada no momento desta compra
# MAGIC          count(h.id_transacao) FILTER (WHERE h.data_confirmacao_fraude < t.data_hora)        AS cli_fraudes_conhecidas
# MAGIC   FROM tx t
# MAGIC   LEFT JOIN tx h
# MAGIC     ON h.id_cliente = t.id_cliente
# MAGIC    AND h.data_hora  < t.data_hora
# MAGIC   GROUP BY t.id_transacao, t.data_hora
# MAGIC )
# MAGIC SELECT
# MAGIC   -- chaves e tempo (não entram no modelo, servem para rastrear e dividir)
# MAGIC   t.id_transacao, t.id_cliente, t.data_hora,
# MAGIC   -- o que se sabe no checkout
# MAGIC   t.canal, t.meio_pagamento, t.parcelas, t.categoria_principal, t.qtd_itens, t.valor_total,
# MAGIC   t.usou_cupom, t.idade_conta_dias, t.dispositivo_novo, t.endereco_alterado_24h,
# MAGIC   t.distancia_entrega_km, t.tentativas_pagamento,
# MAGIC   hour(t.data_hora)                                    AS hora,
# MAGIC   hour(t.data_hora) BETWEEN 0 AND 5                    AS madrugada,
# MAGIC   dayofweek(t.data_hora)                               AS dia_semana,
# MAGIC   t.uf_entrega <> c.uf                                 AS uf_entrega_diferente,
# MAGIC   -- cadastro do cliente (atenção: é a foto de hoje, ver ficha)
# MAGIC   c.segmento, c.faixa_etaria, c.faixa_renda,
# MAGIC   -- histórico do cliente no ponto no tempo
# MAGIC   h.cli_qtd_compras_24h, h.cli_qtd_compras_30d, h.cli_valor_medio_90d,
# MAGIC   round(t.valor_total / h.cli_valor_medio_90d, 3)      AS razao_valor_media_90d,
# MAGIC   h.cli_dias_desde_ultima, h.cli_fraudes_conhecidas,
# MAGIC   -- target e maturidade
# MAGIC   alvo.fraude_60d, alvo.rotulo_maduro
# MAGIC FROM tx t
# MAGIC JOIN historico h          USING (id_transacao)
# MAGIC JOIN workspace.loja_aurora.target_fraude alvo USING (id_transacao)
# MAGIC LEFT JOIN workspace.loja_aurora.clientes c  ON c.id_cliente = t.id_cliente

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Conferência da ABT v1: uma linha por transação e nenhuma coluna espiã
# MAGIC SELECT count(*)                       AS linhas,
# MAGIC        count(DISTINCT id_transacao)   AS transacoes_unicas,
# MAGIC        round(avg(fraude_60d) * 100, 2) AS taxa_fraude_60d_pct,
# MAGIC        sum(CASE WHEN rotulo_maduro THEN 0 ELSE 1 END) AS linhas_sem_rotulo_maduro
# MAGIC FROM workspace.loja_aurora.abt_fraude

# COMMAND ----------

# MAGIC %md
# MAGIC ✅ **Esperado:** 180.000 linhas, 180.000 transações únicas.
# MAGIC
# MAGIC 🧠 **Para pensar:** compare `cli_fraudes_conhecidas` (ponto no tempo) com `qtd_contestacoes_cliente` (histórico todo). Rode o radar de novo trocando a tabela e veja a AUC da versão honesta despencar para perto de 0,5.
# MAGIC A mesma ideia, medida do jeito certo, quase não ajuda. Medida do jeito errado, parecia a melhor pista da base.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parte 5 · Treino, teste e OOT versionados
# MAGIC Em fraude e em vendas, **o tempo manda**. Dividimos pela data, nunca por sorteio:
# MAGIC
# MAGIC | Conjunto | Período | Para quê |
# MAGIC |---|---|---|
# MAGIC | Treino | jan/2024 a dez/2025 | O modelo aprende |
# MAGIC | Teste | jan/2026 a jun/2026 | Escolher e ajustar o modelo |
# MAGIC | OOT (*out-of-time*) | jul/2026 a ago/2026 | Prova final, em meses que ninguém olhou |
# MAGIC | Sem rótulo | set/2026 a out/2026 | Fica de fora: rótulo imaturo. Vira "produção" na Aula 6 |
# MAGIC
# MAGIC **Boa prática de versionamento:** as três tabelas saem de **uma versão fixa** da ABT (`VERSION AS OF`). Assim, mesmo que alguém altere a ABT amanhã, sabemos exatamente de onde veio cada linha.

# COMMAND ----------

# 1. Qual é a versão atual da ABT? (DESCRIBE HISTORY devolve a mais recente primeiro)
versao_abt = spark.sql("DESCRIBE HISTORY workspace.loja_aurora.abt_fraude LIMIT 1").first()["version"]
print("Versão da ABT usada nos splits:", versao_abt)

# 2. Cria as três tabelas a partir dessa versão fixa
splits = {
    "abt_fraude_treino": "data_hora <  '2026-01-01'",
    "abt_fraude_teste":  "data_hora >= '2026-01-01' AND data_hora < '2026-07-01'",
    "abt_fraude_oot":    "data_hora >= '2026-07-01' AND data_hora < '2026-09-01'",
}
for nome, filtro in splits.items():
    spark.sql(f'''
        CREATE OR REPLACE TABLE workspace.loja_aurora.{nome}
        COMMENT 'Case A · {nome} · origem: abt_fraude VERSION AS OF {versao_abt}'
        TBLPROPERTIES ('origem.tabela' = 'abt_fraude', 'origem.versao' = '{versao_abt}', 'target' = 'fraude_60d')
        AS SELECT * FROM workspace.loja_aurora.abt_fraude VERSION AS OF {versao_abt}
        WHERE rotulo_maduro AND {filtro}
    ''')
    print("criada:", nome)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Manifesto dos datasets
# MAGIC O manifesto é a "nota fiscal" de cada conjunto: quantas linhas, quantas fraudes, qual período, de qual versão veio e uma **impressão digital** (hash) do conteúdo.
# MAGIC Se uma única linha mudar, a impressão digital muda.
# MAGIC
# MAGIC | Comando | O que faz |
# MAGIC |---|---|
# MAGIC | `xxhash64(*)` | Calcula um código para cada linha a partir de todas as colunas |
# MAGIC | `bit_xor(...)` | Combina os códigos de todas as linhas em um só, sem depender da ordem |

# COMMAND ----------

partes = []
for nome in ["abt_fraude_treino", "abt_fraude_teste", "abt_fraude_oot"]:
    versao = spark.sql(f"DESCRIBE HISTORY workspace.loja_aurora.{nome} LIMIT 1").first()["version"]
    partes.append(f'''
        SELECT '{nome}' AS dataset, {versao} AS versao_delta,
               min(to_date(data_hora)) AS inicio, max(to_date(data_hora)) AS fim,
               count(*) AS linhas, sum(fraude_60d) AS fraudes,
               round(avg(fraude_60d) * 100, 2) AS taxa_pct,
               lower(hex(bit_xor(xxhash64(*)))) AS impressao_digital,
               current_timestamp() AS gerado_em
        FROM workspace.loja_aurora.{nome}''')

spark.sql(f"CREATE OR REPLACE TABLE workspace.loja_aurora.manifesto_datasets AS " + " UNION ALL ".join(partes))
display(spark.table("workspace.loja_aurora.manifesto_datasets"))

# COMMAND ----------

# MAGIC %md
# MAGIC ✅ **Esperado (aproximado):** treino ≈ 122,7 mil linhas e taxa ≈ 1,20% · teste ≈ 33,6 mil e ≈ 0,92% · OOT ≈ 11,8 mil e ≈ 1,03%.
# MAGIC A impressão digital deve ser **igual** à da dupla ao lado. Copie a tabela do manifesto para a ficha.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Por que não sortear? A prova em números
# MAGIC Abaixo, o mesmo modelo avaliado de dois jeitos: sorteando 20% das linhas (como na Aula 1) e respeitando o tempo.

# COMMAND ----------

from sklearn.model_selection import train_test_split

def preparar(df):
    X = df[["valor_total", "parcelas", "qtd_itens", "idade_conta_dias", "distancia_entrega_km", "tentativas_pagamento",
            "hora", "cli_qtd_compras_24h", "cli_qtd_compras_30d", "cli_valor_medio_90d", "razao_valor_media_90d",
            "cli_dias_desde_ultima", "cli_fraudes_conhecidas"]].astype(float)
    X["dispositivo_novo"] = df["dispositivo_novo"].astype(int)
    X["endereco_alterado_24h"] = df["endereco_alterado_24h"].astype(int)
    X["madrugada"] = df["madrugada"].astype(int)
    X = X.join(pd.get_dummies(df[["canal", "meio_pagamento", "categoria_principal"]], dtype=float))
    return X

tr  = spark.table("workspace.loja_aurora.abt_fraude_treino").toPandas()
te  = spark.table("workspace.loja_aurora.abt_fraude_teste").toPandas()
oot = spark.table("workspace.loja_aurora.abt_fraude_oot").toPandas()
tudo = pd.concat([tr, te, oot], ignore_index=True)
Xtr, Xte, Xoot, Xall = preparar(tr), preparar(te), preparar(oot), preparar(tudo)
Xte, Xoot, Xall = [x.reindex(columns=Xtr.columns, fill_value=0) for x in (Xte, Xoot, Xall)]

modelo = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=42).fit(Xtr, tr["fraude_60d"])
print("Divisão no tempo · teste (jan–jun/26):", round(roc_auc_score(te["fraude_60d"],  modelo.predict_proba(Xte)[:, 1]), 3))
print("Divisão no tempo · OOT   (jul–ago/26):", round(roc_auc_score(oot["fraude_60d"], modelo.predict_proba(Xoot)[:, 1]), 3))

Xa, Xb, ya, yb = train_test_split(Xall, tudo["fraude_60d"], test_size=0.2, random_state=42, stratify=tudo["fraude_60d"])
sorteio = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=42).fit(Xa, ya)
print("Divisão por sorteio (20% aleatório)   :", round(roc_auc_score(yb, sorteio.predict_proba(Xb)[:, 1]), 3))

# COMMAND ----------

# MAGIC %md
# MAGIC 💡 **Leitura:** o sorteio promete uma AUC mais alta que a do teste no tempo, e o OOT mostra a realidade de julho e agosto, quando surgiu um golpe novo.
# MAGIC O sorteio mistura o futuro no treino e esconde a mudança do mundo. **Quem apresenta a nota do sorteio ao comitê está prometendo um desempenho que não vai entregar.**
# MAGIC (O que acontece em julho é assunto da Aula 6: drift.)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parte 6 · Viagem no tempo com Delta Lake
# MAGIC Toda tabela Delta guarda um **histórico de versões**. Cada `CREATE OR REPLACE`, `INSERT`, `UPDATE` ou `DELETE` vira uma versão nova.
# MAGIC
# MAGIC | Comando | O que faz |
# MAGIC |---|---|
# MAGIC | `DESCRIBE HISTORY tabela` | Lista as versões: número, data, quem fez e qual operação |
# MAGIC | `SELECT ... FROM tabela VERSION AS OF 0` | Lê a tabela como ela era na versão 0 |
# MAGIC | `SELECT ... FROM tabela TIMESTAMP AS OF '2026-11-16 20:00'` | Lê a tabela como ela era naquele horário |
# MAGIC | `tabela@v0` | Atalho para `VERSION AS OF 0` |
# MAGIC | `RESTORE TABLE tabela TO VERSION AS OF 0` | Volta a tabela inteira para uma versão anterior |

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE HISTORY workspace.loja_aurora.abt_fraude

# COMMAND ----------

# MAGIC %md
# MAGIC Repare na coluna `operation`: a versão 0 é o **rascunho** (com a espiã) e a versão 1 é a **ABT v1**.
# MAGIC Se você rodou alguma célula mais de uma vez, terá mais versões: use os números que aparecerem para você.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- A versão 0 ainda tem a coluna espiã? (rascunho)
# MAGIC SELECT status_pedido, count(*) AS transacoes
# MAGIC FROM workspace.loja_aurora.abt_fraude VERSION AS OF 0
# MAGIC GROUP BY status_pedido

# COMMAND ----------

v0 = set(spark.sql("SELECT * FROM workspace.loja_aurora.abt_fraude VERSION AS OF 0").columns)
atual = set(spark.table("workspace.loja_aurora.abt_fraude").columns)
print("Colunas removidas da ABT v1 (excluídas por risco de leakage ou por serem chaves técnicas):")
for c in sorted(v0 - atual): print("  -", c)
print()
print("Colunas novas na ABT v1 (criadas no ponto no tempo):")
for c in sorted(atual - v0): print("  +", c)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Simulando um acidente (e desfazendo)
# MAGIC Um colega "limpa" o treino apagando as transações de loja física. O histórico registra quem fez, quando e o quê. O `RESTORE` desfaz.

# COMMAND ----------

tabela = "workspace.loja_aurora.abt_fraude_treino"
versao_antes = spark.sql(f"DESCRIBE HISTORY {tabela} LIMIT 1").first()["version"]

# O "acidente": alguém apaga as compras de loja física
spark.sql(f"DELETE FROM {tabela} WHERE canal = 'loja física'")

# O histórico registra a operação, a data e quantas linhas sumiram
display(spark.sql(f"DESCRIBE HISTORY {tabela}").select("version", "timestamp", "userName", "operation", "operationMetrics"))

antes = spark.sql(f"SELECT count(*) AS n FROM {tabela} VERSION AS OF {versao_antes}").first()["n"]
agora = spark.table(tabela).count()
print(f"Antes do acidente (versão {versao_antes}): {antes:,} linhas  |  agora: {agora:,} linhas")

# Desfazendo: volta a tabela para a versão anterior ao acidente
spark.sql(f"RESTORE TABLE {tabela} TO VERSION AS OF {versao_antes}")
print("Depois do RESTORE:", f"{spark.table(tabela).count():,}", "linhas")

# COMMAND ----------

# MAGIC %md
# MAGIC ⚠️ **Limites do time travel (documentação Databricks):** por padrão, o histórico fica 30 dias e os arquivos de dados antigos podem ser apagados pelo `VACUUM` depois de 7 dias.
# MAGIC A própria Databricks orienta **não usar o histórico como backup de longo prazo**. Para guardar a versão oficial do treino por anos (auditoria, LGPD art. 20), crie uma **cópia congelada** (snapshot):

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Snapshot congelado do treino oficial (cópia física e independente)
# MAGIC CREATE OR REPLACE TABLE workspace.loja_aurora.snapshot_abt_fraude_treino_v1
# MAGIC DEEP CLONE workspace.loja_aurora.abt_fraude_treino

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parte 7 · Dicionário de dados e contrato de dados
# MAGIC - **Dicionário de dados:** o que cada coluna significa. Melhor ainda se estiver **dentro do catálogo**, junto da tabela.
# MAGIC - **Contrato de dados:** as regras que a tabela promete cumprir (formato, valores válidos, dono, prazo). No Delta, parte do contrato vira **restrição**: o próprio banco recusa dados que quebram a regra.

# COMMAND ----------

# MAGIC %sql
# MAGIC ALTER TABLE workspace.loja_aurora.abt_fraude ALTER COLUMN fraude_60d
# MAGIC   COMMENT 'TARGET · 1 = contestação/chargeback confirmado em até 60 dias da compra · fonte: transacoes.data_confirmacao_fraude'

# COMMAND ----------

# MAGIC %sql
# MAGIC ALTER TABLE workspace.loja_aurora.abt_fraude ALTER COLUMN cli_fraudes_conhecidas
# MAGIC   COMMENT 'Fraudes anteriores do cliente JÁ confirmadas antes desta compra (ponto no tempo). Substitui qtd_contestacoes_cliente (vazamento temporal).'

# COMMAND ----------

# MAGIC %sql
# MAGIC ALTER TABLE workspace.loja_aurora.abt_fraude ALTER COLUMN rotulo_maduro
# MAGIC   COMMENT 'true quando a compra tem 60 dias ou mais na data de corte (31/10/2026). Sem rótulo maduro = sem target confiável.'

# COMMAND ----------

# MAGIC %sql
# MAGIC ALTER TABLE workspace.loja_aurora.abt_fraude SET TBLPROPERTIES (
# MAGIC   'abt.versao'           = '1.0',
# MAGIC   'abt.granularidade'    = '1 linha por id_transacao',
# MAGIC   'abt.data_corte'       = '2026-10-31',
# MAGIC   'target.definicao'     = 'fraude_60d: contestacao ou chargeback confirmado em ate 60 dias',
# MAGIC   'leakage.excluidas'    = 'status_pedido, data_confirmacao_fraude, qtd_contestacoes_cliente, fraude_confirmada',
# MAGIC   'dono'                 = 'grupo X · FECAP Modulo 8'
# MAGIC )

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Contrato na prática: o Delta passa a recusar uma target diferente de 0 ou 1
# MAGIC ALTER TABLE workspace.loja_aurora.abt_fraude ADD CONSTRAINT target_binaria CHECK (fraude_60d IN (0, 1))

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Teste o contrato: esta inserção deve FALHAR (é de propósito)
# MAGIC -- INSERT INTO workspace.loja_aurora.abt_fraude (id_transacao, fraude_60d) VALUES ('TESTE', 7)
# MAGIC DESCRIBE TABLE EXTENDED workspace.loja_aurora.abt_fraude

# COMMAND ----------

# MAGIC %md
# MAGIC ✅ Tire o comentário (`--`) da linha do `INSERT` e rode: a mensagem de erro `CHECK constraint target_binaria` é o contrato funcionando.
# MAGIC
# MAGIC ### Checagens de qualidade que todo dataset de treino deveria passar

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 'uma linha por transação'      AS regra, count(*) = count(DISTINCT id_transacao) AS passou FROM workspace.loja_aurora.abt_fraude_treino
# MAGIC UNION ALL
# MAGIC SELECT 'target só 0 ou 1',            min(fraude_60d IN (0, 1))                              FROM workspace.loja_aurora.abt_fraude_treino
# MAGIC UNION ALL
# MAGIC SELECT 'só rótulo maduro',            min(rotulo_maduro)                                     FROM workspace.loja_aurora.abt_fraude_treino
# MAGIC UNION ALL
# MAGIC SELECT 'treino termina antes do teste', max(data_hora) < (SELECT min(data_hora) FROM workspace.loja_aurora.abt_fraude_teste) FROM workspace.loja_aurora.abt_fraude_treino
# MAGIC UNION ALL
# MAGIC SELECT 'nenhuma transação em dois conjuntos',
# MAGIC        count(*) = 0
# MAGIC FROM workspace.loja_aurora.abt_fraude_treino tr JOIN workspace.loja_aurora.abt_fraude_teste te USING (id_transacao)

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Fechamento do laboratório (Case A)
# MAGIC Você tem agora, versionados no Delta:
# MAGIC - `target_fraude` · a definição da target
# MAGIC - `abt_fraude` · versão 0 (rascunho com espiã) e versão 1 em diante (ABT v1)
# MAGIC - `abt_fraude_treino`, `abt_fraude_teste`, `abt_fraude_oot` · criadas a partir de uma versão fixa da ABT
# MAGIC - `manifesto_datasets` · linhas, taxa e impressão digital de cada conjunto
# MAGIC - `snapshot_abt_fraude_treino_v1` · cópia congelada para auditoria
# MAGIC
# MAGIC **Entregável:** preencha a **ficha da target e do dataset** (`docs/ficha_target_dataset.md`) e suba no GitLab junto com este notebook.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Trilha B · Case B: previsão de vendas
# MAGIC **Definição de negócio (v1):** "venda" = **unidades vendidas** (`qtd_vendida`) e **valor** (`receita_bruta`) por **produto, loja e semana**.
# MAGIC
# MAGIC **Decisão apoiada:** o comprador fecha o pedido ao fornecedor com **2 semanas de antecedência**. Então, para prever a semana *t*, só podemos usar o que se sabia até a semana *t − 2*. Esse é o **ponto no tempo** do Case B.
# MAGIC
# MAGIC | Comando | O que faz |
# MAGIC |---|---|
# MAGIC | `lag(qtd_vendida, 2) OVER (PARTITION BY id_loja, id_produto ORDER BY semana_inicio)` | Pega o valor de 2 semanas antes, do mesmo produto na mesma loja |
# MAGIC | `avg(...) OVER (... ROWS BETWEEN 5 PRECEDING AND 2 PRECEDING)` | Média das semanas t−5 a t−2 (nunca inclui t−1 nem t) |

# COMMAND ----------

# MAGIC %sql
# MAGIC -- A espiã do Case B: a receita é exatamente quantidade × preço praticado
# MAGIC SELECT round(corr(receita_bruta, qtd_vendida * preco_praticado), 6) AS correlacao,
# MAGIC        sum(CASE WHEN abs(receita_bruta - qtd_vendida * preco_praticado) > 0.01 THEN 1 ELSE 0 END) AS linhas_diferentes
# MAGIC FROM workspace.loja_aurora.vendas_semanais

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE workspace.loja_aurora.abt_vendas
# MAGIC COMMENT 'Case B · ABT v1 · produto x loja x semana · horizonte de 2 semanas · targets qtd_vendida e receita_bruta'
# MAGIC AS
# MAGIC WITH base AS (
# MAGIC   SELECT *,
# MAGIC          lag(qtd_vendida, 2)  OVER w AS qtd_lag2,
# MAGIC          lag(qtd_vendida, 3)  OVER w AS qtd_lag3,
# MAGIC          avg(qtd_vendida)     OVER (PARTITION BY id_loja, id_produto ORDER BY semana_inicio
# MAGIC                                    ROWS BETWEEN 5 PRECEDING AND 2 PRECEDING) AS qtd_media_4s_ate_t2,
# MAGIC          lag(qtd_vendida, 52) OVER w AS qtd_mesma_semana_ano_anterior
# MAGIC   FROM workspace.loja_aurora.vendas_semanais
# MAGIC   WINDOW w AS (PARTITION BY id_loja, id_produto ORDER BY semana_inicio)
# MAGIC )
# MAGIC SELECT semana_inicio, id_loja, id_produto, categoria,
# MAGIC        -- planejado com antecedência (preço e promoção entram no plano comercial)
# MAGIC        preco_lista, preco_praticado, em_promocao, desconto_pct, semana_black_friday, semana_com_feriado,
# MAGIC        weekofyear(semana_inicio) AS semana_do_ano,
# MAGIC        -- histórico até t-2
# MAGIC        qtd_lag2, qtd_lag3, qtd_media_4s_ate_t2, qtd_mesma_semana_ano_anterior,
# MAGIC        -- targets
# MAGIC        qtd_vendida  AS target_qtd,
# MAGIC        receita_bruta AS target_valor
# MAGIC FROM base

# COMMAND ----------

# Splits do Case B a partir de uma versão fixa da ABT de vendas
versao_vendas = spark.sql("DESCRIBE HISTORY workspace.loja_aurora.abt_vendas LIMIT 1").first()["version"]
for nome, filtro in {
    "abt_vendas_treino": "semana_inicio <  '2026-01-01'",
    "abt_vendas_teste":  "semana_inicio >= '2026-01-01' AND semana_inicio < '2026-07-01'",
    "abt_vendas_oot":    "semana_inicio >= '2026-07-01'",
}.items():
    spark.sql(f'''
        CREATE OR REPLACE TABLE workspace.loja_aurora.{nome}
        TBLPROPERTIES ('origem.tabela' = 'abt_vendas', 'origem.versao' = '{versao_vendas}')
        AS SELECT * FROM workspace.loja_aurora.abt_vendas VERSION AS OF {versao_vendas} WHERE {filtro}''')
    print("criada:", nome, "· origem abt_vendas v", versao_vendas)

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 'treino' AS dataset, count(*) AS linhas, min(semana_inicio) AS inicio, max(semana_inicio) AS fim, round(avg(target_qtd), 2) AS media_unidades FROM workspace.loja_aurora.abt_vendas_treino
# MAGIC UNION ALL SELECT 'teste', count(*), min(semana_inicio), max(semana_inicio), round(avg(target_qtd), 2) FROM workspace.loja_aurora.abt_vendas_teste
# MAGIC UNION ALL SELECT 'oot',   count(*), min(semana_inicio), max(semana_inicio), round(avg(target_qtd), 2) FROM workspace.loja_aurora.abt_vendas_oot

# COMMAND ----------

# MAGIC %md
# MAGIC 💡 **Para a ficha do Case B:**
# MAGIC - `receita_bruta` **não** pode ser feature para prever quantidade (é quantidade × preço). Se o grupo prever **valor**, `qtd_vendida` também vira espiã.
# MAGIC - `lag(qtd_vendida, 1)` parece inocente, mas **não existe** quando o pedido é feito com 2 semanas de antecedência.
# MAGIC - Sorteio em série de vendas coloca a semana seguinte no treino e a anterior no teste: use sempre a divisão no tempo.
# MAGIC - Black Friday e Natal: confira se o teste e o OOT têm semanas especiais, ou a métrica engana.
