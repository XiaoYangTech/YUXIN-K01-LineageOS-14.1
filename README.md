# YUXIN K01 (s630bw_yuxin_k01) — LineageOS 14.1 移植 ROM

廉价 MTK 翻译机 YUXIN K01 的 **Android 7.1.2 LineageOS 14.1 中文移植 ROM** + TWRP 3.4.0-0。

- 维护者：**B站-小杨聊科技**（XiaoYangTech）
- 底包：UleFone Power `lineage-14.1-20190203-UNOFFICIAL-power`（arm64, 7.1.2）
- 内核：设备原厂 6.0 内核 3.18.19（保持原厂 modem/屏幕/触摸驱动）
- 状态：**可日用（WiFi 版）**，已知问题见下

**镜像仓库**：[CNB](https://cnb.cool/InspireWorks/YUXIN-K01-LineageOS-14.1) ｜ [GitHub](https://github.com/XiaoYangTech/YUXIN-K01-LineageOS-14.1)

---

## 设备信息

| 项目 | 参数 |
|------|------|
| 型号 | YUXIN K01（翻译机） |
| 主板/设备名 | s630bw_yuxin_k01 / lineage_s630bw_yuxin_k01 |
| SoC | MediaTek MT6737M（MT6735 BSP），4×Cortex-A53 |
| GPU | Mali-T720 |
| 内存/存储 | 1GB RAM / 8GB eMMC |
| 屏幕 | **240×320** 2.4 寸 SPI 屏（ST7789v/ST7796s 驱动，45Hz） |
| 触摸 | FocalTech FT6x36（电容触摸 + 实体返回/home 触摸键） |
| 传感器 | BMA250 加速度、MMC3524x 磁力、STK3x1x 光线/距离、ITG1010 陀螺（内核未启用） |
| 无线 | MT6625L（WiFi 2.4G + BT 4.0） |
| 蜂窝 | 单 SIM 卡槽（LTE，Cat4）；**无 VoLTE / 无 CS 回落** |
| 其他 | 无摄像头、无听筒（扬声器为二合一）、无 GPS 硬件、无 FM 耳机口 |

- 原厂系统：Android 6.0 MRA58K（`full_hct6753_65u_m0`）
- 刷机方式：TWRP 卡刷（本仓库 Releases 提供 TWRP 与 ROM）

---

## 本 ROM 已做的修改（v3.3）

**基础**
- 底包换成 UleFone Power LineageOS 14.1（中文完整，含简繁）
- 原厂 6.0 内核（保留原厂 modem/触摸/屏幕驱动）
- 显示 HAL 用 UleFone 7.1 原配（hwcomposer/gralloc/memtrack），修复唤醒黑屏与截图
- 原厂 6.0 音频 HAL + 原厂音频配置；无听筒场景下通话音频改走扬声器
- 集成 **Dolby Atmos**（32 位 audioserver 完整模式）；删除 AudioFX

**系统定制**
- MiSans 中文字体（zh-Hans 首选，Noto CJK 保留缺字回退）
- Square Home 桌面（系统应用 + 默认启动器）
- 删除：电话(Dialer)、通讯录(Contacts)、短信(messaging)、SIM 卡工具包(Stk)、相机/Snap/Gallery2、指纹相关、LineageOS 更新、开机向导、CPL 桌面
- 默认：允许未知来源安装、开发者选项、动画缩放 0、手动亮度 128、时区中国、默认讯飞输入法
- 开机动画：LineageOS 原版
- SELinux：首次开机自动 relabel，第二次开机自动 **Enforcing**
- 刷机脚本：按目录分段写入 + 进度条推进

**网络/基带**
- 换用**原厂 6.0 RIL 栈**（mtkrild/libril*/mtk-ril*），删除底包 `ro.telephony.ril.config=fakeiccid`（否则无法注册网络）
- APN 使用联通 3gnet 配置
- NVRAM WIFI 修复：固定 MAC（`d0:b3:3f:7d:95:b0`）
- 锁屏音效后杂音修复（AudioFlinger standby 由 3000ms 改为 500ms）

**修复的移植 bug**
- 蓝牙崩溃（32 位 JNI 内嵌 + priv-app + 系统权限 + MAP 恢复）
- 无 home 键/通知栏无法展开/亮度不可调（`user_setup_complete` / `device_provisioned` 未置位）
- "Build author" 英文与底包作者信息 → 资源 overlay 改为 **ROM 维护者 / B站-小杨聊科技**
- USB 默认模式改为 **MTP + ADB**

---

## 已知问题

| 问题 | 说明 |
|------|------|
| **无语音通话** | 设备无 VoLTE，联通 CS 域被网络拒绝（日志 `+CREG: 3` cause 18）；原厂也无电话 App，本身按数据设备设计。ROM 已删除电话/通讯录 |
| **移动数据用户面不通** | LTE 可注册（46001）、PDP 可激活并拿到 IP/DNS，但用户面流量不通（浏览器 `ERR_NAME_NOT_RESOLVED`）。RIL 用户态与原厂 6.0 modem 配套问题，待后续解决 |
| 陀螺仪未启用 | ITG1010 硬件存在，但内核无对应驱动（需要编译内核） |
| 无 GPS | DTB 无 GPS 节点、无 `/dev/gps`，硬件未引出 |
| 无摄像头/听筒 | 硬件本身没有 |

---

## 刷机步骤

1. 用 Releases 中的 **TWRP 3.4.0-0**（不带主题版）刷入 recovery：
   `fastboot` 不适用，请用 SP Flash Tool 只刷 recovery 分区，或已有 TWRP 时直接卡刷。
2. TWRP 中 **Format Data**（首次从原厂/其他 ROM 切换必须清数据）。
3. 刷入 `ROM-YUXIN_K01_LineageOS-14.1_v3.3_CN.zip`。
4. 首次开机需要 5–10 分钟（1GB 机器 dexopt）。首次开机 SELinux 为 Permissive 并自动 relabel。
5. **重启一次**，之后自动进入 **Enforcing**。
6. 连接电脑默认 **MTP+ADB**（如未生效，在开发者选项/存储里切换一次 USB 模式）。

---

## 下载（Releases）

- GitHub 发布页：https://github.com/XiaoYangTech/YUXIN-K01-LineageOS-14.1/releases/tag/v3.3
- CNB 发布页：https://cnb.cool/InspireWorks/YUXIN-K01-LineageOS-14.1/-/releases/tag/v3.3

> 注意：CNB 附件存储带宽较小，**ROM 卡刷包请从 GitHub Release 下载**（SHA256 一致）；TWRP 镜像在两个 Release 都有。
- CNB 发布页：https://cnb.cool/InspireWorks/YUXIN-K01-LineageOS-14.1/-/releases/tag/v3.3
- `ROM-YUXIN_K01_LineageOS-14.1_v3.3_CN.zip`（约 436MB）
- `twrp-yuxin-k01-3.4.0-0.img`（16MB，不带主题）

校验值见 `SHA256SUMS`。

---

## 仓库内容

| 路径 | 说明 |
|------|------|
| `tools/` | 移植/打包脚本：`build_v3.py`（底包处理）、`build_v32.py`（v3.3 补丁集成）、`mkromzip.py`（生成卡刷包）、`update-binary-los`、`bootimg.py` 等 |
| `config/` | 本 ROM 的关键配置：`build.prop`、`fonts.xml`、`audio_device.xml`、init.d 脚本、`platform.xml`、`mac_permissions.xml` |
| `docs/CHANGELOG.md` | 版本改动记录 |
| `SHA256SUMS` | 发布文件校验值（ROM / TWRP） |
| Releases | ROM 卡刷包 + TWRP 镜像下载 |

> ROM 内的 LineageOS/AOSP/MTK 组件版权归各自项目所有，本仓库仅提供移植脚本、配置与本人修改部分，仅供学习交流，请勿用于商业用途。

---

## 鸣谢

- LineageOS / CyanogenMod
- UleFone Power LineageOS 14.1 底包作者（Hadenix | 4PDA / XDA）
- 提供各类移植教程与工具的社区网友
