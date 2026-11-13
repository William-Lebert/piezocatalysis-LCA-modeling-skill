import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;
import java.lang.reflect.Field;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import org.objectweb.asm.*;

public final class LocalhostAgent {
  private static final Set<String> ALLOWED = new HashSet<>(Arrays.asList(
      "data/get/descriptors", "result/calculate", "result/state", "result/total-impacts",
      "result/impact-contributions-of", "result/dispose"));

  public static void restrictMethods(Object server) {
    try {
      Field field = server.getClass().getDeclaredField("handlers");
      field.setAccessible(true);
      Map<?, ?> methods = (Map<?, ?>) field.get(server);
      if (!methods.keySet().containsAll(ALLOWED)) throw new IllegalStateException("required methods missing");
      methods.keySet().removeIf(key -> !ALLOWED.contains(key));
      if (!methods.keySet().equals(ALLOWED)) throw new IllegalStateException("method restriction failed");
      System.err.println("LOCAL_READONLY_METHODS_APPLIED");
    } catch (Throwable failure) {
      System.err.println("LOCAL_READONLY_METHODS_FAILED: " + failure);
      Runtime.getRuntime().halt(78);
    }
  }

  public static void premain(String args, Instrumentation instrumentation) {
    Thread parentWatch = new Thread(() -> {
      try {
        while (System.in.read() != -1) { /* Keep the parent pipe open. */ }
      } catch (Throwable ignored) { }
      Runtime.getRuntime().halt(77);
    }, "piezolca-parent-watch");
    parentWatch.setDaemon(true);
    parentWatch.start();
    instrumentation.addTransformer(new ClassFileTransformer() {
      @Override public byte[] transform(ClassLoader loader, String className, Class<?> old,
          ProtectionDomain domain, byte[] code) {
        if (!"org/openlca/ipc/Server".equals(className)) return null;
        try {
          final int[] changed = {0, 0};
          ClassReader reader = new ClassReader(code);
          ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS);
          reader.accept(new ClassVisitor(Opcodes.ASM9, writer) {
            @Override public MethodVisitor visitMethod(int access, String name, String desc,
                String signature, String[] exceptions) {
              MethodVisitor next = super.visitMethod(access, name, desc, signature, exceptions);
              return new MethodVisitor(Opcodes.ASM9, next) {
                @Override public void visitMethodInsn(int opcode, String owner, String method,
                    String descriptor, boolean isInterface) {
                  if (name.equals("<init>") && opcode == Opcodes.INVOKESPECIAL
                      && owner.equals("java/net/InetSocketAddress") && method.equals("<init>")
                      && descriptor.equals("(I)V")) {
                    super.visitLdcInsn("127.0.0.1");
                    super.visitInsn(Opcodes.SWAP);
                    super.visitMethodInsn(opcode, owner, method, "(Ljava/lang/String;I)V", false);
                    changed[0]++;
                  } else super.visitMethodInsn(opcode, owner, method, descriptor, isInterface);
                }
                @Override public void visitInsn(int opcode) {
                  if (name.equals("withDefaultHandlers") && desc.equals("()Lorg/openlca/ipc/Server;")
                      && opcode == Opcodes.ARETURN) {
                    super.visitInsn(Opcodes.DUP);
                    super.visitMethodInsn(Opcodes.INVOKESTATIC, "LocalhostAgent", "restrictMethods", "(Ljava/lang/Object;)V", false);
                    changed[1]++;
                  }
                  super.visitInsn(opcode);
                }
              };
            }
          }, 0);
          if (changed[0] != 1 || changed[1] != 1) throw new IllegalStateException("unexpected server implementation");
          System.err.println("LOCAL_ONLY_AGENT_APPLIED");
          return writer.toByteArray();
        } catch (Throwable failure) {
          System.err.println("LOCAL_ONLY_AGENT_FAILED: " + failure);
          Runtime.getRuntime().halt(78);
          return null;
        }
      }
    });
  }
}
