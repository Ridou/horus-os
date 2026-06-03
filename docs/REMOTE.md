# Remote access and the always-on service

This guide covers two related topics for running horus-os beyond your local
machine: how to expose the dashboard safely, and how to keep `horus-os serve`
running 24/7 as a platform-native service.

horus-os ships **no app-level authentication** in this release. That single
fact shapes every recommendation below. The dashboard trusts whoever can reach
it on the network, so the only sanctioned way to reach it remotely is to put a
real authentication layer in front of it. The supported answer is Tailscale,
where your tailnet (WireGuard plus device ACLs) IS the authentication layer.

## 1. `serve --host` and the loopback default (REMOTE-02)

By default, `horus-os serve` binds to loopback only:

```bash
horus-os serve                  # binds 127.0.0.1:8765 (loopback only, safe default)
```

`127.0.0.1` is reachable only from the same machine. Nothing on your LAN, your
Wi-Fi, or the internet can connect to it. This is the safe default and it is
what you want for local use and for the Tailscale path below.

You can override the bind address with `--host`:

```bash
horus-os serve --host 0.0.0.0   # binds EVERY interface (DANGEROUS, no app auth)
```

Binding to `0.0.0.0` exposes the dashboard on every network interface: your
LAN, your Wi-Fi, and any routable address the machine holds. Because horus-os
ships no app-level authentication, anyone who can reach that address can use
the dashboard with no login. Do not bind to `0.0.0.0` (or to any routable
interface address) unless a network-level authentication layer sits in front of
it.

Note that even the key-write endpoint carries a loopback guard added in
Phase 62: it rejects requests whose TCP peer is not loopback, so credential
writes cannot be driven from a remote address. That guard protects key writes
specifically. It does not authenticate the dashboard as a whole, and it is not
a substitute for the network auth layer described below.

**Rule of thumb:** keep `serve` on `127.0.0.1` and reach it remotely through
Tailscale. Reserve `--host 0.0.0.0` for cases where you have already placed an
authenticating reverse proxy or equivalent in front of the dashboard.

## 2. Tailscale serve happy path (REMOTE-03)

Tailscale gives every device in your private network (your tailnet) a stable
identity and an encrypted WireGuard link. With `tailscale serve`, the tailnet
itself is the authentication boundary: only devices you have explicitly added
to your tailnet, and that pass your device ACLs, can reach the dashboard.
`tailscale serve` also injects identity headers describing the calling device.

This is the supported remote-access path. Run it on the machine hosting
horus-os:

```bash
# 1. Join the machine to your tailnet (opens a browser to authenticate once).
tailscale up

# 2. Start horus-os on loopback. Tailscale proxies to it; --host 0.0.0.0 is NOT needed.
horus-os serve

# 3. Expose port 8765 to your tailnet over HTTPS (tailnet-only, not public).
tailscale serve 8765
```

Then, from another device that is logged into the same tailnet, open the
machine's MagicDNS hostname in a browser:

```
https://your-machine.your-tailnet.ts.net
```

Replace `your-machine` and `your-tailnet` with your own MagicDNS name (run
`tailscale status` on the host to see it). Traffic flows from your remote
device, over WireGuard, to `tailscale serve`, which proxies to the loopback
`127.0.0.1:8765` that horus-os is listening on. The dashboard never binds to a
public or LAN-routable address.

Because the tailnet is the auth boundary, you control access by managing tailnet
membership and device ACLs in the Tailscale admin console, not by adding logins
to horus-os.

## 3. Hard do-not: tailscale funnel (REMOTE-03)

> **DO NOT use `tailscale funnel` for the horus-os dashboard.**
>
> `tailscale funnel` publishes a service to the **public internet**. Unlike
> `tailscale serve`, Funnel does NOT restrict access to your tailnet and does
> NOT inject identity headers. Anyone on the internet who learns the URL can
> reach it.
>
> Because horus-os ships **no authentication**, funneling the dashboard would
> expose it to the public internet with **no** authentication at all. That
> means anyone could read your traces, agent prompts, and tasks, and drive the
> dashboard. Do not do this until app-level authentication ships.
>
> The only sanctioned remote path is `tailscale serve` (Section 2), where the
> tailnet is the auth boundary.

If you have a genuine need to publish horus-os publicly, put a real
authenticating reverse proxy in front of it first. Funnel by itself is not an
authentication layer.

## 4. Remote management of the host

Reaching the dashboard is one thing; managing the host machine (a shell to run
`horus-os service`, edit env vars, or read logs) is another. The recommendation
differs by OS.

### Windows: use OpenSSH, not Tailscale SSH

On Windows, manage the host with the built-in Windows **OpenSSH** server, not
Tailscale SSH. Enable the optional OpenSSH Server feature, then connect over
SSH (port 22) across your tailnet:

