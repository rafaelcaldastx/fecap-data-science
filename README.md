# Ficha da Target e do Dataset (Loja Aurora · Case A)

## 1. Definição da Target
A target **fraude_60d** é definida como 1 quando a contestação ou o chargeback de uma compra é confirmado em até 60 dias a contar da data e hora da transação; caso contrário, é 0. Apenas compras realizadas com 60 dias ou mais de antecedência em relação à data de corte (31/10/2026) possuem rótulo maduro.

## 2. Janelas, Cortes e Maturação
- **Janela de Observação:** Histórico do cliente no ponto no tempo do checkout (ex.: compras nas últimas 24h, 30d e ticket médio de 90d).
- **Janela de Desempenho (N = 60 dias):** Justificada pela curva empírica de maturação dos dados, que confirma 91,3% dos estornos em até 60 dias (28,2% até 15 dias; 60,0% até 30 dias; 98,2% até 90 dias; 100% até 120 dias). A aparente redução de fraudes em outubro/2026 deve-se à imaturidade do rótulo, e não a um aumento na segurança da loja.
- **Data de Corte:** 31/10/2026.

## 3. Manifesto dos Datasets (Splits Temporais)
Origem: `workspace.loja_aurora.abt_fraude` congelada via `VERSION AS OF`.

| Conjunto | Período | Linhas | Fraudes | Taxa (%) | Impressão Digital (Hash) |
|---|---|---|---|---|---|
| Treino | 01/01/2024 a 31/12/2025 | 122.734 | 1.478 | 1,20% | 58877f2db95ccd98 |
| Teste | 01/01/2026 a 30/06/2026 | 33.563 | 310 | 0,92% | 40c58aaaecfe8b92 |
| OOT | 01/07/2026 a 31/08/2026 | 11.815 | 122 | 1,03% | c654cdde4f20984f |

*Nota: As transações de setembro e outubro de 2026 foram mantidas fora dos conjuntos de modelagem por estarem imaturas na data de corte.*

## 4. Colunas Excluídas por Risco de Data Leakage
- `status_pedido`: Excluída por **Target Leakage** (muda para *cancelado_chargeback* somente após a ocorrência e contestação da fraude; apresentava AUC individual isolada de ~0,962).
- `data_confirmacao_fraude`: Excluída por **Target Leakage** (campo que só é preenchido após a notificação da contestação; AUC individual de 0,999).
- `qtd_contestacoes_cliente`: Excluída por **Vazamento Temporal** (calculada originalmente sobre todo o histórico, enxergando contestações futuras; substituída na ABT v1 por `cli_fraudes_conhecidas`, que restringe a contagem a fatos já confirmados antes do momento do checkout).
- `fraude_confirmada`: Target bruta original sem janela de maturação.

## 5. Riscos e Premissas
- **Rótulo Imaturo:** Risco de viés caso transações recentes sem contestação fossem assumidas como idôneas.
- **Ponto no Tempo:** As agregações do cliente exigem estrita obediência temporal (`data_evento < data_checkout`).
- **Foto do Cadastro:** As variáveis demográficas de clientes (`segmento`, `faixa_renda`) refletem o estado atual no momento da extração (foto cadastral).