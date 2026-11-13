"""Temporary, loopback-only openLCA 2.7.0 server using an APFS database clone.

This narrowly supports the verified macOS distribution. The original database
is never handed to the server. Unsupported installations fail before launch.
"""
from contextlib import contextmanager
import ctypes
import hashlib
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

GUARD_HASH = 'd0ee680936b9e5f13e69816da09af9389cad2a36dd260b4d33b6e88c08ac2595'
IPC_HASH = 'ddc9ebb829cbc2c70895c24ffd73cc2f0bea0273371071986fe0069abb4c3207'
ASM_HASH = '6f3828a215c920059a5efa2fb55c233d6c54ec5cadca99ce1b1bdd10077c7ddd'


class LaunchError(ValueError):
    pass


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else _digest_stream(stream)


def _digest_stream(stream):
    value = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        value.update(chunk)
    return value.hexdigest()


def validate_inputs(app, workspace, database):
    if sys.platform != 'darwin':
        raise LaunchError('automatic local startup currently supports verified macOS openLCA 2.7.0 only')
    if not database or database in ('.', '..') or Path(database).name != database or '/' in database or '\\' in database:
        raise LaunchError('database must be an existing database name, not a path')
    app, workspace = Path(app).resolve(), Path(workspace).resolve()
    java = app / 'Contents/Eclipse/jre/Contents/Home/bin/java'
    libs = app / 'Contents/Eclipse/plugins/olca-app_2.7.0/libs'
    guard = Path(__file__).resolve().parent / 'openlca_guard/localhost-agent.jar'
    for path, expected in ((guard, GUARD_HASH), (libs / 'olca-ipc-2.7.0.jar', IPC_HASH), (libs / 'asm-9.9.1.jar', ASM_HASH)):
        if not path.is_file() or digest(path) != expected:
            raise LaunchError('unsupported or modified openLCA/guard files; refusing automatic startup')
    if not java.is_file():
        raise LaunchError('openLCA Java runtime not found')
    signature = subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)],
                               capture_output=True, text=True)
    if signature.returncode:
        raise LaunchError('openLCA application signature verification failed')
    identity = subprocess.run(['/usr/bin/codesign', '-dv', '--verbose=2', str(app)],
                              capture_output=True, text=True)
    if identity.returncode or 'TeamIdentifier=4C67Z85L4A' not in identity.stderr or 'Identifier=org.openlca.app' not in identity.stderr:
        raise LaunchError('openLCA application is not signed by the expected publisher')
    db = workspace / 'databases' / database
    if db.is_symlink() or not db.is_dir() or not (db / 'log').is_dir() or not (db / 'seg0').is_dir() or not (db / 'service.properties').is_file():
        raise LaunchError('existing Derby database not found; refusing to create, overwrite or delete one')
    if any((db / name).exists() for name in ('db.lck', 'dbex.lck')):
        raise LaunchError('database may be open; close it before creating a temporary clone')
    return app, workspace, db, java, libs, guard


def clone_file(source, destination):
    libc = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
    clone = libc.clonefile
    clone.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
    clone.restype = ctypes.c_int
    if clone(os.fsencode(source), os.fsencode(destination), 0) != 0:
        error = ctypes.get_errno()
        raise OSError(error, 'APFS clonefile failed; no full-copy fallback', str(source))
    return destination


def clone_tree(source, destination):
    for root, directories, files in os.walk(source, followlinks=False):
        if any((Path(root) / name).is_symlink() for name in directories + files):
            raise LaunchError('symbolic links in the data tree are not supported')
    shutil.copytree(source, destination, copy_function=clone_file)


def own_loopback_listener(pid, port):
    result = subprocess.run(['/usr/sbin/lsof', '-nP', '-a', '-p', str(pid),
                             '-iTCP:' + str(port), '-sTCP:LISTEN'], capture_output=True, text=True)
    lines = [line for line in result.stdout.splitlines() if '(LISTEN)' in line]
    return bool(lines) and all(('127.0.0.1:' + str(port) + ' (LISTEN)') in line for line in lines)


@contextmanager
def launch(app, workspace, database):
    app, workspace, db, java, libs, guard = validate_inputs(app, workspace, database)
    with tempfile.TemporaryDirectory(prefix='piezolca-openlca-local-') as temp:
        root = Path(temp)
        data = root / 'data'
        (data / 'databases').mkdir(parents=True)
        clone_tree(db, data / 'databases' / database)
        if any((db / name).exists() for name in ('db.lck', 'dbex.lck')):
            raise LaunchError('database became active during cloning; temporary copy discarded')
        libraries = workspace / 'libraries'
        if libraries.is_symlink():
            raise LaunchError('symbolic library directory is not supported')
        if libraries.is_dir():
            clone_tree(libraries, data / 'libraries')
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        command = [str(java), '-Xmx3584M', '-javaagent:' + str(guard), '-cp', str(libs / '*'),
                   'org.openlca.ipc.Server', '-data', str(data), '-db', database, '-port', str(port), '--readonly']
        log_path = root / 'server.log'
        with log_path.open('w+b') as logfile:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=logfile,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise LaunchError('guarded openLCA server exited during startup')
                    logfile.flush()
                    with log_path.open('rb') as reader:
                        log = reader.read()
                    guarded = b'LOCAL_ONLY_AGENT_APPLIED' in log and b'LOCAL_READONLY_METHODS_APPLIED' in log
                    if guarded and own_loopback_listener(process.pid, port):
                        break
                    time.sleep(0.2)
                else:
                    raise LaunchError('guarded loopback listener could not be verified before timeout')
                yield port
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                if process.stdin is not None:
                    process.stdin.close()
