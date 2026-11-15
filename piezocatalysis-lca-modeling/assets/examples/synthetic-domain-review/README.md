# 压电催化领域服务与证据检查

本目录四份均为虚构声明，分别示范处理水量、污染物表观去除、H2O2 产品和干催化剂制备。它们不是实测数据，也不是可直接用于研究的完整 LCA。可从 `assets/templates/domain_review.template.json` 出发填写；按功能类型补齐对应的必填字段。

```sh
python3 piezocatalysis-lca-modeling/scripts/domain_review.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-domain-review/apparent_pollutant_removal.json \
  --compare piezocatalysis-lca-modeling/assets/examples/synthetic-domain-review/h2o2_product.json
```

字段 `status` 为 `provided`、`missing` 或 `not_applicable`。提供的文本或数值须有 `source` 和 `evidence_class`；数值还须有单位与 `basis`（例如每批、每轮或每份样品）。`not_applicable` 须给出原因。未填写的字段保留缺口，零值要以明确的数值 0 给出。出水低于检出限／定量限时，使用 `qualifier=below_lod`／`below_loq`、`value=null` 和正数 `limit`；四个进出水体积与浓度字段应使用相同的批次／循环 `basis`；脚本仅在基准一致且信息足够时给出水相表观质量差区间，不代零、不宣称矿化或闭合质量平衡。

对已有前景清单可同时指定 `--inventory` 与 `--manifest`；可再指定 `--mapping` 与 `--assignments`。工具使用现有交接检查哈希和每功能单位基准，再核对声明的服务类型、功能单位及边界；可用 `--source-input` 核对原始前景输入与 manifest 的 SHA-256。领域声明中的数值不会自动与原始输入或模型交换逐项比对，仍须人工核实。H2O2 另外核对产品基准与定义。映射仍是人工声明，代理、缺口和模型警告会保留。`--compare` 只检查服务、污染物／产品、指定边界等声明；LCIA 方法、数据库、映射、功能性能和数据质量仍须审查，不能仅凭此选项自动排名。

H2O2 的 `net_accumulated`、`gross_generated`、`recovered_product` 和 `in_situ_consumed` 是不同声明。现有 `h2o2_foreground.py` 只计算净积累或回收产品基准，不会自动推算总生成量或原位消耗。处理水量和催化剂制备在本目录提供服务定义与证据检查；其他相应计算应使用现有工具并单独核对清单基准。完整研究和公开报告还应复核 [领域研究检查表](../../../references/domain-quality-checklist.md)。
