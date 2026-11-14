#!/usr/bin/env python3
"""Dump a complete Manifest (path/type/mode/uid/gid/size/symlink target/selinux context/xattrs)
from a raw ext4 image. Used to generate an exact-permission TWRP flash script.
Usage: python ext4manifest.py <system.img> <out.json>
"""
import sys, os, stat, json
import ext4

XATTR_PREFIX = {'security.selinux': 'selinux'}


def walk(vol):
    out = []
    stack = [('', vol.root)]
    while stack:
        rel, cur = stack.pop()
        for ent, ftype in cur.opendir():
            name = ent.name_bytes.decode('utf-8', 'replace')
            if name in ('.', '..'):
                continue
            ino = vol.inodes[ent.inode]
            path = ('/' + rel + '/' + name) if rel else ('/' + name)
            mode = int(ino.i_mode)
            rec = dict(path=path, mode=mode & 0o7777, uid=int(ino.i_uid), gid=int(ino.i_gid),
                       size=int(ino.i_size))
            fmt = stat.S_IFMT(mode)
            if fmt == stat.S_IFDIR:
                rec['type'] = 'dir'
                stack.append((rel + '/' + name if rel else name, ino))
            elif fmt == stat.S_IFLNK:
                rec['type'] = 'symlink'
                try:
                    rec['target'] = ino.readlink().decode('utf-8', 'replace')
                except Exception as e:
                    rec['target'] = ''
            elif fmt == stat.S_IFREG:
                rec['type'] = 'file'
            elif fmt == stat.S_IFCHR:
                rec['type'] = 'char'
            elif fmt == stat.S_IFBLK:
                rec['type'] = 'block'
            elif fmt == stat.S_IFIFO:
                rec['type'] = 'fifo'
            elif fmt == stat.S_IFSOCK:
                rec['type'] = 'socket'
            else:
                rec['type'] = 'unknown'
            try:
                for xname, xvalue in ino.xattrs:
                    if xname == 'security.selinux':
                        rec['selinux'] = xvalue.rstrip(b'\0').decode('utf-8', 'replace')
                    else:
                        rec.setdefault('xattrs', {})[xname] = xvalue.hex()
            except Exception:
                pass
            out.append(rec)
    out.sort(key=lambda r: r['path'])
    return out


def main():
    img, outjson = sys.argv[1], sys.argv[2]
    with open(img, 'rb') as f:
        vol = ext4.Volume(f)
        print(f'superblock: block_size={vol.block_size} blocks={vol.superblock.s_blocks_count_lo}')
        recs = walk(vol)
    with open(outjson, 'w', encoding='utf-8') as f:
        json.dump(recs, f, ensure_ascii=False, indent=0)
    from collections import Counter
    print(f'entries={len(recs)}', Counter(r['type'] for r in recs))
    sel = sum(1 for r in recs if 'selinux' in r)
    print(f'with selinux xattr: {sel}/{len(recs)}')
    for r in recs[:5]:
        print(r)


if __name__ == '__main__':
    main()
