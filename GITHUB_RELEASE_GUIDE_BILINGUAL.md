# GitHub Release Guide / GitHub 发布指南

## Repository layout / 仓库结构

Keep this release root as the repository root. The installable Skill remains in the `piezocatalysis-lca-modeling/` subfolder so user documentation does not pollute the Skill context.

建议将本发布目录作为仓库根目录。可安装 Skill 保留在 `piezocatalysis-lca-modeling/` 子目录中，使用户文档不会污染 Skill 上下文。

## Pre-publication checklist / 发布前检查

- [ ] Remove all private paths, names, credentials, license keys, and unpublished measurements.
- [ ] Confirm that no ecoinvent, CLCD, SimaPro, or other commercial database content is bundled.
- [ ] Confirm that the original source DOCX and copyrighted articles are absent.
- [ ] Run the Skill validator and bundled sample checks.
- [ ] Add repository topics such as `lca`, `piezocatalysis`, `openlca`, `simapro`, and `research-reproducibility`.
- [ ] Create a tagged release such as `v1.0.0` and attach the ZIP.

- [ ] 删除私人路径、姓名、凭据、许可证密钥与未公开实验数据。
- [ ] 确认未打包 ecoinvent、CLCD、SimaPro 或其他商业数据库内容。
- [ ] 确认原始 DOCX 与受版权保护的论文不在发布包中。
- [ ] 运行 Skill 校验器和内置示例测试。
- [ ] 添加 `lca`、`piezocatalysis`、`openlca`、`simapro`、`research-reproducibility` 等主题。
- [ ] 创建 `v1.0.0` 等标签发布并附加 ZIP。

## Suggested repository description / 建议仓库简介

Research-grade Codex Skill for reproducible LCA and EE/O modeling of piezocatalysis, photocatalysis, and piezo-photocatalysis systems in openLCA and SimaPro.

用于 openLCA 与 SimaPro 中压电催化、光催化和压电光催化体系可复现 LCA 与 EE/O 建模的科研级 Codex Skill。
