#!/system/bin/sh
# fix MTK WiFi NVRAM warning + random MAC: copy known-good NVRAM blobs
if [ ! -f /data/.nvram_wifi_fixed ]; then
  if [ -f /system/etc/nvram_fix/WIFI ]; then
    cp -f /system/etc/nvram_fix/WIFI /data/nvram/APCFG/APRDEB/WIFI
    cp -f /system/etc/nvram_fix/WIFI_CUSTOM /data/nvram/APCFG/APRDEB/WIFI_CUSTOM
    chown root:system /data/nvram/APCFG/APRDEB/WIFI /data/nvram/APCFG/APRDEB/WIFI_CUSTOM
    chmod 660 /data/nvram/APCFG/APRDEB/WIFI /data/nvram/APCFG/APRDEB/WIFI_CUSTOM
    touch /data/.nvram_wifi_fixed
  fi
fi