```powershell
# In an elevated PowerShell, add and start the OpenSSH server feature.
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
```

Then SSH to the machine's tailnet address from another device:

```bash
ssh your-user@your-machine.your-tailnet.ts.net
```

OpenSSH is the mature, supported remote-shell path on Windows. Tailscale SSH is
not the recommended mechanism for Windows hosts here.

### Linux and macOS: keep `serve` alive with the platform service

On Linux and macOS, you do not need a separate remote-shell story to keep the
dashboard running: use the platform-native always-on service (Section 5) so
`horus-os serve` is supervised by systemd or launchd and restarts on failure.
Reach a shell over your tailnet with ordinary SSH if you need to run CLI
commands.

## 5. Always-on service install guide (REMOTE-04)

`horus-os service` registers a platform-native service that runs
`horus-os serve` continuously and restarts it on failure. The guided path is
the same on every OS: install, then verify with the doctor.

```bash
# Preview the generated service definition without touching the OS (dry run).
horus-os service install --print

# Register and start the service.
horus-os service install

# Verify it is registered and running.
horus-os doctor --service
```

The full lifecycle is available:

```bash
horus-os service start
horus-os service stop
horus-os service status
horus-os service uninstall
```

`horus-os doctor --service` exits 0 only when the service is both registered
and running, and prints a structured report otherwise. It guides rather than
crashes when a required supervisor binary is missing.

### Per-OS notes

**Linux (systemd --user).** The service installs as a user unit at
`~/.config/systemd/user/horus-os.service` with `Restart=on-failure`. No admin
is needed to install or run it while you are logged in. To keep it alive after
you log out (for example on a headless box), enable lingering once:

```bash
sudo loginctl enable-linger "$USER"
```

This is the one admin-ish step on Linux, and it is only required for
survive-logout persistence. `horus-os doctor --service` reports your linger
status so you know whether the service will outlive your session.

**macOS (launchd LaunchAgent).** The service installs as a LaunchAgent at
`~/Library/LaunchAgents/sh.horus-os.plist` with `RunAtLoad` and `KeepAlive`,
so it starts at GUI login and is kept running. No admin is needed. Note that a
LaunchAgent runs only while a user is logged into the GUI session: after a
reboot it starts once you log in, not before. Pre-login always-on would require
a LaunchDaemon (admin), which is out of scope for the no-admin default.

**Windows (NSSM, with a no-admin fallback).** The default Windows mechanism is
NSSM, which gives a true service with restart-on-failure. NSSM is not bundled
with Windows; install it first (for example from `https://nssm.cc`, or with
`choco install nssm` or `winget install NSSM.NSSM`). NSSM registers a system
service, so `horus-os service install` must run in an administrator shell on
Windows. This is a deliberate, documented exception to the no-admin default,
because Windows has no clean user-level always-on mechanism with genuine
crash-restart.

If you refuse admin on Windows, the no-admin fallback is a Task Scheduler
at-logon task (`schtasks /create /sc onlogon ...`). It starts the dashboard
when you log in but does not provide native crash-restart and does not run
before logon. Use NSSM when you can; use Task Scheduler when you cannot grant
admin.

### Forwarding env vars (API keys and data dir) into the service

A supervised service does NOT inherit the environment of your interactive
shell. If your agents need provider keys, the service process must be given
them explicitly, or your scheduled and dashboard runs will fail with
missing-key errors even though the CLI works for you interactively.

- The generated definition sets `HORUS_OS_DATA_DIR` so the service uses the
  same data directory as your CLI. If you keep your data dir elsewhere, set
  `HORUS_OS_DATA_DIR` in the service environment to match.
- Forward provider keys (for example your Anthropic or Gemini key) into the
  service environment using the platform mechanism:
  - systemd: add `Environment=` lines to the unit, or an `EnvironmentFile=`
    pointing at your `~/.config/horus-os/.env`.
  - launchd: add an `EnvironmentVariables` dict to the plist.
  - NSSM: `nssm set horus-os AppEnvironmentExtra "ANTHROPIC_API_KEY=your-api-key"`.

Never commit real keys into any of these files. Use placeholders like
`your-api-key` in examples and keep the real values in your own untracked
environment files.

## Summary

- Keep `horus-os serve` on the `127.0.0.1` loopback default. `--host 0.0.0.0`
  exposes an unauthenticated dashboard and is unsafe without a network auth
  layer.
- Reach the dashboard remotely with `tailscale serve`, where the tailnet is
  the authentication boundary.
- Never `tailscale funnel` the dashboard: Funnel is the public internet with no
  authentication.
- On Windows, manage the host over OpenSSH, not Tailscale SSH.
- Install the always-on service with `horus-os service install` and verify it
  with `horus-os doctor --service`.
