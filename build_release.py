#!/usr/bin/env python3
"""Build a portable source release and an architecture-independent Debian package.
Only Python's standard library is required, even when building on macOS.
"""
import gzip
import hashlib
import io
from pathlib import Path
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = '1.0.0'
EPOCH = 1791244800


def tar(entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        directories = set()
        for name, _, _ in entries:
            directories.update(str(parent) for parent in Path(name).parents if str(parent) != '.')
        for directory in sorted(directories):
            info = tarfile.TarInfo('./' + directory + '/')
            info.type, info.mode, info.mtime = tarfile.DIRTYPE, 0o755, EPOCH
            info.uid = info.gid = 0
            info.uname = info.gname = 'root'
            archive.addfile(info)
        for name, data, mode in sorted(entries):
            info = tarfile.TarInfo('./' + name)
            info.size, info.mode, info.mtime = len(data), mode, EPOCH
            info.uid = info.gid = 0
            info.uname = info.gname = 'root'
            archive.addfile(info, io.BytesIO(data))
    return gzip.compress(buffer.getvalue(), mtime=0)


def ar(entries):
    data = bytearray(b'!<arch>\n')
    for name, content in entries:
        header = f'{name+"/":<16}{EPOCH:<12}{0:<6}{0:<6}{"100644":<8}{len(content):<10}`\n'
        assert len(header) == 60
        data.extend(header.encode('ascii'))
        data.extend(content)
        if len(content) % 2:
            data.extend(b'\n')
    return bytes(data)


def build():
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    entries = []
    for source in sorted((ROOT / 'monitorbar').glob('*.py')):
        entries.append(('usr/share/monitorbar/monitorbar/' + source.name, source.read_bytes(), 0o644))
    launcher = b'#!/bin/sh\nset -eu\ncd /usr/share/monitorbar\nexec /usr/bin/python3 -m monitorbar "$@"\n'
    entries.append(('usr/bin/monitorbar', launcher, 0o755))
    entries.append(('usr/share/applications/monitorbar.desktop', (ROOT/'packaging/monitorbar.desktop').read_bytes(), 0o644))
    entries.append(('usr/share/icons/hicolor/scalable/apps/monitorbar.svg', (ROOT/'packaging/monitorbar.svg').read_bytes(), 0o644))
    for name in ('README.md', 'NOTICE.md', 'VALIDATION.md'):
        entries.append(('usr/share/doc/monitorbar/' + name, (ROOT/name).read_bytes(), 0o644))
    control = f'''Package: monitorbar
Version: {VERSION}
Section: utils
Priority: optional
Architecture: all
Maintainer: MonitorBar <monitorbar@localhost>
Depends: python3 (>= 3.10), python3-pyqt5
Recommends: xwayland
Suggests: intel-gpu-tools
Installed-Size: {sum(len(e[1]) for e in entries)//1024+32}
Description: Customizable floating CPU, RAM and GPU monitor
 Ubuntu port of MonitorBar with themes, graphs and persistent preferences.
'''.encode()
    checksums = ''.join(hashlib.md5(data).hexdigest()+'  '+name+'\n' for name, data, _ in sorted(entries)).encode()
    deb = dist / f'monitorbar_{VERSION}_all.deb'
    deb.write_bytes(ar([('debian-binary', b'2.0\n'),
                        ('control.tar.gz', tar([('control', control, 0o644), ('md5sums', checksums, 0o644)])),
                        ('data.tar.gz', tar(entries))]))
    bundle = dist / f'MonitorBar-Ubuntu-{VERSION}.zip'
    with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
        files = [p for p in ROOT.rglob('*') if p.is_file() and not any(
            part in ('dist', '__pycache__', '.git') for part in p.relative_to(ROOT).parts)]
        files.append(deb)
        for path in sorted(files):
            relative = path.relative_to(ROOT)
            info = zipfile.ZipInfo('MonitorBar-Ubuntu/' + str(relative), (2026, 10, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if path.suffix == '.sh' or path.name == 'monitorbar-run' else 0o100644) << 16
            archive.writestr(info, path.read_bytes())
    (dist / 'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in (deb, bundle)))
    print(deb)
    print(bundle)


if __name__ == '__main__':
    build()
