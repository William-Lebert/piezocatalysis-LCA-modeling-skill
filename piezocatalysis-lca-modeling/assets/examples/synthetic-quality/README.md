# 合成逐循环实验数据质量检查

本文件的三批记录、地区、校准文字和数据均为虚构，不是实测重复，也不支持推断真实研究的概率分布。第三批特意设置干产率缺失、第二轮出水低于定量限以及催化剂损失；最终催化剂没有处置映射。第一轮功率／时间以虚构的三组成对设置演示描述性相关，不能作为实际工况相关性证据。

在仓库根目录运行：

```sh
python3 piezocatalysis-lca-modeling/scripts/experimental_quality.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-quality/synthetic-campaigns.json \
  > /tmp/piezolca-synthetic-quality.json
```

输出保留每个批次与循环的原始数量、单位、来源、证据类型、删失状态和限值，并标出缺失值、缺测批次、异常催化剂损失、未说明处置和关联／分布依据缺口。仅对单位一致的精确记录计算描述统计；删失值不代入零或半个限值，缺失量也不填零。功率与时间成对保留，至少三对且两者有变化时提供描述性 Pearson 相关，不能由此认定独立或拟合分布。批次是否独立、校准、代表性、数据量和研究边界由研究者判断。

真实背景可以对选定模型和方法类别做只读定向字段盘点：

```sh
python3 piezocatalysis-lca-modeling/scripts/openlca_uncertainty_inventory.py --help
```

该工具统计 IPC 响应中的非空 `uncertainty` 字段，并不证明数据库没有其他不确定性数据，也不代表字段缺失就是零。完整结果可能含有受许可约束的过程名称；分享前应核对许可。需要使用有依据分布时，先结合 `uncertainty_readiness.py` 和实际数据审查；本演示不自动拟合分布。
