---
title: "Running as a service"
description: "Keep horus-os running 24/7 as an OS service with systemd, launchd, or Windows, and forward provider keys and the data directory into it."
---

## Why run as a service

`horus-os serve` runs in the foreground and stops when you close the terminal. To keep the dashboard, scheduler, and autonomous research running around the clock, register horus-os as a platform-native service. `horus-os service` installs a definition that runs `horus-os serve` continuously and restarts it on failure, using systemd on Linux, launchd on macOS, and NSSM (or Task Scheduler) on Windows.

The workflow is identical on every OS: install, then verify with the doctor.

> [!NOTE]
> The service binds to the loopback default (`127.0.0.1:8765`). To reach the dashboard from another machine, do not change the bind address. Put a network authentication layer in front of it instead. See [Remote access](/guides/remote-access/).

## Install and verify

Preview the generated service definition first. The `--print` flag is a dry run that emits the definition without touching the OS:

```bash
horus-os service install --print
```

When the definition looks right, register and start the service:

```bash
horus-os service install
```

Then confirm it is registered and running:

```bash
horus-os doctor --service
```

`horus-os doctor --service` exits `0` only when the service is both registered and running, and prints a structured report otherwise. It guides you through fixes (for example a missing supervisor binary) rather than crashing.

## Lifecycle commands

The full lifecycle is available once the service is installed:

```bash
horus-os service install      # register and start
horus-os service start        # start a stopped service
horus-os service stop         # stop without unregistering
horus-os service status       # report registration and run state
horus-os service uninstall    # stop and unregister
```

Running `horus-os service` with no subcommand reports status.

## Per-OS notes

### Linux (systemd user unit)

The service installs as a user unit at `~/.config/systemd/user/horus-os.service` with `Restart=on-failure`. No admin is required to install or run it while you are logged in.

By default a systemd user service stops when you log out. To keep it alive after logout (for example on a headless box), enable lingering once:

```bash
sudo loginctl enable-linger "$USER"
```

This is the only admin step on Linux, and it is required only for survive-logout persistence. `horus-os doctor --service` reports your linger status so you know whether the service will outlive your session.

### macOS (launchd LaunchAgent)

The service installs as a LaunchAgent at `~/Library/LaunchAgents/sh.horus-os.plist` with `RunAtLoad` and `KeepAlive`, so it starts at GUI login and is kept running. No admin is required.

> [!IMPORTANT]
> A LaunchAgent runs only while a user is logged into the GUI session. After a reboot it starts once you log in, not before. Pre-login always-on would require a LaunchDaemon (admin), which is out of scope for the no-admin default.

### Windows (NSSM, with a Task Scheduler fallback)

The default Windows mechanism is NSSM, which gives a true service with restart-on-failure. NSSM is not bundled with Windows, so install it first, for example with `choco install nssm`, `winget install NSSM.NSSM`, or from `https://nssm.cc`.

NSSM registers a system service, so `horus-os service install` must run in an administrator shell on Windows. This is a deliberate, documented exception to the no-admin default, because Windows has no clean user-level always-on mechanism with genuine crash-restart.

> [!WARNING]
> If a required supervisor binary is missing (for example `nssm`), `horus-os service install` exits non-zero and prints guidance instead of completing the install.

If you cannot grant admin, the fallback is a Task Scheduler at-logon task:

```text
schtasks /create /sc onlogon /tn horus-os /tr "horus-os serve"
```

This starts the dashboard when you log in, but it does not provide native crash-restart and does not run before logon. Use NSSM when you can; use Task Scheduler only when you cannot grant admin.

## Forwarding environment into the service

A supervised service does not inherit the environment of your interactive shell. If your agents need provider keys, the service process must be given them explicitly. Otherwise scheduled runs and dashboard runs fail with missing-key errors even though the CLI works for you interactively.

### Data directory

The generated definition sets `HORUS_OS_DATA_DIR` so the service uses the same data directory as your CLI. If you keep your data directory elsewhere, set `HORUS_OS_DATA_DIR` in the service environment to match. See [Environment variables](/reference/environment-variables/) for the default locations.

### Provider keys

Forward provider keys (for example `ANTHROPIC_API_KEY` or `GEMINI_API_KEY`) into the service environment using the platform mechanism.

systemd: add `Environment=` lines to the unit, or an `EnvironmentFile=` pointing at an env file:

```ini
[Service]
EnvironmentFile=%h/.config/horus-os/.env
```

launchd: add an `EnvironmentVariables` dict to the plist:

```xml
<key>EnvironmentVariables</key>
<dict>
  <key>ANTHROPIC_API_KEY</key>
  <string>your-api-key</string>
</dict>
```

NSSM: set the extra environment on the registered service:

```text
nssm set horus-os AppEnvironmentExtra "ANTHROPIC_API_KEY=your-api-key"
```

> [!CAUTION]
> Never commit real keys into a unit file, plist, or env file. Use placeholders like `your-api-key` in examples and keep real values in untracked files outside version control.

## Verifying agents run under the service

After forwarding keys, restart the service and re-run the doctor:

```bash
horus-os service stop
horus-os service start
horus-os doctor --service
```

With the service supervised and keys forwarded, scheduled agents fire on their cron triggers without an open terminal. Confirm a schedule from the dashboard or CLI, then watch its traces accumulate while the service runs.

## See also

- [Remote access](/guides/remote-access/) - reach the always-on dashboard safely with Tailscale
- [Scheduling agents](/guides/scheduling-agents/) - run agents on a cron schedule under the service
- [CLI reference](/reference/cli-reference/) - full `horus-os service` and `doctor` flags
- [Environment variables](/reference/environment-variables/) - data directory and provider key variables
