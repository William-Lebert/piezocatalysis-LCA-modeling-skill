import gnu.trove.map.hash.TLongObjectHashMap;
import org.objectweb.asm.*;
import org.openlca.core.database.RefEntityDao;
import org.openlca.core.model.descriptors.RootDescriptor;

public final class DescriptorLookup {
  static final String JSON_REFS = "org/openlca/jsonld/output/JsonRefs";
  private static final String DAO = "org/openlca/core/database/RefEntityDao";
  private static final String ROOT_DAO = "org/openlca/core/database/RootEntityDao";
  private static final String MAP = "Lgnu/trove/map/hash/TLongObjectHashMap;";
  private static final int MAX_POINT_LOOKUPS = 32;

  private DescriptorLookup() {}

  public static TLongObjectHashMap<RootDescriptor> lazyMap(RefEntityDao<?, ?> dao) {
    // The pinned JsonRefs writer only uses get(long) on this map.
    return new TLongObjectHashMap<RootDescriptor>() {
      private TLongObjectHashMap<?> all;

      @Override public RootDescriptor get(long id) {
        if (all != null) return (RootDescriptor) all.get(id);
        if (containsKey(id)) return super.get(id);
        if (size() >= MAX_POINT_LOOKUPS) {
          all = dao.descriptorMap();
          clear();
          return (RootDescriptor) all.get(id);
        }
        RootDescriptor descriptor = (RootDescriptor) dao.getDescriptor(id);
        put(id, descriptor);
        return descriptor;
      }
    };
  }

  static byte[] transform(byte[] code) {
    // Retain the upstream exporter's own per-type map and JSON formatting.
    final int[] rewritten = {0};
    ClassReader reader = new ClassReader(code);
    ClassWriter writer = new ClassWriter(reader, 0);
    reader.accept(new ClassVisitor(Opcodes.ASM9, writer) {
      @Override public MethodVisitor visitMethod(int access, String name, String desc,
          String signature, String[] exceptions) {
        MethodVisitor next = super.visitMethod(access, name, desc, signature, exceptions);
        if (!name.equals("lambda$descriptorOf$0")) return next;
        return new MethodVisitor(Opcodes.ASM9, next) {
          @Override public void visitMethodInsn(int opcode, String owner, String method,
              String descriptor, boolean isInterface) {
            if (opcode == Opcodes.INVOKEVIRTUAL && (owner.equals(DAO) || owner.equals(ROOT_DAO))
                && method.equals("descriptorMap") && descriptor.equals("()" + MAP)) {
              super.visitMethodInsn(Opcodes.INVOKESTATIC, "DescriptorLookup", "lazyMap",
                  "(L" + DAO + ";)" + MAP, false);
              rewritten[0]++;
            } else {
              super.visitMethodInsn(opcode, owner, method, descriptor, isInterface);
            }
          }
        };
      }
    }, 0);
    if (rewritten[0] != 1) throw new IllegalStateException("unexpected descriptor resolver");
    return writer.toByteArray();
  }
}
