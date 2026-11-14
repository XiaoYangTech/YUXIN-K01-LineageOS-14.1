#!/usr/bin/env python3
"""mkromzip: build a TWRP-flashable, file-based ROM zip from a system tree + manifest.

The manifest comes from tools/ext4manifest.py on the donor raw ext4 image and carries exact
mode/uid/gid/selinux context for every original path. New files (mods) get inferred metadata
(inherit selinux context from parent dir / sibling).

Zip layout:
  META-INF/com/google/android/update-binary   (AOSP 7.1 updater ELF, from donor OTA)
  META-INF/com/google/android/updater-script  (generated edify)
  system/...                                  (regular files only; symlinks are created by script)
  boot.img

The updater-script does: mount system -> delete_recursive -> package_extract_dir ->
set_metadata (mode/uid/gid/selabel) -> symlink() -> package_extract_file(boot.img) -> unmount.

Usage:
  python mkromzip.py --system <dir> --manifest <manifest.json> --boot <boot.img>
                     --updater <update-binary> --out <out.zip> [--dev <by-name-base>]
                     [--script-only] [--verbose]
"""
import argparse, json, os, stat, sys, zipfile, time

SYS_DEV = '/dev/block/platform/mtk-msdc.0/11230000.msdc0/by-name/'
DEFAULT_SELINUX = 'u:object_r:system_file:s0'
# gid/mode defaults for new files by directory (Android 7 fs_config rules, common cases)
EXEC_DIRS = ('/bin', '/xbin', '/sbin')


def load_manifest(path):
    with open(path, 'r', encoding='utf-8') as f:
        recs = json.load(f)
    m = {}
    for r in recs:
        m[r['path']] = r
    return m


def norm(treepath):
    p = treepath.replace(os.sep, '/')
    if not p.startswith('/'):
        p = '/' + p
    return p


def build_entries(system_dir, manifest):
    """Return dict path -> dict(kind, mode, uid, gid, selinux, target)."""
    entries = {}
    for root, dirs, files in os.walk(system_dir):
        rel = os.path.relpath(root, system_dir)
        rel = '' if rel == '.' else rel
        for d in dirs:
            full = os.path.join(root, d)
            path = norm(os.path.join(rel, d)) if rel else norm(d)
            if path == '/lost+found':
                continue
            if os.path.islink(full):
                rec = manifest.get(path, {})
                entries[path] = dict(kind='symlink', target=os.readlink(full),
                                     selinux=rec.get('selinux', DEFAULT_SELINUX), mode=0o777,
                                     uid=0, gid=0)
            else:
                rec = manifest.get(path, {})
                entries[path] = dict(kind='dir', mode=rec.get('mode', 0o755),
                                     uid=rec.get('uid', 0), gid=rec.get('gid', 0),
                                     selinux=rec.get('selinux', DEFAULT_SELINUX))
        for f in files:
            full = os.path.join(root, f)
            path = norm(os.path.join(rel, f)) if rel else norm(f)
            if path == '/lost+found':
                continue
            if os.path.islink(full):
                rec = manifest.get(path, {})
                entries[path] = dict(kind='symlink', target=os.readlink(full),
                                     selinux=rec.get('selinux', DEFAULT_SELINUX), mode=0o777,
                                     uid=0, gid=0)
            else:
                rec = manifest.get(path)
                if rec and rec.get('type') == 'file':
                    e = dict(kind='file', mode=rec.get('mode', 0o644),
                             uid=rec.get('uid', 0), gid=rec.get('gid', 0),
                             selinux=rec.get('selinux', DEFAULT_SELINUX))
                    if 'security.capability' in (rec.get('xattrs') or {}):
                        e['cap_workaround'] = True
                    entries[path] = e
                else:
                    entries[path] = infer_file(path, manifest)
    return entries


def infer_file(path, manifest):
    parent = path.rsplit('/', 1)[0] or '/'
    # inherit context from a sibling in the same dir, else from parent dir record
    sel = None
    for p, r in manifest.items():
        if p.rsplit('/', 1)[0] == parent:
            sel = r.get('selinux')
            break
    if not sel:
        sel = manifest.get(parent, {}).get('selinux', DEFAULT_SELINUX)
    mode = 0o644
    uid, gid = 0, 0
    for d in EXEC_DIRS:
        if path.startswith(d + '/'):
            mode = 0o755
            gid = 2000
            break
    if path.startswith('/etc/init.d/') or path.endswith('/.sh') and path.startswith('/etc/'):
        mode = 0o755
    if path.endswith('/build.prop'):
        mode = 0o644
    return dict(kind='file', mode=mode, uid=uid, gid=gid, selinux=sel)


def esc(st):
    b = chr(92)
    return st.replace(b, b + b).replace('"', b + '"')


def edify_meta(path, rec):
    target = esc('/system' + path)
    if rec['kind'] == 'symlink':
        return 'set_metadata("%s", "selabel", "%s");' % (target, rec['selinux'])
    if rec.get('cap_workaround') and rec['kind'] == 'file':
        # file capabilities cannot be set through edify; fall back to setuid root for run-as
        return ('set_metadata("%s", "uid", %d, "gid", %d, "mode", 0%o, "selabel", "%s");'
                % (target, rec['uid'], rec['gid'], rec['mode'] | 0o4000, rec['selinux']))
    return ('set_metadata("%s", "uid", %d, "gid", %d, "mode", 0%o, "selabel", "%s");'
            % (target, rec['uid'], rec['gid'], rec['mode'], rec['selinux']))


