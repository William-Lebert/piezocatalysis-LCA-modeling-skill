# macOS 开发

从仓库根目录在终端运行。示例使用 Python 3.11。

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r piezocatalysis-lca-modeling/assets/examples/synthetic-plotting/requirements.txt
.venv/bin/python -m unittest discover -s tests
```

Agent 使用仓库中的 `piezocatalysis-lca-modeling/`。已有受信任的 IPC 时，可以指定端口。在项目验证过的 macOS openLCA 2.7.0 构建上，也可以为已有库启动受控本机 IPC。将 `DATABASE_NAME` 替换为本机库名，工作区以实际位置为准。

```sh
.venv/bin/python piezocatalysis-lca-modeling/scripts/openlca_readonly.py \
  --start-local --workspace "$HOME/openLCA-data-1.4" --database DATABASE_NAME \
  list --type ProductSystem
```

受控启动器核验程序和组件，使用数据库临时副本，并在命令结束后停止服务。切换 openLCA 版本或安装来源时，先按工作流核验，再做真实计算。结果仍按共用清单和交付格式保存。

[双平台布局](../README.md) · [openLCA 工作流](../../piezocatalysis-lca-modeling/references/openlca-workflow.md)
