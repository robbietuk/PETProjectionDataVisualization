# Getting set up

This guide takes you from a computer with nothing installed to a running viewer, on Windows, macOS
and Linux. If you only want to develop the viewer (editable install, pre-commit, tests), see
[CONTRIBUTING.md](https://github.com/robbietuk/PETProjectionDataVisualization/blob/main/CONTRIBUTING.md)
instead.

## Choose a route

| Route | Needs | STIR (`.hs` files) | Use it if |
| --- | --- | --- | --- |
| **Desktop app** | nothing | included | you just want to look at data, without Python |
| **conda** (recommended) | Miniforge | included | you want the viewer and STIR's Python bindings in one place |
| **pip** | Python 3.11 or newer | **not** included | you only open numpy files or the demo, or you already have STIR built from source |

STIR's Python module is a compiled extension and is not on PyPI, so `pip` cannot install it. The conda
route gets it from conda-forge.

### Desktop app (no Python needed)

The desktop apps are self-contained: Python, Qt and STIR are inside. Download the archive for your
operating system from
[GitHub Releases](https://github.com/robbietuk/PETProjectionDataVisualization/releases), unpack it and
double-click the app. The builds are unsigned, so the first launch needs one extra click (macOS: right-click,
**Open**; Windows: *More info > Run anyway*). Details, and the libraries Linux needs, are in
[packaging/README.md](https://github.com/robbietuk/PETProjectionDataVisualization/blob/main/packaging/README.md#first-launch).

Until a release carries the apps, the latest builds are the `PETProjectionDataVisualization-<OS>` artifacts of
the [app workflow](https://github.com/robbietuk/PETProjectionDataVisualization/actions/workflows/app.yml)
(you need to be signed in to GitHub to download them).

### Not published yet?

The viewer is on its way to PyPI and conda-forge. Until the packages exist:

* the conda route uses the repository's
  [environment.yml](https://github.com/robbietuk/PETProjectionDataVisualization/blob/main/environment.yml)
  to get STIR, then installs the viewer from GitHub;
* the pip route installs from GitHub:
  `pip install https://github.com/robbietuk/PETProjectionDataVisualization/archive/refs/heads/main.zip`.

Both are shown in the steps below as "until the package is published".

## Step by step

Open the section for your operating system. In every section, step 1 (Python) is only needed for the pip
route: conda brings its own Python.

<details>
<summary><b>Windows</b> (10 or 11)</summary>

#### 1. Install Python 3.11 or newer (pip route only)

Either download the installer from [python.org](https://www.python.org/downloads/windows/) and, on the first
screen, tick **Add python.exe to PATH**, or install it from PowerShell:

```powershell
winget install Python.Python.3.13
```

Close and reopen PowerShell, then check:

```powershell
py --version
```

It should print `Python 3.11` or newer. `py` is the Python launcher that comes with the python.org
installer; `py -0` lists every Python it knows about.

#### 2. Install conda (Miniforge; conda route only)

Download `Miniforge3-Windows-x86_64.exe` from the
[Miniforge releases](https://github.com/conda-forge/miniforge/releases/latest) and run it with the default
settings ("Just Me"), or:

```powershell
winget install CondaForge.Miniforge3
```

Miniforge uses conda-forge by default. Open **Miniforge Prompt** from the Start menu: that is a shell where
`conda` works. To use `conda` in PowerShell as well, run this once in Miniforge Prompt and reopen PowerShell:

```powershell
conda init powershell
```

The commands in steps 3a and 4 work in both Miniforge Prompt and PowerShell.

#### 3a. Install the viewer with conda (recommended, includes STIR)

```powershell
conda create -n petpdv -c conda-forge petprojectiondatavisualization
conda activate petpdv
```

Until the package is published on conda-forge, use `environment.yml` from the repository instead:

```powershell
curl.exe -L -O https://raw.githubusercontent.com/robbietuk/PETProjectionDataVisualization/main/environment.yml
conda env create -n petpdv -f environment.yml
conda activate petpdv
pip install https://github.com/robbietuk/PETProjectionDataVisualization/archive/refs/heads/main.zip
```

Run `conda activate petpdv` in every new shell before you start the viewer.

#### 3b. Install the viewer with pip (no STIR)

In PowerShell, in a folder of your choice:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install PETProjectionDataVisualization
```

In Command Prompt (`cmd`) the activate line is `.venv\Scripts\activate.bat` instead. If PowerShell refuses to
run `Activate.ps1`, see [Common problems](#powershell-will-not-run-activateps1).

Until the package is published on PyPI, replace the last line with:

```powershell
python -m pip install https://github.com/robbietuk/PETProjectionDataVisualization/archive/refs/heads/main.zip
```

This route has no STIR: numpy files and the demo work, `.hs` files do not, unless you point the viewer at
a STIR build of your own with `--stir-path <STIR install>\python`.

Activate the environment (`.venv\Scripts\Activate.ps1`) in every new shell before you start the viewer.

Now [check that it works](#check-it-works).

</details>

<details>
<summary><b>macOS</b> (Apple silicon or Intel)</summary>

#### 1. Install Python 3.11 or newer (pip route only)

**The `python3` that comes with macOS is too old.** `/usr/bin/python3` is Apple's Python 3.9 from the Xcode
command line tools, and the viewer needs 3.11 or newer. Check what you have:

```bash
which -a python3
python3 --version
```

Install a newer Python in one of three ways.

*Homebrew* (if you do not have it, see [brew.sh](https://brew.sh)):

```bash
brew install python@3.13
```

Homebrew puts its programs in `/opt/homebrew/bin` (Apple silicon) or `/usr/local/bin` (Intel). If
`which python3` still prints `/usr/bin/python3`, Homebrew is not first on your `PATH`. Add it to `~/.zshrc`
(Apple silicon; on an Intel Mac use `/usr/local/bin/brew`) and open a new terminal:

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
```

*python.org*: download the macOS installer from [python.org](https://www.python.org/downloads/macos/) and run
it. It installs `python3.13` into `/usr/local/bin`.

*uv*: [uv](https://docs.astral.sh/uv/) downloads and manages Pythons for you, without touching the system:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.13
```

Check the result with the versioned name, which never means Apple's 3.9:

```bash
python3.13 --version
```

#### 2. Install conda (Miniforge; conda route only)

With Homebrew:

```bash
brew install --cask miniforge
```

or with the installer script:

```bash
curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash "Miniforge3-$(uname)-$(uname -m).sh"
```

Accept the licence, keep the default location (`~/miniforge3`) and answer **yes** when it asks to initialise
conda. Miniforge uses conda-forge by default. Open a new terminal: `conda` now works there. If it does not,
run `~/miniforge3/bin/conda init zsh` (or `conda init zsh` after a Homebrew install) and open a new terminal.

#### 3a. Install the viewer with conda (recommended, includes STIR)

```bash
conda create -n petpdv -c conda-forge petprojectiondatavisualization
conda activate petpdv
```

Until the package is published on conda-forge, use `environment.yml` from the repository instead:

```bash
curl -L -O https://raw.githubusercontent.com/robbietuk/PETProjectionDataVisualization/main/environment.yml
conda env create -n petpdv -f environment.yml
conda activate petpdv
pip install https://github.com/robbietuk/PETProjectionDataVisualization/archive/refs/heads/main.zip
```

Run `conda activate petpdv` in every new terminal before you start the viewer.

#### 3b. Install the viewer with pip (no STIR)

Create the virtual environment with the Python from step 1, by its versioned name:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install PETProjectionDataVisualization
```

With uv, `uv venv --python 3.13 .venv` replaces the first line.

Until the package is published on PyPI, replace the last line with:

```bash
python -m pip install https://github.com/robbietuk/PETProjectionDataVisualization/archive/refs/heads/main.zip
```

This route has no STIR: numpy files and the demo work, `.hs` files do not, unless you point the viewer at
a STIR build of your own (see the
[README](https://github.com/robbietuk/PETProjectionDataVisualization/blob/main/README.md#1-from-the-command-line)).

Activate the environment (`source .venv/bin/activate`) in every new terminal before you start the viewer.

Now [check that it works](#check-it-works).

</details>

<details>
<summary><b>Linux</b> (Ubuntu/Debian; Fedora notes at the end)</summary>

#### 1. Install Python 3.11 or newer (pip route only)

```bash
sudo apt update
sudo apt install python3 python3-venv
python3 --version
```

Ubuntu 24.04 (3.12) and Debian 12 (3.11) or newer are recent enough. Ubuntu 22.04 has 3.10, which is too
old. Then either use [uv](https://docs.astral.sh/uv/), which works on any distribution and needs no root:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.13
```

or, on Ubuntu, the deadsnakes PPA:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.13 python3.13-venv
```

Check with `python3.13 --version`, and use `python3.13` instead of `python3` in step 3b.

The viewer's window also needs some Qt system libraries:

```bash
sudo apt install libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0
```

#### 2. Install conda (Miniforge; conda route only)

```bash
curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash "Miniforge3-$(uname)-$(uname -m).sh"
```

Accept the licence, keep the default location (`~/miniforge3`) and answer **yes** when it asks to initialise
conda. Miniforge uses conda-forge by default. Open a new terminal: `conda` now works there. If it does not,
run `~/miniforge3/bin/conda init bash` and open a new terminal.

#### 3a. Install the viewer with conda (recommended, includes STIR)

```bash
conda create -n petpdv -c conda-forge petprojectiondatavisualization
conda activate petpdv
```

Until the package is published on conda-forge, use `environment.yml` from the repository instead:

```bash
curl -L -O https://raw.githubusercontent.com/robbietuk/PETProjectionDataVisualization/main/environment.yml
conda env create -n petpdv -f environment.yml
conda activate petpdv
pip install https://github.com/robbietuk/PETProjectionDataVisualization/archive/refs/heads/main.zip
```

Run `conda activate petpdv` in every new terminal before you start the viewer.

#### 3b. Install the viewer with pip (no STIR)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install PETProjectionDataVisualization
```

With uv, `uv venv --python 3.13 .venv` replaces the first line; with deadsnakes, use `python3.13 -m venv .venv`.

Until the package is published on PyPI, replace the last line with:

```bash
python -m pip install https://github.com/robbietuk/PETProjectionDataVisualization/archive/refs/heads/main.zip
```

This route has no STIR: numpy files and the demo work, `.hs` files do not, unless you point the viewer at
a STIR build of your own (see the
[README](https://github.com/robbietuk/PETProjectionDataVisualization/blob/main/README.md#1-from-the-command-line)).

Activate the environment (`source .venv/bin/activate`) in every new terminal before you start the viewer.

#### Fedora

Fedora's Python is recent enough and includes `venv`. Steps 2 to 3b are the same; step 1 becomes:

```bash
sudo dnf install python3
sudo dnf install mesa-libEGL mesa-libGL libxkbcommon-x11 xcb-util-cursor
```

Now [check that it works](#check-it-works).

</details>

## Check it works

With the environment active (`conda activate petpdv`, or the `.venv` activate command):

```bash
pet-projection-data-visualization --version
pet-projection-data-visualization --demo
```

The first prints the version. The second opens the window with a synthetic time-of-flight phantom; the demo
needs no STIR, so it checks Python, Qt and the viewer.

To check whether STIR was found, ask Python directly:

```bash
python -c "import stir; print('STIR found:', stir.__file__)"
```

On the conda route this prints a path inside the `petpdv` environment. On the pip route it normally fails
with `ModuleNotFoundError: No module named 'stir'`; that is expected. In the viewer, opening a `.hs` file
without STIR shows a banner starting *Could not import the 'stir' module*. If STIR is a source build, pass
`--stir-path <STIR install>/python` (or set `STIR_PYTHON_PATH`), as described in the
[README](https://github.com/robbietuk/PETProjectionDataVisualization/blob/main/README.md#1-from-the-command-line).

## Common problems

#### `command not found: python` (or `python` opens the Microsoft Store)

On macOS and Linux the command is `python3` (or the versioned `python3.13`); inside an active virtual or conda
environment `python` works too. On Windows use the launcher, `py`. If Windows opens the Microsoft Store, turn
off the *python.exe* and *python3.exe* entries in *Settings > Apps > Advanced app settings > App execution
aliases*.

#### The wrong Python is used

`python3 --version` prints 3.9 or 3.10, or `pip` says *requires a different Python*. List every Python on your
`PATH`, in the order they are found:

```bash
which -a python3
```

```powershell
where.exe python
py -0
```

The first one wins. On macOS, `/usr/bin/python3` is Apple's 3.9: put Homebrew first (see the macOS section),
or call the new Python by its versioned name (`python3.13`). Once a virtual environment is active, `python`
always means the environment's own Python; delete the `.venv` folder and create it again if it was made with
the wrong one.

#### PowerShell will not run `Activate.ps1`

PowerShell says *running scripts is disabled on this system*. Allow locally created scripts for your user
(this needs no administrator rights), then activate again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.venv\Scripts\Activate.ps1
```

#### Linux: the window does not open (Qt platform plugin errors)

Errors such as *Could not load the Qt platform plugin "xcb"* or *libEGL.so.1: cannot open shared object file*
mean that Qt's system libraries are missing. On Ubuntu/Debian:

```bash
sudo apt install libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0
```

On Fedora: `sudo dnf install mesa-libEGL mesa-libGL libxkbcommon-x11 xcb-util-cursor`.

#### `conda: command not found`

Open a new terminal after installing Miniforge (on Windows, use **Miniforge Prompt**). If it still fails, run
`~/miniforge3/bin/conda init bash` (or `zsh` on macOS) once, or `conda init powershell` from Miniforge Prompt
on Windows, then open a new terminal.
