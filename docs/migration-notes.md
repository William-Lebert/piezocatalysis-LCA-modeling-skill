# Migration notes / 迁移说明

The inventory, evidence and delivery schemas and command-line options remain unchanged. A cyclic inventory whose `evidence_class` or `source` differs from the foreground is now rejected by `evidence_chain.py` and `research_delivery.py`, even if its inventory hash was updated. Regenerate an inventory and paired manifest from the original foreground after correcting the underlying evidence, then rerun dependent audits and deliveries to new paths. If an inventory record legitimately needs different provenance, record that change in the foreground and rebuild; do not simply edit the manifest hash.

`workflow_state.py` is optional and introduces independent local stage records. It does not validate old artifacts by their existence alone, alter existing reports, infer missing dependencies or replace scientific review. Its absolute paths mean records need to be recreated after moving files.

When a basis is written as `cycle-<cycle_id>` for a known cycle, evidence links to a different foreground cycle now fail. Correct the source record and regenerate dependent evidence reports. Custom basis labels remain user assertions and need review.

逐循环清单的证据类别或来源与前景不一致时，证据审查和交付现在会拒绝该清单。请修正前景记录并重新生成清单及 manifest，再重新生成受影响的审查和交付；不要只修改清单摘要。新的阶段记录为可选功能，不改变现有数据格式或审批权限。
