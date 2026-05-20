# Authorization & Responsible Use

Android-Crack is offensive tooling. It generates Meterpreter payloads,
installs APKs over ADB, exfiltrates personal data (SMS, contacts, call
logs, WhatsApp media), and toggles security-relevant settings on the
target device. Treat it the same way you would Metasploit itself: only
against targets you own or are explicitly authorized to test.

## Allowed use cases

- **Devices you own.** Your phone, your tablet, your spare.
- **Pen-test engagements** with written scope and Rules of Engagement.
- **CTF / training labs.** Vulnerable Android VMs, intentional ranges.
- **Defensive research.** Reproducing TTPs to build detections.

## Forbidden use

- Devices belonging to other people without explicit written consent.
- Any system you are not authorized to test, even briefly, even for
  "fun" or "curiosity".
- Bypassing employer / school / parental controls without sign-off.
- Anything that violates applicable local, state, federal, or
  international law.

## How the tool enforces it

1. **First-run gate.** Until you confirm:

   ```bash
   android-crack --i-have-authorization
   ```

   every subcommand refuses to act and prints the disclaimer. The
   acknowledgement is persisted in `~/.config/android-crack/config.json`.

2. **Disclaimer banner.** Each launch without a subcommand shows the
   warning panel.

3. **Explicit opt-in for risky behavior.**
   - `exploit run` confirms before generating and installing a payload.
   - `--disable-verifier` is off by default. When used, the verifier is
     restored on exit via `try/finally`.
   - `--auto-accept` is off by default.
   - `wifi disable` and `apps clear` prompt unless `-y` passed.
   - `audit clear` prompts unless `-y` passed.

4. **Audit log.** Every REST call lands in
   `~/.local/share/android-crack/audit.sqlite3` with the operator user,
   host, capability, serial, duration, exit code, and a sha256 of
   stdout. Use `android-crack audit tail` to inspect. This is a
   forensic trail you can hand a client.

## ADB authorization is upstream

Android-Crack does not bypass the "Allow USB debugging?" prompt. The
target device must already trust the host ADB key, either via:

- USB cable + accepted "Always allow from this computer" prompt
- `adb pair HOST:PORT CODE` with a 6-digit code shown on the device
  (Android 11+ Wireless debugging)

A device that has neither will reject every adb command this tool
sends. That is the intended behavior — consent flows back to the device
owner.

## Things explicitly NOT in scope

- AV evasion / payload signature obfuscation
- Silent persistence hooks that survive a factory reset
- Mass-targeting unauthorized hosts from scanner output
- Bypassing ADB authorization itself

These are out of scope and will not be added. If your engagement
genuinely requires them, use purpose-built tooling under a documented
engagement, not this CLI.

## Responsibility

You are responsible for compliance with all applicable laws, including
data-protection statutes (GDPR / CCPA / equivalents) for any personal
information that touches your disk via `export sms`, `export contacts`,
`files bucket whatsapp`, etc. The author of this tool disclaims any
liability for misuse.

If you are unsure whether a particular use is authorized: stop, get it
in writing, then continue.
