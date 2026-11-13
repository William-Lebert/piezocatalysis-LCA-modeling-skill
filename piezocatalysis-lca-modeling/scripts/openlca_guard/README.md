# Local openLCA guard

This project-authored Java agent is a narrowly version-locked compatibility safeguard for the signed macOS openLCA 2.7.0 build documented in `references/openlca-workflow.md`. It does not replace openLCA or copy its implementation. At JVM class-load time the guard modifies the tested server's bind address to `127.0.0.1`, removes all RPC handlers except descriptor reads and temporary calculation/result operations, and exits when the parent pipe closes. If the expected bytecode or method registry is not found it aborts instead of starting an unrestricted server. The Python launcher separately verifies component hashes, publisher signature and listening address, and starts it only with a temporary APFS database clone.

This guard is limited to the exact pinned component hashes in `openlca_local_launch.py`; a different build or future version fails closed and requires fresh review and integration tests. The openLCA executable and ASM library are external dependencies from the user's verified installation, not included in this folder. `localhost-agent.jar` contains only the project's compiled guard classes and manifest. Localhost access is not authenticated, and this is not a substitute for OS-level isolation or an external security audit.

## Reproduce the agent binary

`LocalhostAgent.java` is the source. `build_agent.py` expects the independently obtained Eclipse ECJ compiler version 3.42.0 (SHA-256 `29f6d3918ee02db4400c103bc25dd90a22491c3a395867d9393070cb96a7dd29`) and the ASM 9.9.1 jar from the verified openLCA 2.7.0 app (SHA-256 `6f3828a215c920059a5efa2fb55c233d6c54ec5cadca99ce1b1bdd10077c7ddd`). The compiler is a build tool and is not distributed here. For example, using an existing compiler file and a new output path:

```sh
python3 piezocatalysis-lca-modeling/scripts/openlca_guard/build_agent.py \
  --java /Applications/openLCA.app/Contents/Eclipse/jre/Contents/Home/bin/java \
  --compiler /path/to/ecj-3.42.0.jar \
  --asm /Applications/openLCA.app/Contents/Eclipse/plugins/olca-app_2.7.0/libs/asm-9.9.1.jar \
  --output /tmp/localhost-agent-rebuilt.jar
```

Expected JAR SHA-256: `d0ee680936b9e5f13e69816da09af9389cad2a36dd260b4d33b6e88c08ac2595`. Verify with `shasum -a 256 /tmp/localhost-agent-rebuilt.jar`. The script refuses to overwrite an existing output. Runtime hash verification rejects a different agent binary; after changing source, review the generated binary and update the pinned hash deliberately.
