---
title: "Remote access"
description: "Reach your horus-os dashboard safely from another device using Tailscale, where the tailnet is the authentication boundary."
---

## Before you start

horus-os ships **no app-level authentication** in this release. The dashboard trusts whoever can reach it on the network. That single fact shapes everything on this page: the only sanctioned way to reach your instance from another device is to put a real authentication layer in front of it, and the supported answer is [Tailscale](https://tailscale.com/), where your tailnet (WireGuard plus device ACLs) is the authentication layer.

> [!WARNING]
> Do not expose the dashboard to the public internet. It has no login. Anyone who can reach it can read your traces, agent prompts, and tasks, and drive the dashboard. See [Security](/operations/security/).

## The loopback default

By default, `horus-os serve` binds to loopback only:

```bash
horus-os serve                  # binds 127.0.0.1:8765 (loopback only, safe default)
```

`127.0.0.1` is reachable only from the same machine. Nothing on your LAN, your Wi-Fi, or the internet can connect to it. This is the safe default, and it is what you want for local use and for the Tailscale path below.

## Why --host 0.0.0.0 is dangerous

You can override the bind address with `--host`:

```bash
horus-os serve --host 0.0.0.0   # binds EVERY interface (DANGEROUS, no app auth)
```

Binding to `0.0.0.0` exposes the dashboard on every network interface: your LAN, your Wi-Fi, and any routable address the machine holds. Because horus-os ships no app-level authentication, anyone who can reach that address can use the dashboard with no login.

Do not bind to `0.0.0.0` (or to any routable interface address) unless a network-level authentication layer, such as an authenticating reverse proxy, already sits in front of the dashboard.

> [!NOTE]
> The key-write endpoint carries a loopback guard: it rejects requests whose TCP peer is not loopback, so credential writes cannot be driven from a remote address. That guard protects key writes specifically. It does not authenticate the dashboard as a whole, and it is not a substitute for the network auth layer described below.

**Rule of thumb:** keep `serve` on `127.0.0.1` and reach it remotely through Tailscale. Reserve `--host 0.0.0.0` for cases where you have already placed an authenticating reverse proxy or equivalent in front of the dashboard.

## The supported path: tailscale serve

Tailscale gives every device in your private network (your tailnet) a stable identity and an encrypted WireGuard link. With `tailscale serve`, the tailnet itself is the authentication boundary: only devices you have explicitly added to your tailnet, and that pass your device ACLs, can reach the dashboard. `tailscale serve` also injects identity headers describing the calling device.

This is the supported remote-access path. Run it on the machine hosting horus-os:

```bash
# 1. Join the machine to your tailnet (opens a browser to authenticate once).
tailscale up

# 2. Start horus-os on loopback. Tailscale proxies to it; --host 0.0.0.0 is NOT needed.
horus-os serve

# 3. Expose port 8765 to your tailnet over HTTPS (tailnet-only, not public).
tailscale serve 8765
```

Then, from another device that is logged into the same tailnet, open the machine's MagicDNS hostname in a browser:

```text
https://your-machine.your-tailnet.ts.net
```

Replace `your-machine` and `your-tailnet` with your own MagicDNS name. Run `tailscale status` on the host to see it.

Traffic flows from your remote device, over WireGuard, to `tailscale serve`, which proxies to the loopback `127.0.0.1:8765` that horus-os is listening on. The dashboard never binds to a public or LAN-routable address.

Because the tailnet is the auth boundary, you control access by managing tailnet membership and device ACLs in the Tailscale admin console, not by adding logins to horus-os.

> [!TIP]
> For unattended remote use, keep `horus-os serve` supervised by your platform service so it restarts on failure. See [Running as a service](/guides/running-as-a-service/).

## Do not use tailscale funnel

> [!CAUTION]
> Do not use `tailscale funnel` for the horus-os dashboard.
>
> `tailscale funnel` publishes a service to the **public internet**. Unlike `tailscale serve`, Funnel does not restrict access to your tailnet and does not inject identity headers. Anyone on the internet who learns the URL can reach it.
>
> Because horus-os ships no authentication, funneling the dashboard would expose it to the public internet with no authentication at all. Anyone could read your traces, agent prompts, and tasks, and drive the dashboard.

The only sanctioned remote path is `tailscale serve`, where the tailnet is the auth boundary. If you have a genuine need to publish horus-os publicly, put a real authenticating reverse proxy in front of it first. Funnel by itself is not an authentication layer.

## Remote shell access

Reaching the dashboard is one thing; getting a shell on the host machine to run CLI commands, edit env vars, or read logs is another.

### Windows: use OpenSSH, not Tailscale SSH

On Windows, manage the host with the built-in Windows **OpenSSH** server, not Tailscale SSH. Enable the optional OpenSSH Server feature, then connect over SSH across your tailnet:

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

OpenSSH is the mature, supported remote-shell path on Windows. Tailscale SSH is not the recommended mechanism for Windows hosts here.

### Linux and macOS

On Linux and macOS, reach a shell over your tailnet with ordinary SSH if you need to run CLI commands. To keep the dashboard itself running without a remote shell, use the platform-native always-on service so `horus-os serve` is supervised by systemd or launchd and restarts on failure. See [Running as a service](/guides/running-as-a-service/).

## See also

- [Running as a service](/guides/running-as-a-service/)
- [Security](/operations/security/)
- [Deploy to Vercel](/operations/deploy-to-vercel/)
- [The dashboard](/guides/dashboard/)
