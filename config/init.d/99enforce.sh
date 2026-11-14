#!/system/bin/sh
# SELinux enforcing: only from the boot AFTER the relabel has been done
i=0
while [ "$(getprop sys.boot_completed)" != "1" ] && [ $i -lt 180 ]; do sleep 2; i=$((i+1)); done
if [ -f /data/.v32_relabeled ]; then
  setenforce 1 2>/dev/null
fi
