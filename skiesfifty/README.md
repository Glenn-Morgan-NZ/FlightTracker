# SkiesFifty logo

Every 60 seconds the SkiesFifty logo scrolls onto the display, holds in the centre for 5 seconds, then scrolls off.

It runs as its own service alongside the tracker and sends the animation through the tracker's [Image Upload API](https://flight-tracker.dev) (`POST /api/image`). The tracker's own code is not changed for the logo.

## Files

| File | Purpose |
| --- | --- |
| `push_logo.py` | Builds the animation and sends it to the tracker. Python standard library only. |
| `skiesfifty-logo.service` | systemd unit that starts it on boot (user `glenn`). |
| `logo.pgm` | The logo image. **Not in git**: copy it here by hand (see below). |

## Settings

Set at the top of `push_logo.py`:

| Setting | Default | Meaning |
| --- | --- | --- |
| `INTERVAL` | `60` | Seconds between showings (also `--interval`) |
| `COLOUR` | `(200, 0, 200)` | The purple used for the aircraft type text |
| `BACKGROUND` | `(0, 0, 0)` | Black |
| `SCROLL_SPEED` | `1.5` | Pixels per frame. Lower is slower; 1 is the smoothest |
| `HOLD_MS` | `5000` | How long the logo stays in the centre |

The API key and web port are read from the tracker's `~/.local/share/FlightTracker/config.json` each time, so regenerating the key in the web settings needs no change here.

## Setup on the Pi

1. In the web settings (`http://<pi>:8584/settings`), generate an Image API key.
2. Copy the logo image (a 63x16 plain PGM made from the SkiesFifty lockup) to `~/FlightTracker/skiesfifty/logo.pgm`.
3. Test it once:

   ```bash
   python3 ~/FlightTracker/skiesfifty/push_logo.py --once
   ```

4. Install the service:

   ```bash
   sudo cp ~/FlightTracker/skiesfifty/skiesfifty-logo.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now skiesfifty-logo
   ```

Logs: `journalctl -u skiesfifty-logo`.

## Behaviour

- The logo interrupts whatever is on screen when it is due. The API has no way to see whether flights are showing.
- The API accepts at most 60 frames per upload, so the animation is sent as several uploads, each sent just before the previous one ends.
- If the tracker is restarting or no key is set, that showing is skipped and it tries again next interval.
