# Scenario context check

Use `python3 piezocatalysis-lca-modeling/scripts/scenario_comparability.py <file>` before interpreting differences between independently declared scenarios. Inputs here are fictional. `comparable.json` returns exit code 0; `not-comparable.json` returns 2 and identifies the different functional unit. The command checks declared functional unit, boundary, geography, period, database and system model, LCIA method, allocation, reuse, electricity scenario and mapping scope. Missing or inconsistent declarations block the context check. Matching text is not independent verification of database identity or modeling assumptions; the tool does not rank impacts or change the calculation.

从项目根目录运行上述命令；先填报研究者已核对的功能单位、边界、地域、时间、数据库、系统模型、方法、分配、复用、电力情景及映射范围。字段不一致或缺失时退出码为 2，不应给出无条件排名；字段一致只表示声明一致，仍需人工检查数据与模型。对于同一产品系统的单参数实际重算，功能单位、边界和 LCIA 设置保持一致，但参数变化本身仍需有科学依据。
