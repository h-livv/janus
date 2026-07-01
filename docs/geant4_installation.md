# Geant4 Installation (Linux)

This project depends on **Geant4** with **Qt** and **OpenGL** visualization enabled.

---

## 1. Install Required Dependencies

Update your system and install the required development packages.

```bash
sudo dnf update

sudo dnf install \
    gcc \
    gcc-c++ \
    cmake \
    make \
    git \
    qt6-qtbase-devel \
    qt6-qttools-devel \
    mesa-libGL-devel \
    mesa-libGLU-devel \
    xerces-c-devel \
    expat-devel \
    hdf5-devel \
    libXmu-devel \
    libXi-devel \
    libXt-devel \
    libX11-devel
```

(Optional, but recommended)

```bash
sudo dnf groupinstall "Development Tools"
```

Verify the installation:

```bash
g++ --version
cmake --version
```

---

## 2. Create a Workspace

It is recommended to install Geant4 outside of the project directory.

```bash
mkdir -p ~/software/Geant4
cd ~/software/Geant4
```

---

## 3. Download Geant4

Download the latest stable release from:

https://geant4.web.cern.ch/support/download

Replace `<version>` below with the desired Geant4 release.

```bash
wget https://cern.ch/geant4-data/releases/geant4-<version>.tar.gz
```


Example:

```bash
wget https://cern.ch/geant4-data/releases/geant4-v11.4.2.tar.gz
```

Extract the archive:

```bash
tar -xzf geant4-<version>.tar.gz
```

---

## 4. Create Build and Install Directories

```bash
mkdir geant4-build
mkdir geant4-install
```

---

## 5. Configure Geant4

```bash
cd geant4-build

cmake \
  -DCMAKE_INSTALL_PREFIX=$HOME/opt/Geant4/geant4-install \
  -DGEANT4_INSTALL_DATA=ON \
  -DGEANT4_USE_QT=ON \
  -DGEANT4_USE_OPENGL_X11=ON \
  -DGEANT4_USE_ROOT=ON \
  ../geant4-<version>
```

These options:

- Install all required physics datasets
- Enable the Qt GUI
- Enable OpenGL visualization
- Enable HDF5 support for data export

---

## 6. Build Geant4

```bash
cmake --build . -j$(nproc)
```

---

## 7. Install Geant4

```bash
make install
```

---

## 8. Configure the Geant4 Environment

Add the following line to your shell configuration file.

For Bash:

```bash
echo 'source ~/software/Geant4/geant4-install/bin/geant4.sh' >> ~/.bashrc
```

Reload your shell:

```bash
source ~/.bashrc
```

---

## 9. Verify the Installation

Confirm that Geant4 is available:

```bash
echo $GEANT4_DATA_DIR
```

You can also verify that CMake can locate the installation:

```bash
find ~/software/Geant4/geant4-install -name Geant4Config.cmake
```

Expected output:

```text
~/software/Geant4/geant4-install/lib64/cmake/Geant4/Geant4Config.cmake
```

---

# Building This Project

From the project root:

```bash
mkdir -p build
cd build

cmake ..
cmake --build . -j$(nproc)
```

# Running the simulation

Create a virtual environment and install the project requirements.

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Run the python interface:

```bash
python collision/run.py
```

---

## Install ROOT

Janus uses CERN ROOT as the simulation output format.

On Fedora:

```bash
sudo dnf install \
    root \
    python3-root
```

Verify the installation:

```bash
root --version
root-config --version
```

For the Python data pipeline, install:

```bash
pip install uproot awkward
```

To use the data pipeline, set `"interactive": false` in collision/config.json

---

### Moving an Existing Installation

If you move an existing Geant4 installation after it has been built,
reconfigure and rebuild both Geant4 and this project. CMake embeds
absolute paths to the installation during configuration.

```bash
rm -rf build

mkdir build
cd build

cmake ..
cmake --build . -j$(nproc)
```