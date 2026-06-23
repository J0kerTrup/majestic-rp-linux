# Installation

This project is installed as the `majestic-linux-runner` package. After package installation, the main command is:

```bash
majestic-linux
```

The old repository wrapper still works when running from a source checkout:

```bash
./install-and-run-majestic-proton.sh
```

## Requirements

- Python 3.11 or newer.
- Steam GTA V with an existing Proton prefix, or manually configured Proton and GTA paths.
- `protontricks` or `winetricks` for first-run prefix setup.
- `asar` for Majestic Launcher `app.asar` patching.
- Optional: `xdotool` for Caps Lock cleanup before launch.

Keep the project path ASCII-only. Proton, Wine, and some shell tools can fail on non-English paths.

## Arch Linux / AUR

Current AUR package: <https://aur.archlinux.org/packages/majestic-linux-runner-git>

With an AUR helper:

```bash
yay -S majestic-linux-runner-git
```

Without an AUR helper:

```bash
git clone https://aur.archlinux.org/majestic-linux-runner-git.git
cd majestic-linux-runner-git
makepkg -si
```

Then run:

```bash
majestic-linux config
majestic-linux doctor
majestic-linux install
majestic-linux run
```

If `asar`, `protontricks`, or `winetricks` is missing, install the missing dependency with `pacman` or from AUR, depending on your distribution packaging.

## Debian / Ubuntu

Download the `.deb` package from the project releases, then install it:

```bash
sudo apt update
sudo apt install ./majestic-linux-runner_<version>_all.deb
```

If dependency resolution fails, run:

```bash
sudo apt --fix-broken install
```

Then run:

```bash
majestic-linux config
majestic-linux doctor
majestic-linux install
majestic-linux run
```

The package installs the `majestic-linux` command, a desktop entry, the example config, and a bundled `asar` command.

## Fedora / RPM

Download the `.rpm` package from the project releases, then install it:

```bash
sudo dnf install ./majestic-linux-runner-<version>-<release>.noarch.rpm
```

On RPM-based systems without `dnf`, use the system package manager, for example:

```bash
sudo zypper install ./majestic-linux-runner-<version>-<release>.noarch.rpm
```

Then run:

```bash
majestic-linux config
majestic-linux doctor
majestic-linux install
majestic-linux run
```

The package installs the `majestic-linux` command, a desktop entry, the example config, and a bundled `asar` command.

## Configuration

The default config path is:

```text
$XDG_CONFIG_HOME/majestic-runner/majestic-runner.conf
```

If `XDG_CONFIG_HOME` is unset, the runner uses:

```text
~/.config/majestic-runner/majestic-runner.conf
```

Most users should leave path values empty and let auto-detection find Steam, Proton, GTA V, compatdata, and Majestic Launcher.

To use a custom config path:

```bash
majestic-linux --config /path/to/majestic-runner.conf doctor
majestic-linux --config /path/to/majestic-runner.conf run
```

## First Run Checklist

1. Create or review the config:

   ```bash
   majestic-linux config
   ```

2. Check detected paths and dependencies:

   ```bash
   majestic-linux doctor
   ```

3. Prepare the prefix and install/patch Majestic Launcher if needed:

   ```bash
   majestic-linux install
   ```

4. Launch:

   ```bash
   majestic-linux run
   ```

For GUI diagnostics during prefix setup:

```bash
majestic-linux install --gui
majestic-linux run --gui
```
