"""Run a fictional LCA in a fresh, temporary Brightway project."""
import math
import os
import tempfile

# bw2data resolves its data directory on import. Never use an existing project.
with tempfile.TemporaryDirectory(prefix="piezolca-brightway-synthetic-") as directory:
    os.environ["BRIGHTWAY2_DIR"] = directory
    import bw2data as bd
    import bw2calc as bc

    bd.projects.set_current("synthetic_only")
    bd.Database("synthetic_flows").write({
        ("synthetic_flows", "emission"): {
            "name": "fictional emission", "unit": "kg", "type": "emission"
        }
    })
    bd.Database("synthetic_processes").write({
        ("synthetic_processes", "product"): {
            "name": "fictional product", "unit": "unit", "type": "process",
            "exchanges": [
                {"input": ("synthetic_processes", "product"), "amount": 1,
                 "unit": "unit", "type": "production"},
                {"input": ("synthetic_flows", "emission"), "amount": 2,
                 "unit": "kg", "type": "biosphere"},
            ],
        }
    })
    method = ("synthetic", "fictional impact")
    bd.Method(method).register(unit="fictional impact units")
    bd.Method(method).write([(("synthetic_flows", "emission"), 1.6)])
    product = bd.get_activity(("synthetic_processes", "product"))
    for amount in (1, 2):
        demand, data_objs, _ = bd.prepare_lca_inputs({product: amount}, method=method)
        lca = bc.LCA(demand=demand, data_objs=data_objs)
        lca.lci()
        lca.lcia()
        expected = amount * 2 * 1.6
        if not math.isclose(lca.score, expected, rel_tol=1e-6, abs_tol=1e-9):
            raise AssertionError(f"Expected {expected}, got {lca.score}")
        print(f"demand={amount}; Brightway={lca.score:.6f}; hand={expected:.6f}")
