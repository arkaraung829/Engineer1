# Health Check Report — 192.168.0.10 (R1)

## Summary
Device is operationally healthy right now (low CPU, ample memory, management interface up), but it has a **critical latent fault: the configuration register is set to `0x0`**. On the next reload the router will boot into ROMMON instead of IOS and drop off the network until manually recovered at the console. This must be corrected before any future reboot.

## Root Cause
`show version` reports `Configuration register is 0x0`. A value of `0x0` forces the device to the ROMMON monitor on boot instead of loading the IOS image. The running config contains no `config-register` override and no `boot system` statements, so nothing corrects this at boot. The correct value for this platform is `0x2102`. Recent reload history (`System returned to ROM by reload`, `Last reload reason: Unknown reason`, uptime 24 min) is consistent with this misconfiguration.

## Evidence
- **show version:** `Configuration register is 0x0`; uptime 24 minutes; `System returned to ROM by reload`; IOSv 15.8(3)M2.
- **show running-config | include boot|config-register:** only `boot-start-marker` / `boot-end-marker` present — no `config-register` line, no `boot system` line.
- **show processes cpu:** 2%/1%/4% — no runaway processes.
- **show memory statistics:** Processor ~789 MB free / 854 MB; I/O ~10.7 MB free / 64 MB — healthy.
- **show ip interface brief:** Gi0/0 (192.168.0.10) up/up; Gi0/1–Gi0/3 administratively down (manually shut at 06:59, appears intentional — confirm).
- **show logging:** SSH KEX mismatch (`%SSH-3-NO_MATCH`) rejecting modern clients; benign IOSv boot messages (`%C3600-3-NOMAC`, `%PA-3-PA_INIT_FAILED`, `%CVAC-4-FILE_IGNORED`).

## Fix Commands
```
enable
configure terminal
 config-register 0x2102
end
show version | include register
write memory
```
Expected result: `Configuration register is 0x2102` (may display "will be 0x2102 at next reload"). No reload required to set the value — ensure it is corrected before any future reboot.

Optional — resolve SSH key-exchange rejections:
```
configure terminal
 ip ssh version 2
 ip ssh dh min size 2048
end
```

## Follow-up
- Confirm Gi0/1–Gi0/3 being administratively down is intentional.
- Investigate why the router previously reloaded (Last reload reason: Unknown) if unexpected.
