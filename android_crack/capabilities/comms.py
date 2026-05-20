"""Communication capabilities: send SMS, open URL.

Both use stable Android primitives that are documented in AOSP /
Android developer docs:

- `service call isms 5` invokes the `sendTextForSubscriber` transaction
  on the SMS manager binder service. Parcel layout follows the public
  AIDL signature.
- `am start -a android.intent.action.VIEW -d URL` is the standard
  Android intent for opening links in the default browser.

These functions require an ADB-authorized device. The SMS path is
known to vary across OEM ROMs and Android versions — BETA.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from android_crack.core.adb_client import AdbClient, AdbResult


_PHONE_RE = re.compile(r"^\+?[0-9 \-]{4,20}$")
_URL_SCHEMES = ("http://", "https://", "tel:", "mailto:", "geo:", "intent:")


def is_plausible_phone(number: str) -> bool:
    return bool(_PHONE_RE.match(number.strip()))


def is_plausible_url(url: str) -> bool:
    if not any(url.startswith(s) for s in _URL_SCHEMES):
        return False
    parsed = urlparse(url)
    return bool(parsed.scheme)


async def send_sms(
    client: AdbClient,
    serial: str,
    number: str,
    message: str,
) -> AdbResult:
    """Send an SMS via the on-device telephony service.

    Implemented as `service call isms 5` (sendTextForSubscriber).
    Parcel layout (Android 12 reference):
      i32  subscription id (0 = default)
      s16  calling package
      s16  attribution tag (null)
      s16  destination address
      s16  service centre (null)
      s16  text message
      s16  sent intent (null)
      s16  delivered intent (null)
      s16  messageUri (null)
      s16  callingMessageId (null)

    Returns the raw AdbResult. OEMs vary; on failure inspect stderr.
    """
    if not is_plausible_phone(number):
        raise ValueError(f"Invalid phone number: {number!r}")
    if not message:
        raise ValueError("Empty message")

    safe_number = number.replace('"', "")
    safe_message = message.replace('"', '\\"')

    cmd = (
        "service call isms 5 "
        "i32 0 "
        's16 "com.android.mms.service" '
        "s16 null "
        f's16 "{safe_number}" '
        "s16 null "
        f's16 "{safe_message}" '
        "s16 null "
        "s16 null "
        "s16 null "
        "s16 null"
    )
    return await client.shell(cmd, serial=serial)


async def open_link(client: AdbClient, serial: str, url: str) -> AdbResult:
    """Launch a URL via the default VIEW intent on the device."""
    if not is_plausible_url(url):
        raise ValueError(
            f"URL must start with one of {', '.join(_URL_SCHEMES)} — got {url!r}"
        )
    safe = url.replace('"', "")
    return await client.shell(
        f'am start -a android.intent.action.VIEW -d "{safe}"',
        serial=serial,
    )
