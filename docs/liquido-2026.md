# Líquido estimado · 2026

O modo **Dados reais** passa a selecionar `eppgg-folha-real-2026-v2`, válido de janeiro a dezembro de 2026. O banco recebe esse conjunto automaticamente na inicialização, inclusive no Neon configurado. A carga é imutável e idempotente; uma versão administrativa previamente importada com vigência sobreposta é preservada. Não é necessário alterar o schema do banco: as regras ficam no JSON versionado de `parameter_sets`.

## Caso de referência

Servidor ativo I-A, ADI 95, AI 90, mês integral, sem dependentes fiscais, sem comissão/função, regime previdenciário sem teto e sem descontos extras:

| Rubrica | R$ |
| --- | ---: |
| Vencimento | 3.773,24 |
| GDPI | 2.644,01 |
| Bruto | 6.417,25 |
| RPPS | 795,88 |
| IRRF | 512,95 |
| Líquido sem adesão IPSEMG | **5.108,42** |
| IPSEMG, titular de 35 anos | 205,35 |
| Líquido com adesão IPSEMG | **4.903,07** |

Não se presume adesão ao IPSEMG nem enquadramento no regime limitado ao teto. Selecione conforme seu vínculo. Dependentes fiscais e beneficiários da saúde são entradas separadas.

## RPPS

LC 64/2002, arts.26 e 28, redação consolidada: base contributiva das rubricas e alíquotas progressivas de 11%, 12%, 13%, 14%, 15%, 15,5% e 16%. O §5º do art.28 determina atualizar os limites pelos mesmos índices anuais dos benefícios RGPS. A carga recompõe a base de 2020, com arredondamento a centavos em cada ano:

| Ano | Índice | Limites superiores das seis primeiras faixas (R$) |
| --- | ---: | --- |
| 2020 | Base legal | 1.500; 2.500; 3.500; 4.500; 5.500; 6.101,06 |
| 2021 | 5,45% | 1.581,75; 2.636,25; 3.690,75; 4.745,25; 5.799,75; 6.433,57 |
| 2022 | 10,16% | 1.742,46; 2.904,09; 4.065,73; 5.227,37; 6.389; 7.087,22 |
| 2023 | 5,93% | 1.845,79; 3.076,30; 4.306,83; 5.537,35; 6.767,87; 7.507,49 |
| 2024 | 3,71% | 1.914,27; 3.190,43; 4.466,61; 5.742,79; 7.018,96; 7.786,02 |
| 2025 | 4,77% | 2.005,58; 3.342,61; 4.679,67; 6.016,72; 7.353,76; 8.157,41 |
| 2026 | 3,90% | **2.083,80; 3.472,97; 4.862,18; 6.251,37; 7.640,56; 8.475,55** |

A sétima faixa não tem limite. O último limite coincide com o teto RGPS de 2026 publicado na Portaria MPS/MF 13/2026. Os índices intermediários têm referência normativa na memória (`pension_revaluation`); as cópias das portarias de 2021, 2022, 2023 e 2026 estão preservadas. As portarias de 2024 e 2025 são referenciadas, mas suas cópias não foram obtidas nesta execução. Trata-se de reconstrução legal explícita, não transcrição de tabela estadual publicada. Confronte especialmente o arredondamento das faixas com o contracheque.

Cargos/funções respeitam a opção contributiva informada. No regime com teto, aplica-se R$8.475,55 à base RPPS; a contribuição complementar usa o percentual informado sobre o excedente. Terço de férias usufruídas não integra RPPS (STF, Tema 163); não são simuladas férias indenizadas.

## IPSEMG

Lei 25.143/2025, arts.4º e 6º, e Decreto 48.981/2025, arts.4º–5º. As cópias legais estão preservadas. A regra de revisão monetária do art.6º, §4º, aplicada à revisão geral de 5,4% da Lei 25.804/2026, resulta em piso R$63,24, teto básico R$527,00 e filho de 21 a 38 anos R$94,86.

- Titular, cônjuge, pais e irmãos elegíveis: 3,2%, observados piso e teto individuais.
- Desde 59 anos (última faixa ANS), adicional de 1% com limite próprio de R$527,00, sem consumir o teto da contribuição básica, conforme §3º. A memória separa a contribuição regular e o adicional.
- Filho menor de 21 anos: R$63,24, dentro do teto básico conjunto com o titular. De 21 a 38 anos: R$94,86.
- Até dois salários mínimos (R$3.242): 3,2%, sem piso nem adicional etário; menores de 21 isentos e filhos de 21 a 38 limitados a R$94,86.
- Filho com condição especial só é tratado como isento se a aprovação do IPSEMG for confirmada. O diagnóstico isolado bloqueia a simulação. Pais/irmãos exigem confirmação de elegibilidade/dependência econômica e não podem ser acumulados com cônjuge/filhos; irmãos também não podem ser acumulados com pais. Não há concessão automática de direitos.
- A base inclui 13º e remuneração de férias usufruídas. Verbas indenizatórias dependem das incidências de cada rubrica. Coparticipação é informada separadamente e não se repete no 13º.

## IRRF e projeções

A tabela e os exemplos da Receita Federal de 2026 estão preservados com URL e SHA-256. Dedução por dependente R$189,59; simplificado mensal R$607,20; seleciona-se a dedução mais vantajosa. IPSEMG não é contribuição previdenciária dedutível na retenção mensal.

A redução usa o rendimento tributável antes das deduções: até R$5.000, limitada a R$312,89; até R$7.350, `978,62 − 0,133145 × rendimento`, limitada ao imposto calculado. A dispensa mensal de retenção até R$10 (Lei 9.430/1996, art.67) não se aplica ao 13º de tributação exclusiva. A memória distingue imposto calculado, redução, dispensa e imposto retido.

Férias e 13º têm folhas próprias. O anual soma 11 folhas normais, uma folha com férias e terço e o 13º integral; não soma o salário das férias duas vezes. É uma projeção estática de retenções, não ajuste anual do IR nem previsão de remunerações futuras.

## Evidências e limites

O JSON exportado contém fontes, hashes, incidências, faixas aplicadas, atualização anual RPPS e ressalvas. `scripts/build_payroll_data.py` reproduz o conjunto a partir das cópias locais; não consulta rede ao iniciar o serviço nem lê fixtures demonstrativas. Mudanças exigem nova versão.

O status `verified` significa conferência dos parâmetros implementados; não representa certificação estatal, auditoria independente ou conciliação com contracheques. A opção A, RRA de anos anteriores e consolidação de vínculos/fontes foram implementados em [rotinas próprias](folhas-especificas.md). Aposentados, isenções fora das hipóteses cadastradas, pensão percentual e avos proporcionais exigem rotinas próprias. As entradas de regime, decisões judiciais, opções contributivas e elegibilidade devem corresponder aos atos do vínculo.
