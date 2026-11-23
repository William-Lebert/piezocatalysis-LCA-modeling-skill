"""Rebuild the small local guard with a separately obtained, pinned compiler."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

COMPILER_SHA256 = '29f6d3918ee02db4400c103bc25dd90a22491c3a395867d9393070cb96a7dd29'
CORE_SHA256 = '2504f24f5d3274b1e04ea714231699de9408a038491fc89aed12973c123e869e'
TROVE_SHA256 = '3c8616203d61a12a7e3487e8b34f3c198c2b5ba9e90da0c7ea32d99cd4958012'
ASM_SHA256 = '6f3828a215c920059a5efa2fb55c233d6c54ec5cadca99ce1b1bdd10077c7ddd'


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, required=True, help='Eclipse ECJ 3.42.0 jar, obtained separately')
    parser.add_argument('--asm', type=Path, required=True, help='ASM jar from verified openLCA 2.7.0')
    parser.add_argument('--core', type=Path, required=True, help='olca-core jar from verified openLCA')
    parser.add_argument('--trove', type=Path, required=True, help='trove4j jar from verified openLCA')
    parser.add_argument('--output', type=Path, required=True, help='new jar path; existing files are not replaced')
    args = parser.parse_args()
    for path, expected in ((args.compiler, COMPILER_SHA256), (args.asm, ASM_SHA256),
                           (args.core, CORE_SHA256), (args.trove, TROVE_SHA256)):
        if checksum(path) != expected:
            raise SystemExit('build dependency checksum mismatch: ' + path.name)
    classpath = os.pathsep.join(str(path) for path in (args.asm, args.core, args.trove))
    sources = [Path(__file__).with_name(name) for name in ('LocalhostAgent.java', 'SnapshotQuery.java', 'DescriptorLookup.java')]
    with tempfile.TemporaryDirectory(prefix='piezolca-guard-build-') as temp:
        subprocess.run([str(args.java), '-jar', str(args.compiler), '-1.8', '-cp', classpath,
                        '-d', temp, *(str(source) for source in sources)], check=True)
        def entry(archive, name, data):
            item = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            item.compress_type = ZIP_DEFLATED
            item.external_attr = 0o644 << 16
            archive.writestr(item, data)
        with ZipFile(args.output, 'x') as archive:
            entry(archive, 'META-INF/MANIFEST.MF', b'Manifest-Version: 1.0\r\nPremain-Class: LocalhostAgent\r\n\r\n')
            for item in sorted(Path(temp).glob('*.class')):
                entry(archive, item.name, item.read_bytes())
    print('sha256:', checksum(args.output))


if __name__ == '__main__':
    main()
