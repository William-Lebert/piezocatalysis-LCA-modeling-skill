import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import gnu.trove.map.hash.TLongObjectHashMap;
import org.objectweb.asm.*;
import org.openlca.core.database.RefEntityDao;
import org.openlca.core.model.descriptors.RootDescriptor;

public final class DescriptorLookup {
  static final String JSON_REFS = "org/openlca/jsonld/output/JsonRefs";
  static final String TECH_INDEX = "org/openlca/core/matrix/index/TechIndex";
  private static final String DB = "org/openlca/core/database/";
  private static final String DAO = DB + "RefEntityDao";
  private static final Set<String> JSON_DAOS = new HashSet<>(Arrays.asList(DAO, DB + "RootEntityDao"));
  private static final Set<String> INDEX_DAOS = new HashSet<>(Arrays.asList(
      DB + "ProductSystemDao", DB + "ProcessDao", DB + "ResultDao", DB + "FlowDao"));
  private static final String MAP = "Lgnu/trove/map/hash/TLongObjectHashMap;";
  private static final int MAX_POINT_LOOKUPS = 32;

  private DescriptorLookup() {}

  public static TLongObjectHashMap<RootDescriptor> lazyMap(RefEntityDao<?, ?> dao) {
    // The pinned JsonRefs and TechIndex call sites use only get(long) on these maps.
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

  static byte[] transform(String className, byte[] code) {
    boolean index = TECH_INDEX.equals(className);
    String target = index ? "fillFrom" : "lambda$descriptorOf$0";
    Set<String> owners = index ? INDEX_DAOS : JSON_DAOS;
    int expected = index ? owners.size() : 1;
    final int[] rewritten = {0};
    ClassReader reader = new ClassReader(code);
    ClassWriter writer = new ClassWriter(reader, 0);
    reader.accept(new ClassVisitor(Opcodes.ASM9, writer) {
      @Override public MethodVisitor visitMethod(int access, String name, String desc,
          String signature, String[] exceptions) {
        MethodVisitor next = super.visitMethod(access, name, desc, signature, exceptions);
        if (!name.equals(target)) return next;
        return new MethodVisitor(Opcodes.ASM9, next) {
          @Override public void visitMethodInsn(int opcode, String owner, String method,
              String descriptor, boolean isInterface) {
            if (opcode == Opcodes.INVOKEVIRTUAL && owners.contains(owner)
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
    if (rewritten[0] != expected) throw new IllegalStateException("unexpected descriptor resolver in " + className);
    return writer.toByteArray();
  }
}
