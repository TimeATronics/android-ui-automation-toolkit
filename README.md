# Android UI Automation Toolkit

Small, dependency-free helpers for automating Android device UI over ADB. It
started as a way to fill metadata in a controller-first game launcher whose
custom on-screen keyboard did not reliably handle spaces, capital letters, or
punctuation when driven through ADB.

The repository contains code and scripts only. It does **not** include game
artwork, ROMs, APKs, or other third-party binaries.

## Contents

- `cliphelper/` — a tiny Android app that sets the system clipboard from a
  base64 intent extra and immediately closes.
- `automation/adb_ui.py` — reusable ADB wrapper: tap, long-press, key events,
  clipboard, screenshots, focus checks.
- `automation/run_actions.py` — execute a JSON list of UI actions.
- `automation/cocoon_metadata.py` — example workflow that fills a Cocoon
  metadata editor from a JSON file or command-line values.
- `automation/cocoon_config.example.json` — example coordinates and timing.
- `examples/metadata.example.json` — example metadata input.

## Requirements

- Python 3.9 or newer.
- Android SDK Platform Tools (`adb`) and a device with USB debugging enabled.
- Android Studio, or Gradle 8.7+ and JDK 17, to build the clipboard helper.

No Python packages are required.

## Setup

```bash
export ADB="$HOME/Android/Sdk/platform-tools/adb"
export ANDROID_SERIAL="your-device-serial"
adb devices
```

On Windows PowerShell:

```powershell
$env:ADB = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$env:ANDROID_SERIAL = "your-device-serial"
& $env:ADB devices
```

## Clipboard helper

### Why it exists

Some controller-first Android apps render their own keyboard. Sending taps for
each character can lose spaces, case, or punctuation. Placing the complete
string on the system clipboard and using the app's Paste button is much more
reliable.

### Build and install

Open `cliphelper/` in Android Studio, or build with Gradle:

```bash
cd cliphelper
gradle :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

The app has no UI and no network permission. It is intentionally tiny: read
the `b64` extra, write the clipboard, finish.

### Use it

Linux/macOS:

```bash
B64="$(printf %s 'Motion Twin' | base64 -w0)"
adb shell am start -W -n com.ayaneo.cliphelper/.MainActivity --es b64 "$B64"
```

PowerShell:

```powershell
$text = 'Motion Twin'
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($text))
& $env:ADB shell am start -W -n com.ayaneo.cliphelper/.MainActivity --es b64 $b64
```

The activity finishes immediately. Android 10+ generally lets the currently
focused app read clipboard data; tap the target app's Paste button after running
the helper.

### Remove it

When it is no longer needed:

```bash
adb uninstall com.ayaneo.cliphelper
```

## UI automation scripts

### Low-level wrapper

`automation/adb_ui.py` is intentionally boring and readable. It wraps methods
such as:

- `tap(x, y)`
- `long_press(x, y, ms=1100)` — uses separate `motionevent DOWN`/`UP`
  events, which is more reliable than `input swipe` on some launchers
- `keyevent(53)` — controller Y in the example workflow
- `set_clipboard(text)`
- `paste(paste_x, paste_y, confirm_x, confirm_y)`
- `screenshot(path)`
- `current_focus()`

Serial and adb path come from `ANDROID_SERIAL` and `ADB`, or from CLI options.

### JSON action runner

`automation/run_actions.py` runs a list of actions:

```bash
python automation/run_actions.py automation/actions.example.json
```

Supported actions:

```json
{"type": "tap", "x": 640, "y": 480}
{"type": "long_press", "x": 640, "y": 684, "ms": 1200}
{"type": "keyevent", "key": 53}
{"type": "wait", "seconds": 0.5}
{"type": "set_clipboard", "text": "Motion Twin"}
{"type": "paste", "target": [1152, 400], "text": "Motion Twin", "paste": [104, 500], "confirm": [1196, 72]}
{"type": "screenshot", "path": "screen.png"}
```

Use `--dry-run` to print the parsed actions without contacting the device.

### Cocoon metadata example

The example script assumes the game popup is open. It sends controller Y and
Enter to reach **Edit App → Edit Metadata**, fills fields, and taps the
top-right save action.

```bash
python automation/cocoon_metadata.py \
  --metadata path/to/metadata.json \
  --config automation/cocoon_config.example.json
```

Individual values are also accepted:

```bash
python automation/cocoon_metadata.py \
  --publisher "Motion Twin" \
  --release-date "2018-08-06" \
  --description "A short description."
```

To edit the title too:

```bash
python automation/cocoon_metadata.py \
  --set-title \
  --title "The Legend of Zelda: Twilight Princess" \
  --publisher "Nintendo" \
  --release-date "2006-11-19" \
  --description "A short description."
