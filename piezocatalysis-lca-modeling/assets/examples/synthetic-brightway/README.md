# 第 5 批：高级引擎可行性记录

日期：2026-11-07。结论：**Brightway 可作为独立可选实验工具；暂不加入项目的运行依赖。** 参数化、全局敏感性和未来情景暂缓接入，待明确研究问题、输入假设和授权后分别验证。此例没有读取、复制或转换 ecoinvent，未运行 lca_algebraic 或 premise。

## 合成案例与复现

运行环境：macOS Apple Silicon、Python 3.9.6；`bw2calc==3.1.0`、`bw2data==4.8`、`bw_processing==1.6`，完整已安装版本见同目录 `requirements-verified-macos-python39.txt`。这份冻结清单记录本次求解后的版本，不含下载哈希，不保证其他平台、Python 版本或未来仍可安装；它不是主项目依赖，也不是安全审计。

仅在独立虚拟环境安装并运行（需要联网获取公开软件包）：

```sh
python3.9 -m venv /tmp/piezolca-bw-example-env
/tmp/piezolca-bw-example-env/bin/python -m pip install -r requirements-verified-macos-python39.txt
/tmp/piezolca-bw-example-env/bin/python calculate.py
```

命令在本目录执行。脚本在导入 Brightway 前创建独立临时数据目录，设置 `BRIGHTWAY2_DIR`，在其中写入虚构数据，结束后清除临时项目；不操作已有 Brightway/openLCA 项目。若进程异常终止，系统临时目录可能残留该次合成数据。

合成过程生产 1 单位虚构产品，排放 2 kg 虚构物质，虚构表征因子 1.6。需求分别为 1 和 2 时，Brightway 返回约 3.2 和 6.4，与手算一致；1 单位的 3.2 也与此前 openLCA 2.7.0 独立合成案例的数值相符。两边数值均为人为构造，不能据此确认真实模型及数据库之间的映射或一致性。Brightway 本次实际值为 3.200000047683716，采用相对误差 1e-6 核对，不能依赖展示的小数位数判断精度。案例无区域信息，运行时会提示不支持区域化；缺少可选高性能求解器也会提示性能影响。

## 依赖及引擎评估

- 参考包中旧版 brightway2 把 `bw2calc==1.8.2`、`bw2data==3.6.6` 和 `bw2io==0.8.12` 固定在旧系列；另一个 bw2io 快照要求 `bw2calc>=2.0`、`bw2data>=4.6.2`。不得混装。旧版与新版应使用不同虚拟环境和独立项目，迁移前先备份并验证。实际演示使用的是上述 PyPI 固定版本，而非声称运行了参考包快照。
- [lca_algebraic 官方仓库](https://github.com/oie-mines-paristech/lca_algebraic) 分别提供旧 Brightway 和新版的包；其参数化和 Sobol 功能尚未在本机运行。参考包 pyproject 标注 Python >=3.10,<3.14，README 标注 >=3.10,<3.13，存在差异。应针对具体发行版验证，而非假定统一兼容。本机默认 Python 3.9.6 不满足参考包的下限。
- 在实施蒙特卡洛或 Sobol 前，须明确每个参数的单位、来源、分布和范围、参数间相关性、抽样方法、样本数、随机种子、收敛性及输出指标。标准 Sobol 分解通常假定输入独立；如参数相关，应选用有相应理论支持的方法，不能直接将结果解释为独立因素贡献。本项目第 4 批单因素报告也不是全局敏感性分析。
- [premise 文档](https://premise.readthedocs.io/en/latest/getting_started/installation.html)要求独立兼容环境，当前版本要求 Python 3.12 或更高；其[来源数据库说明](https://premise.readthedocs.io/en/latest/user_guide/source-databases.html)要求用户持有有效 ecoinvent 许可并核对许可条款。需确认 ecoinvent 3.9.1 cutoff 是否允许拟议用途、转换及结果分发，并记录具体 premise 版本、IAM 模型、路径、年份、地理范围、数据库版本及 LCIA 方法；部分 IAM 文件需要密钥。许可及 IAM 访问目前未核实，不能据此创建或发布情景数据库。预测情景是条件化模型，不是实测。
- 软件包各自许可证与商业数据库许可是两回事；本批未复用参考包代码或分发商业数据。正式引入前需再核对所有实际依赖的许可证与分发义务。

## 成本和下一步

本次公开软件包下载无已知收费，未使用付费服务；临时虚拟环境约 215 MB（不含 pip 缓存），时间和实际费用未单独计量。尚未评估真实大型数据库的运行时间、内存、存储或许可费用。是否做进一步集成，取决于明确的压电催化研究问题、经审查的参数和可用授权。新环境必须与现有 openLCA 和数据库分离，且每次引入前锁定并验证版本。