def gen_script(entries, dev, chunk_sizes=None):
    files = sorted(p for p, r in entries.items() if r['kind'] == 'file')
    dirs = sorted(p for p, r in entries.items() if r['kind'] == 'dir')
    links = sorted(p for p, r in entries.items() if r['kind'] == 'symlink')
    # split extraction into top-level chunks so TWRP progress bar visibly moves
    chunks = []
    if chunk_sizes:
        chunks = sorted(chunk_sizes.items(), key=lambda kv: -kv[1][0])
    L = []
    L.append('ui_print("==========================================");')
    L.append('ui_print("  YUXIN K01  LineageOS 14.1 (Android 7.1.2)");')
    L.append('ui_print("  移植卡刷包 - 请使用 TWRP 3.4 刷入");')
    L.append('ui_print("==========================================");')
    L.append('show_progress(0.02, 0);')
    L.append('ifelse(is_mounted("/system"), unmount("/system"));')
    L.append('ui_print("挂载 /system ...");')
    L.append('mount("ext4", "EMMC", "%ssystem", "/system");' % dev)
    L.append('ifelse(is_mounted("/system"), '
             'ui_print("OK"), abort("无法挂载 /system，请先在 TWRP 中检查分区"));')
    L.append('ui_print("清空旧系统 ...");')
    L.append('delete_recursive("/system");')
    L.append('show_progress(0.08, 2);')
    L.append('ui_print("写入系统文件 (%d 个) ...");' % len(files))
    if chunks:
        total = float(sum(sz for _, (sz, _kind) in chunks)) or 1.0
        cum = 0.0
        lo, hi = 0.10, 0.68
        for name, (sz, kind) in chunks:
            cum += sz
            frac = lo + (hi - lo) * (cum / total)
            secs = max(1, min(90, int(sz / 3.0e6)))
            L.append('ui_print("  -> %s");' % esc(name))
            if kind == 'file':
                L.append('package_extract_file("system%s", "/system%s");' % (esc(name), esc(name)))
            else:
                L.append('package_extract_dir("system%s", "/system%s");' % (esc(name), esc(name)))
            L.append('show_progress(%.3f, %d);' % (frac, secs))
    else:
        L.append('package_extract_dir("system", "/system");')
    L.append('show_progress(0.70, 10);')
    L.append('ui_print("设置目录/文件权限与 SELinux 上下文 ...");')
    for p in dirs:
        L.append(edify_meta(p, entries[p]))
    for p in links:
        L.append('symlink("%s", "/system%s");' % (esc(entries[p]['target']), esc(p)))
    for p in links:
        L.append(edify_meta(p, entries[p]))
    for p in files:
        L.append(edify_meta(p, entries[p]))
    L.append('show_progress(0.90, 4);')
    L.append('ui_print("写入 boot.img ...");')
    L.append('package_extract_file("boot.img", "%sboot");' % dev)
    L.append('unmount("/system");')
    L.append('show_progress(1.0, 0);')
    L.append('ui_print("刷入完成！");')
    L.append('ui_print("如需 root，请再刷入 Magisk 卡刷包。");')
    return '\n'.join(L) + '\n', files, dirs, links


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--system', required=True)
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--boot', required=True)
    ap.add_argument('--updater', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--dev', default=SYS_DEV)
    ap.add_argument('--script-only', action='store_true')
    ap.add_argument('--script-out', default=None)
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args()

    manifest = load_manifest(a.manifest)
    print('manifest entries:', len(manifest))
    entries = build_entries(a.system, manifest)
    counts = {}
    for r in entries.values():
        counts[r['kind']] = counts.get(r['kind'], 0) + 1
    print('tree entries:', counts)
    # chunk by top-level component for visible progress during extraction
    chunk_sizes = {}
    for p, r in entries.items():
        parts = p.strip('/').split('/')
        top = '/' + parts[0]
        kind = 'file' if (r['kind'] == 'file' and len(parts) == 1) else 'dir'
        sz = 0
        if r['kind'] == 'file':
            try:
                sz = os.path.getsize(os.path.join(a.system, p.lstrip('/')))
            except OSError:
                sz = 0
        cur = chunk_sizes.get(top)
        if cur is None:
            chunk_sizes[top] = [sz, kind]
        else:
            cur[0] += sz
    script, files, dirs, links = gen_script(entries, a.dev, chunk_sizes)
    print('updater-script lines=%d bytes=%d' % (script.count('\n'), len(script)))
    if a.script_out:
        open(a.script_out, 'w', encoding='utf-8', newline='').write(script)
        print('script written to', a.script_out)
    if a.script_only:
        return
    tmp_script = a.out + '.updater-script'
    open(tmp_script, 'w', encoding='utf-8', newline='').write(script)
    t0 = time.time()
    n = 0
    with zipfile.ZipFile(a.out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        z.write(a.updater, 'META-INF/com/google/android/update-binary')
        z.write(tmp_script, 'META-INF/com/google/android/updater-script')
        z.write(a.boot, 'boot.img')
        for p in sorted(dirs):
            zi = zipfile.ZipInfo('system' + p + '/')
            zi.external_attr = (0o40755 << 16) | 0x10
            zi.compress_type = zipfile.ZIP_STORED
            z.writestr(zi, b'')
        for p in sorted(files):
            src = os.path.join(a.system, p.lstrip('/'))
            z.write(src, 'system' + p)
            n += 1
            if a.verbose and n % 300 == 0:
                print('  zipped %d files ...' % n)
    os.remove(tmp_script)
    print('zip written: %s (%.1f MB) files=%d elapsed=%.0fs'
          % (a.out, os.path.getsize(a.out) / 1048576.0, n + 3, time.time() - t0))


if __name__ == '__main__':
    main()
