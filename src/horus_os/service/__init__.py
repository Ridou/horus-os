"""Cross-platform always-on service support (Phase 66 - REMOTE-04 / TEST-30).

`definitions` holds pure string generators for the per-OS service definition
(systemd --user unit, launchd LaunchAgent plist, NSSM command set). `manager`
holds all OS-mutating subprocess dispatch behind ``sys.platform`` so the
``service install --print`` dry run and the cross-OS tests never touch the OS.
"""
