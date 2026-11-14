#!/usr/bin/env python3
"""Read-only ext4 image helper built on the `ext4` pip package."""
import sys, os, stat

import ext4


def open_vol(path):
    f = open(path, 'rb')
    return ext4.Volume(f), f


def node_from_path(vol, path):
    node = vol.root
    for part in [p for p in path.split('/') if p]:
        found = None
        for ent, ftype in node.opendir():
            if ent.name_bytes.decode('utf-8','replace') == part:
                found = vol.inodes[ent.inode]
                break
        if found is None:
            raise FileNotFoundError(path)
        node = found
    return node


def read_file(node):
    with node.open('rb') as fh:
        return fh.read()


def extract_tree(vol, node, outdir, prefix=''):
    os.makedirs(outdir, exist_ok=True)
    stack = [('', node)]
    while stack:
        rel, cur = stack.pop()
        for ent, ftype in cur.opendir():
            name = ent.name_bytes.decode('utf-8','replace')
            if name in ('.', '..'):
                continue
            child = vol.inodes[ent.inode]
            r = (rel + '/' + name) if rel else name
            dest = os.path.join(outdir, r)
            mode = child.i_mode
            if stat.S_ISDIR(mode):
                os.makedirs(dest, exist_ok=True)
                stack.append((r, child))
            elif stat.S_ISLNK(mode):
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                target = child.readlink().decode('latin1')
                if os.path.lexists(dest):
                    os.unlink(dest)
                os.symlink(target, dest)
            elif stat.S_ISREG(mode):
                os.makedirs(os.path.dirname(dest) or '.', exist_ok=True)
                data = read_file(child)
                with open(dest, 'wb') as f:
                    f.write(data)
                os.chmod(dest, stat.S_IMODE(mode) or 0o644)
            else:
                print('skip special', r, mode)


def list_dir(vol, path):
    node = node_from_path(vol, path)
    rows = []
    for ent, ftype in node.opendir():
        name = ent.name_bytes.decode('utf-8','replace')
        if name in ('.', '..'):
            continue
        child = vol.inodes[ent.inode]
        rows.append((name, child.i_mode, child.i_size))
    return rows


if __name__ == '__main__':
    cmd = sys.argv[1]
    img = sys.argv[2]
    vol, fh = open_vol(img)
    if cmd == 'ls':
        path = sys.argv[3] if len(sys.argv) > 3 else '/'
        for name, mode, size in list_dir(vol, path):
            print(f'{mode:07o} {size:>10} {name}')
    elif cmd == 'cat':
        sys.stdout.write(read_file(node_from_path(vol, sys.argv[3])).decode('utf-8', 'replace'))
    elif cmd == 'extract':
        path, outdir = sys.argv[3], sys.argv[4]
        node = vol.root if path in ('/', '') else node_from_path(vol, path)
        extract_tree(vol, node, outdir)
        print('extracted', path, '->', outdir)
    elif cmd == 'extractfile':
        src, dest = sys.argv[3], sys.argv[4]
        data = read_file(node_from_path(vol, src))
        os.makedirs(os.path.dirname(dest) or '.', exist_ok=True)
        open(dest, 'wb').write(data)
        print('wrote', dest, len(data))
