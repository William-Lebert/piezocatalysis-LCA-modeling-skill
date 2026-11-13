# 合成参数重算 / Synthetic parameter recalculation

该案例使用完全虚构的模型和影响因子，在真实 openLCA 引擎内逐个覆盖参数重新计算。模型公式为 `(power × hours + 2 / reuse) × 1.6`，基准参数分别为 2、1、2：基准 4.8；单独将功率、时间、复用次数各翻倍，结果分别为 8、8、4（虚构影响单位）。它用于验证机制，不是实际研究结果。

在已安装 macOS openLCA 2.7.0 的系统上，从仓库根目录运行真实引擎集成验证：

```sh
python3 tests/integration_openlca_parameters.py
```

该测试创建临时合成数据库，计算两遍，核对结果、只读限制和源库内容哈希，然后清理测试库。`scenarios.template.json` 中的 UUID 只是占位符；测试每次创建新 UUID，不能直接用于真实计算。

## 对已有产品系统使用

先查阅产品系统中实际可用的参数；指定数据库名称和工作区：

```sh
python3 scripts/openlca_readonly.py --start-local --workspace /path/to/openLCA-data-1.4 \
  --database YOUR_DATABASE \
  parameters --system-id YOUR_PRODUCT_SYSTEM_UUID
```

复制 `scenarios.template.json` 为新的本地文件，填入产品系统、方法、功能流单位和属性 UUID、功能单位、研究边界、数据库及 LCIA 方法版本和映射说明。每个情景填写从参数查询获得的**准确参数名及所属过程的 UUID**；全局参数的 `context_id` 写 `null`。填写参数单位、值、来源和证据类别；`minimum` / `maximum` 为按实际物理意义设定的可选边界，不能凭空认为参数一定有效。

```sh
python3 scripts/parameter_sensitivity.py /path/to/your-scenarios.json \
  --start-local --workspace /path/to/openLCA-data-1.4 --database YOUR_DATABASE \
  --summary /path/to/new-summary.json \
  > /path/to/new-private-report.json
```

每个情景只改变一个参数，其余采用模型基准值；程序查询参数并校验名称和上下文，拒绝缺失、同一上下文不唯一、受保护、无效或超过所声明边界的参数，随后在 openLCA 中分别进行基准和各情景的实际计算。参数是否被模型中的公式使用及其单位需要事先核对；未被使用的参数改变后可能不会影响结果。比较以相同影响类别 UUID、名称和单位为前提，基准为零时百分比为 null。运行记录包括输入及代码哈希、时间、模型和方法 UUID、功能单位、用户提供的数据库及映射信息、模型基准参数、每个重算结果与差值。受控启动还记录数据库路径、文件大小和修改时间的摘要；这**不是**数据库内容哈希。已有本机服务可改用 `--port PORT`，数据库身份由使用者核对。

默认使用 `/Applications/openLCA.app`；其他安装路径可通过 `--openlca-app` 指定。标准输出包含完整数据，可能含有许可数据库信息；`--summary` 生成不含数据库和参数名称的相对变化摘要，发布前仍需检查内容和许可。两个输出路径都应是新文件；程序仅保证摘要不覆盖已有文件，shell 重定向可能覆盖完整报告。不要把情景百分比当作概率或不确定性分布。具体参数单位、背景数据和方法的适用性仍需结合模型审核。

与 `scripts/sensitivity_report.py` 不同，本工具真正重算 openLCA 模型；原脚本只是对给定的非重叠贡献做线性、反比或替代值估算。上述虚构公式在明确的可加条件下两者数值相同；不代表复杂模型一定相同。缺少有依据的分布和相关性时先报告情景结果，不生成蒙特卡洛概率结论。
