import org.objectweb.asm.*;
import org.openlca.core.database.IDatabase;
import org.openlca.jsonld.output.JsonRefs;

public final class ResultReferences {
  static final String SERVICE = "org/openlca/core/services/JsonResultService";
  private static final String REFS = "org/openlca/jsonld/output/JsonRefs";
  private static final String FACTORY = "(Lorg/openlca/core/database/IDatabase;)L" + REFS + ";";
  private static final int REQUESTS_PER_RESOLVER = 32;
  private static final ThreadLocal<Window> recent = new ThreadLocal<>();

  private ResultReferences() {}

  private static final class Window {
    final IDatabase database;
    final JsonRefs refs;
    int uses;

    Window(IDatabase database) {
      this.database = database;
      this.refs = JsonRefs.of(database);
    }
  }

  public static JsonRefs forResult(IDatabase database) {
    // JsonRefs has mutable maps. Each IPC worker has its own bounded reuse window.
    Window window = recent.get();
    if (window == null || window.database != database || window.uses >= REQUESTS_PER_RESOLVER) {
      window = new Window(database);
      recent.set(window);
    }
    window.uses++;
    return window.refs;
  }

  static byte[] transform(byte[] code) {
    final int[] rewritten = {0};
    ClassReader reader = new ClassReader(code);
    ClassWriter writer = new ClassWriter(reader, 0);
    reader.accept(new ClassVisitor(Opcodes.ASM9, writer) {
      @Override public MethodVisitor visitMethod(int access, String name, String desc,
          String signature, String[] exceptions) {
        MethodVisitor next = super.visitMethod(access, name, desc, signature, exceptions);
        if (!name.equals("refs") || !desc.equals("()L" + REFS + ";")) return next;
        return new MethodVisitor(Opcodes.ASM9, next) {
          @Override public void visitMethodInsn(int opcode, String owner, String method,
              String descriptor, boolean isInterface) {
            if (opcode == Opcodes.INVOKESTATIC && owner.equals(REFS)
                && method.equals("of") && descriptor.equals(FACTORY)) {
              super.visitMethodInsn(opcode, "ResultReferences", "forResult", FACTORY, false);
              rewritten[0]++;
            } else {
              super.visitMethodInsn(opcode, owner, method, descriptor, isInterface);
            }
          }
        };
      }
    }, 0);
    if (rewritten[0] != 1) throw new IllegalStateException("unexpected result reference factory");
    return writer.toByteArray();
  }
}
