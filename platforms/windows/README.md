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

运行前核对活动数据库，结束后关闭自行启动的 IPC。Windows 自动启动、隔离副本与 SimaPro COM 的开发和实际联调继续在 Windows 上验证。公共流程使用同一套 CSV、JSON 和功能单位规则。

[双平台布局](../README.md) · [openLCA 工作流](../../piezocatalysis-lca-modeling/references/openlca-workflow.md)
