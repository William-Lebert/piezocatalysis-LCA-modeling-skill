import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import javax.sql.rowset.CachedRowSet;
import javax.sql.rowset.RowSetProvider;
import org.objectweb.asm.*;
import org.openlca.core.database.IDatabase;
import org.openlca.core.database.NativeSql;
import org.openlca.core.matrix.index.ImpactIndex;

public final class ImpactFactorQuery {
  static final String BUILDER = "org/openlca/core/matrix/ImpactBuilder";
  private static final String DATABASE = "Lorg/openlca/core/database/IDatabase;";
  private static final String INDEX = "Lorg/openlca/core/matrix/index/ImpactIndex;";
  private static final String SQL = "org/openlca/core/database/NativeSql";
  private static final String ARGS = "Ljava/lang/String;L" + SQL + "$QueryResultHandler;";
  private static final String SCAN = "SELECT f_impact_category, f_flow, value, formula, f_flow_property_factor,"
      + " f_unit, distribution_type, parameter1_value, parameter2_value, parameter3_value, f_location"
      + " FROM tbl_impact_factors";
  private static final int MAX_CATEGORIES = 64;
  private static final int MAX_ROWS = 16384;
  private static final ThreadLocal<Factors> recent = new ThreadLocal<>();

  private ImpactFactorQuery() {}

  private static final class Factors {
    final IDatabase db;
    final long[] categories;
    final CachedRowSet rows;

    Factors(IDatabase db, long[] categories, CachedRowSet rows) {
      this.db = db;
      this.categories = categories;
      this.rows = rows;
    }
  }

  public static void query(NativeSql sql, String statement, NativeSql.QueryResultHandler consume,
      IDatabase db, ImpactIndex impacts) throws SQLException {
    if (!SCAN.equals(statement)) throw new IllegalStateException("unexpected impact factor query");
    int count = impacts.size();
    if (count == 0 || count > MAX_CATEGORIES) {
      sql.query(statement, consume);
      return;
    }
    long[] categories = new long[count];
    for (int i = 0; i < count; i++) categories[i] = impacts.idAt(i);
    Factors factors = recent.get();
    if (factors == null || factors.db != db || !Arrays.equals(factors.categories, categories)) {
      factors = new Factors(db, categories, readSelected(db, categories));
      recent.set(factors);
    }
    if (factors.rows == null) {
      sql.query(statement, consume);
      return;
    }
    factors.rows.beforeFirst();
    while (factors.rows.next() && consume.accept(factors.rows)) { }
  }

  private static CachedRowSet readSelected(IDatabase db, long[] categories) throws SQLException {
    String placeholders = String.join(",", Collections.nCopies(categories.length, "?"));
    CachedRowSet rows = RowSetProvider.newFactory().createCachedRowSet();
    try (Connection con = db.createConnection();
         PreparedStatement read = con.prepareStatement(SCAN + " WHERE f_impact_category IN (" + placeholders + ")")) {
      read.setMaxRows(MAX_ROWS + 1);
      for (int i = 0; i < categories.length; i++) read.setLong(i + 1, categories[i]);
      try (ResultSet result = read.executeQuery()) {
        rows.populate(result);
      }
    }
    if (rows.size() > MAX_ROWS) return null;
    Set<List<Long>> seen = new HashSet<>();
    while (rows.next()) {
      long location = rows.getLong(11);
      // Duplicate keys can change the last factor written to a cell. Keep the upstream scan.
      if (location < 0 || !seen.add(Arrays.asList(rows.getLong(1), rows.getLong(2), location))) return null;
    }
    return rows;
  }

  static byte[] transform(byte[] code) {
    final int[] rewritten = {0, 0};
    ClassReader reader = new ClassReader(code);
    ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS);
    reader.accept(new ClassVisitor(Opcodes.ASM9, writer) {
      @Override public MethodVisitor visitMethod(int access, String name, String desc,
          String signature, String[] exceptions) {
        MethodVisitor next = super.visitMethod(access, name, desc, signature, exceptions);
        boolean regionalized = name.equals("fillRegionalized");
        if ((!name.equals("fill") && !regionalized) || !desc.equals("()V")) return next;
        return new MethodVisitor(Opcodes.ASM9, next) {
          @Override public void visitMethodInsn(int opcode, String owner, String method,
              String descriptor, boolean isInterface) {
            if (opcode == Opcodes.INVOKEVIRTUAL && owner.equals(SQL) && method.equals("query")
                && descriptor.equals("(" + ARGS + ")V")) {
              super.visitVarInsn(Opcodes.ALOAD, 0);
              super.visitFieldInsn(Opcodes.GETFIELD, BUILDER, "db", DATABASE);
              super.visitVarInsn(Opcodes.ALOAD, 0);
              super.visitFieldInsn(Opcodes.GETFIELD, BUILDER, "impactIndex", INDEX);
              super.visitMethodInsn(Opcodes.INVOKESTATIC, "ImpactFactorQuery", "query",
                  "(L" + SQL + ";" + ARGS + DATABASE + INDEX + ")V", false);
              rewritten[regionalized ? 1 : 0]++;
            } else {
              super.visitMethodInsn(opcode, owner, method, descriptor, isInterface);
            }
          }
        };
      }
    }, 0);
    if (rewritten[0] != 1 || rewritten[1] != 1) throw new IllegalStateException("unexpected impact factor reader");
    return writer.toByteArray();
  }
}
