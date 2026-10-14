# Rater Desk

A small desktop app I use to keep track of AI rating and training work across several platforms: sign-up steps, a session timer, payouts, and what each platform really pays per hour.

![Money screen](docs/screenshots/money.png)

## What it does

- Times work sessions, by hand or automatically from the browser tab you're in
- Records payouts and shows real hourly pay next to the advertised rate
- Tracks each platform's sign-up steps
- Plans the week and exports it to a calendar (`.ics`)
- Can read platform and PayPal/Payoneer emails to log payouts and status changes
- Keeps everything in one local SQLite file

## Run it

**Windows:** grab `RaterDesk.exe` from the [latest release](https://github.com/nicholasphillips-systems/rater-desk/releases/latest). It isn't code-signed, so click **More info → Run anyway** the first time.

**Linux** (Python 3.10+):

```bash
git clone https://github.com/nicholasphillips-systems/rater-desk.git
cd rater-desk
python3 -m venv ~/.venvs/rater-desk
~/.venvs/rater-desk/bin/pip install -r requirements.txt
./run.sh
```

## Tests

```bash
QT_QPA_PLATFORM=offscreen ~/.venvs/rater-desk/bin/python -m pytest
```

## License

MIT
