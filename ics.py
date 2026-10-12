"""ICS writer for Rater Desk.

Hand-written ICS generation — no icalendar dependency.
Implements:
  - VCALENDAR / VEVENT with TZID
  - Stable UID per block (raterdesk-block-<id>@raterdesk)
  - Escaping of comma, semicolon, backslash, newline
  - 75-octet line folding
"""

import datetime

CRLF = "\r\n"
FOLD_LEN = 75


def escape_text(value):
    """Escape TEXT per RFC 5545 section 3.3.11."""
    if value is None:
        return ""
    s = str(value)
    s = s.replace("\\", "\\\\")
    s = s.replace(";", "\\;")
    s = s.replace(",", "\\,")
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "")
    return s


def format_local_dt(dt):
    """Format an ISO datetime as local time for use with TZID (no Z suffix).

    If tz-aware, convert to the stored timezone first.
    If date-only, emit YYYYMMDD.
    Returns YYYYMMDDTHHMMSS or None on failure.
    """
    if not dt:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(dt)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone()
        parsed = parsed.replace(tzinfo=None)
        return parsed.strftime("%Y%m%dT%H%M%S")
    except (ValueError, TypeError):
        try:
            d = datetime.date.fromisoformat(dt)
            return d.strftime("%Y%m%d")
        except (ValueError, TypeError):
            return None


def fold_line(line):
    """Fold an ICS line at 75 octets (octets, not chars).

    RFC 5545 section 3.1: lines longer than 75 octets are folded by inserting
    CRLF + a single space, and the continuation line must start with a space.
    """
    encoded = line.encode("utf-8")
    if len(encoded) <= FOLD_LEN:
        return line
    result = ""
    pos = 0
    first = True
    while pos < len(encoded):
        if first:
            chunk_size = FOLD_LEN
            prefix = ""
            first = False
        else:
            chunk_size = FOLD_LEN - 1  # leave room for leading space
            prefix = " "
        chunk = encoded[pos:pos + chunk_size]
        if not chunk:
            break
        result += prefix + chunk.decode("utf-8", errors="replace")
        pos += chunk_size
    return result


def build_ics(blocks, tzid="America/New_York"):
    """Build an iCalendar string from a list of block dicts.

    Each block dict needs:
      - starts_at: ISO datetime string
      - ends_at: ISO datetime string
      - title: event summary (may contain commas)
      - calendar_uid: stable UID (derived from block.id)
      - tzid: optional, overrides the default tzid

    Returns a complete iCalendar VCALENDAR string with CRLF line endings.
    """
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    logical_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Rater Desk//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for block in blocks:
        uid = block.get("calendar_uid") or ""
        start = format_local_dt(block.get("starts_at"))
        end = format_local_dt(block.get("ends_at"))
        title = escape_text(block.get("title", ""))
        block_tzid = block.get("tzid", tzid)

        if not start or not end:
            continue

        logical_lines.append("BEGIN:VEVENT")
        logical_lines.append(f"UID:{uid}")
        logical_lines.append(f"DTSTAMP:{now}")
        logical_lines.append(f"DTSTART;TZID={block_tzid}:{start}")
        logical_lines.append(f"DTEND;TZID={block_tzid}:{end}")
        logical_lines.append(f"SUMMARY:{title}")
        if block.get("description"):
            logical_lines.append(f"DESCRIPTION:{escape_text(block['description'])}")
        logical_lines.append("SEQUENCE:0")
        logical_lines.append("END:VEVENT")

    logical_lines.append("END:VCALENDAR")

    # Fold and join with CRLF
    folded = [fold_line(line) for line in logical_lines]
    return CRLF.join(folded) + CRLF


def write_ics_file(blocks, file_path, tzid="America/New_York"):
    """Write ICS content to a file. Returns the file path."""
    content = build_ics(blocks, tzid=tzid)
    with open(file_path, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    return file_path
