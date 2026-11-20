# Windows 与 macOS 开发入口

两个平台从同一个 `main` 开发，共用一次版本发布。克隆仓库后，按系统选入口。

- [Windows](windows/README.md) 使用 PowerShell，运行共用工具和测试，openLCA 由用户启动并通过本机 IPC 连接。
- [macOS](macos/README.md) 使用终端，运行同一套工具和测试。匹配验证环境时可让 Skill 临时启动 openLCA，再在副本中计算。

## 仓库布局

| 目录 | 放什么 |
| --- | --- |
| `piezocatalysis-lca-modeling/` | 可单独安装的 Skill。包含共有的证据、清单、映射、计算接口、图表、交付代码、模板和示例。 |
| `platforms/windows/` | Windows 上的开发、测试和本机软件接入说明，供 Windows 专用入口后续扩展。 |
| `platforms/macos/` | macOS 上的开发、测试和本机软件接入说明。现有受控启动器随 Skill 安装。 |
| `tests/` | 两端共用的测试和合成样例。 |
| `docs/` | 版本说明、迁移、科研验收及回滚记录。 |
| `.github/workflows/` | 用 Windows 和 macOS 分别运行共用测试。 |

涉及功能单位、单位换算、科研规则或输出格式的改动放在 Skill 的共有代码中。系统路径、软件安装或进程管理的改动从对应平台入口着手。有新任务时，从 `main` 开出短期分支，例如 `codex/windows-ipc` 或 `codex/macos-launch`，同一份测试通过后合并。两端可各自保存本机软件配置和授权数据库。提交仓库的验证输入采用合成数据，Git 保留证据表和 JSON 的原始字节，以便两台机器读到相同的文件哈希。

自动测试核对 Python 流程和合成样例。openLCA、ecoinvent 和 SimaPro 的真实接入另用对应系统上的授权安装验收。