```

If the metadata editor is already open, add `--editor-open` to skip the
controller-key sequence. Use `--screenshot after.png` to capture the result.

#### Calibration

The coordinates in `cocoon_config.example.json` are starting points, not
universal values. Calibrate against a screenshot from your device:

```bash
adb exec-out screencap -p > before.png
adb shell uiautomator dump /sdcard/window.xml
adb pull /sdcard/window.xml
```

The metadata list can scroll by a small amount after a field is filled, so
verify all three field taps before relying on an unattended run. For a
different device or launcher version, adjust the `x`/`y` values in a private
copy of the config. Keep the example config generic.

## Where the metadata and artwork came from

These are the sources and practical rules used while building a personal game
library.

### Game metadata

**Steam Store API** was the main source for published PC games:

```text
https://store.steampowered.com/api/appdetails?appids=400&l=english&cc=us
https://store.steampowered.com/api/storesearch/?term=portal&l=english&cc=us
```

Useful fields include `name`, `publishers`, `developers`,
`release_date.date`, `short_description`, and `genres`. Normalize the release
date to ISO format yourself; some Steam dates are re-release dates rather than
the original platform date.

For non-Steam games, use the publisher's press kit, IGDB, RAWG, Wikipedia, or
the game's official site. Confirm the original release date and publisher
rather than copying a storefront re-release date.

### SteamGridDB artwork

SteamGridDB is an excellent source for launcher artwork because it categorizes
assets by type.

Official API (requires a free API key):

```text
GET https://www.steamgriddb.com/api/v2/search/autocomplete/portal
GET https://www.steamgriddb.com/api/v2/games/id/9022
GET https://www.steamgriddb.com/api/v2/heroes/game/9022
GET https://www.steamgriddb.com/api/v2/logos/game/9022
GET https://www.steamgriddb.com/api/v2/grids/game/9022
GET https://www.steamgriddb.com/api/v2/icons/game/9022
Authorization: Bearer <steamgriddb-api-key>
```

Asset types and how they were used:

- `heroes` — wide background art, usually 3840×1240 or similar. Resize/crop to
  the launcher's hero size, for example 1920×620 JPEG.
- `logos` — transparent wordmarks. Prefer official or white variants, trim
  transparent padding, and keep the longest side around 2048 px.
- `grids` — box art, usually portrait. Use as the portrait icon source. When a
  square icon is required, crop around the artwork while keeping the title
  readable; do not cut off the title.
- `icons` — square icons. Use directly when the launcher expects a square icon.

Filter out NSFW assets and inspect alpha/background before using a logo. Some
community logos have a baked-in background even though they are PNG files.

The public website also exposes internal JSON endpoints such as:

```text
/api/public/search/autocomplete?term=portal
/api/public/game/9022/home
```

Those endpoints are what a browser session uses; they are undocumented, may
change without notice, and should be treated as a fallback only. Respect
SteamGridDB's terms and rate limits, and prefer the official API.

### Android app icons and app artwork

For Play Store apps, the store listing's `og:image` is a convenient high-res
icon source. For installed apps, locate the APK and inspect its launcher
resources:

```bash
adb shell pm path com.example.app
adb pull /data/app/.../base.apk
```

Adaptive icons may be XML with separate foreground/background layers; extract
the relevant drawables with `aapt2` or inspect the APK zip. For system apps,
the package can live under `/system` or `/product`.

Chrome and YouTube-style app artwork was built from official app icons plus a
brand wordmark and a wide background. For a console-themed app, use the app
icon and a neutral 3DS/Switch-inspired layout rather than redistributing
console UI screenshots.

### Other places worth checking

- IGDB: https://www.igdb.com/ (API via Twitch developer credentials)
- RAWG: https://rawg.io/ (API key required)
- Wikipedia/Wikidata for release dates and publisher facts
- Official publisher press kits and media pages
- SteamCDN/Steam store media for screenshots when the license allows personal
  use

### Practical image sizes

These are useful defaults, not hard requirements:

- Hero: 1920×620 JPEG, quality around 90–92
- Logo: transparent PNG, 1200–2048 px wide
- Square icon: 600×600 or 1024×1024 PNG
- Portrait box art: preserve the original aspect ratio; crop only where the
  launcher requires square art

## Safety and legal notes

- Use this only on devices and accounts you own or are authorized to manage.
- Prefer UI automation over editing app databases or app-private files.
- Do not commit ROMs, BIOS files, APKs, artwork, screenshots, or metadata dumps
  that you do not have the right to redistribute.
- Game names, logos, and artwork belong to their respective owners. This
  repository contains no such assets.
- This is not affiliated with Cocoon, SteamGridDB, Google, Nintendo, or any
  game publisher.
