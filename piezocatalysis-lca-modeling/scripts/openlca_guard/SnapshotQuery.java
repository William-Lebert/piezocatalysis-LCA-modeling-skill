import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import gnu.trove.map.hash.TLongLongHashMap;
import org.objectweb.asm.*;
import org.openlca.core.database.NativeSql;

public final class SnapshotQuery {
  static final String WRITER = "org/openlca/jsonld/output/ProductSystemWriter";
  private static final String SCAN = "select id, internal_id from tbl_exchanges";
  private static final String QUERY = "(Ljava/lang/String;Lorg/openlca/core/database/NativeSql$QueryResultHandler;)V";
  private static final int BATCH_SIZE = 256;
  private static final int MAX_INDEXED_IDS = 4096;

  private SnapshotQuery() {}

  public static void query(NativeSql sql, String statement, NativeSql.QueryResultHandler onRow,
      TLongLongHashMap required) {
    if (!SCAN.equals(statement)) throw new IllegalStateException("unexpected exchange ID query");
    if (required.size() > MAX_INDEXED_IDS) {
      // Keep the scan for large systems to bound the number of index queries per snapshot.
      sql.query(statement, onRow);
      return;
    }
    long[] ids = required.keys();
    for (int start = 0; start < ids.length; start += BATCH_SIZE) {
      int count = Math.min(BATCH_SIZE, ids.length - start);
      List<Object> values = new ArrayList<>(count);
      for (int i = start; i < start + count; i++) values.add(ids[i]);
      String placeholders = String.join(",", Collections.nCopies(count, "?"));
      sql.query(SCAN + " where id in (" + placeholders + ")", values, onRow);
    }
  }

  static byte[] transform(byte[] code) {
    // In the hash-checked core JAR, exchangeIDs stores its map in local slot 2.
    // Redirect only the full-table query and keep upstream's row handler and JSON writer.
    final int[] rewritten = {0};
    ClassReader reader = new ClassReader(code);
    ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS);
    reader.accept(new ClassVisitor(Opcodes.ASM9, writer) {
      @Override public MethodVisitor visitMethod(int access, String name, String desc,
          String signature, String[] exceptions) {
        MethodVisitor next = super.visitMethod(access, name, desc, signature, exceptions);
        if (!name.equals("exchangeIDs")
            || !desc.equals("(Lorg/openlca/core/model/ProductSystem;)Lgnu/trove/map/hash/TLongLongHashMap;")) {
          return next;
        }
        return new MethodVisitor(Opcodes.ASM9, next) {
          private boolean sawScan;

          @Override public void visitLdcInsn(Object value) {
            if (SCAN.equals(value)) sawScan = true;
            super.visitLdcInsn(value);
          }

          @Override public void visitMethodInsn(int opcode, String owner, String method,
              String descriptor, boolean isInterface) {
            if (sawScan && opcode == Opcodes.INVOKEVIRTUAL
                && owner.equals("org/openlca/core/database/NativeSql")
                && method.equals("query") && descriptor.equals(QUERY)) {
              super.visitVarInsn(Opcodes.ALOAD, 2);
              super.visitMethodInsn(Opcodes.INVOKESTATIC, "SnapshotQuery", "query",
                  "(Lorg/openlca/core/database/NativeSql;Ljava/lang/String;"
                  + "Lorg/openlca/core/database/NativeSql$QueryResultHandler;"
                  + "Lgnu/trove/map/hash/TLongLongHashMap;)V", false);
              rewritten[0]++;
            } else {
              super.visitMethodInsn(opcode, owner, method, descriptor, isInterface);
            }
          }
        };
      }
    }, 0);
    if (rewritten[0] != 1) throw new IllegalStateException("unexpected product system writer");
    return writer.toByteArray();
  }
}
