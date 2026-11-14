#!/system/bin/sh
# clean-flash first boot: relabel /system so SELinux domains are correct
mount -o rw,remount /system 2>/dev/null
for d in bin lib lib64 app priv-app framework etc fonts usr xbin vendor media tts; do
  [ -d /system/$d ] && restorecon -R /system/$d 2>/dev/null
done
touch /data/.v32_relabeled
sync
