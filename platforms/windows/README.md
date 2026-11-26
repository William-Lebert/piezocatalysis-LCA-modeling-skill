# Windows 开发

从仓库根目录在 PowerShell 中运行。示例使用 Python 3.11。

```powershell
py -3.11 -m venv .venv
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m pip install -r piezocatalysis-lca-modeling/assets/examples/synthetic-plotting/requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

将仓库中的 `piezocatalysis-lca-modeling/` 加载到 Agent 后，可以直接运行共用的实验导入、清单、审查、图表和交付。需要接入 openLCA 时，在 Windows 的 openLCA 中打开本机数据库并启动 IPC，在受信任的本机环境下用实际端口连接。下面以端口 8080 为例。

```powershell
.\.venv\Scripts\python.exe piezocatalysis-lca-modeling/scripts/openlca_readonly.py --port 8080 list --type ProductSystem
```

## 手动 IPC 真机验收

用同一份虚构数据库副本和 `fixture.json` 进行跨平台对照。模型由 `tests/fixtures/create_openlca_synthetic.py` 以 33 个供应过程生成。两台机器使用同一次生成的数据集，确保系统、过程、方法和类别的 UUID 相同。

在 openLCA 打开该测试库，从 **Tools → Developer tools → IPC Server** 启动标准 IPC。以下示例用 8080 端口。参见 [openLCA IPC 官方说明](https://greendelta.github.io/openLCA-ApiDoc/intro.html)。

```powershell
.\.venv\Scripts\python.exe tests/integration_openlca_manual_ipc.py `
  --port 8080 --fixture .\fixture.json `
  --compare .\macos-reference.json --output .\windows-ipc-evidence.json
```

脚本核对两个计算量的 LCIA、贡献、总清单流和快照，再用 1 ms 的等待预算触发超时。在释放后及一次恢复计算后，都用原结果 ID 查询服务端状态。输出中记录实际运行平台。使用新输出路径，结束后在 openLCA 停止测试 IPC。

若已在 Windows 准备好与归档完全对应的情景数据库，可用 `scenario_suite.py rerun <归档 JSON> --port 8080 --output <新输出 JSON>` 复算。该流程使用同一套 CSV、JSON 和功能单位规则。

[双平台布局](../README.md) · [openLCA 工作流](../../piezocatalysis-lca-modeling/references/openlca-workflow.md)
