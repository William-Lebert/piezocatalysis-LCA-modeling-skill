# Local openLCA guard

This project-authored Java agent is a narrowly version-locked compatibility safeguard for the signed macOS openLCA 2.7.0 build documented in `references/openlca-workflow.md`. It does not replace openLCA or copy its implementation. At JVM class-load time the guard modifies the tested server's bind address to `127.0.0.1`, removes all RPC handlers except single-entity, descriptor and parameter reads and temporary calculation/result operations, and exits when the parent pipe closes. If the expected bytecode or method registry is not found it aborts instead of starting an unrestricted server. The Python launcher separately verifies component hashes, publisher signature and listening address, and starts it only with a temporary APFS database clone.

The guard supports the exact signed runtime checked by `openlca_local_launch.py`. The optional product-system optimization also checks the core and Trove JAR hashes. It redirects the existing writer's exchange ID query in the temporary JVM. For up to 4,096 referenced IDs it uses parameterized primary-key lookups in batches of 256. Larger ID sets and other compatible component builds use the original query. The writer runs on every request, preserving the original JSON representation and the two independent reads around each calculation. The optimization runs in the temporary IPC process against the APFS database clone. [openLCA 2.7.0 writer](https://github.com/GreenDelta/olca-modules/blob/v2.7.0/olca-core/src/main/java/org/openlca/jsonld/output/ProductSystemWriter.java#L105-L127)

In that same pinned runtime, `DescriptorLookup.java` changes the writer's descriptor map to load individual references using the existing DAO's ID lookup. After 32 distinct lookups for one entity type in an export, it loads the original full map. The JSON export still supplies its own fields and content. [openLCA descriptor resolver](https://github.com/GreenDelta/olca-modules/blob/v2.7.0/olca-core/src/main/java/org/openlca/jsonld/output/JsonRefs.java)

The openLCA executable and its Java libraries are external dependencies from the user's verified installation. `localhost-agent.jar` contains only this project's compiled classes and manifest. Localhost access is unauthenticated.

## Reproduce the agent binary

`LocalhostAgent.java`, `SnapshotQuery.java` and `DescriptorLookup.java` are the sources. The builder verifies the separately obtained Eclipse ECJ compiler version 3.42.0 and the installed ASM, olca-core and Trove JARs against pinned SHA-256 values. These dependencies are obtained separately.

```sh
olca_libs=/Applications/openLCA.app/Contents/Eclipse/plugins/olca-app_2.7.0/libs
python3 piezocatalysis-lca-modeling/scripts/openlca_guard/build_agent.py \
  --java /Applications/openLCA.app/Contents/Eclipse/jre/Contents/Home/bin/java \
  --compiler /path/to/ecj-3.42.0.jar \
  --asm "$olca_libs/asm-9.9.1.jar" \
  --core "$olca_libs/olca-core-2.7.0.jar" \
  --trove "$olca_libs/trove4j-3.0.3.jar" \
  --output /tmp/localhost-agent-rebuilt.jar
```

Expected SHA-256 is `203b26bebb9fdea6e7207878ef81bdd0338176df44bffae7d579c753df77bd3e`. Verify with `shasum -a 256 /tmp/localhost-agent-rebuilt.jar`. The script requires a new output file. After editing the sources, review the rebuilt JAR, update the pinned guard hash in the launcher, and rerun the real software integration tests.
