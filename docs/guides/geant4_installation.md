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
  -DCMAKE_INSTALL_PREFIX=$HOME/software/Geant4/geant4-install \
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
- Enable ROOT support (Janus collision output uses ROOT)

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

# Building the Janus Geant4 engine

From the repository root, with the Geant4 environment loaded (`source …/geant4.sh`):

```bash
cd engines/geant4
mkdir -p build
cd build

cmake ..
cmake --build . -j$(nproc)
```

The executable is `engines/geant4/build/janus`. Collision runs invoke it via `interactions/interface.py`.

If you move an existing Geant4 installation after it has been built, reconfigure and rebuild both Geant4 and this project. CMake embeds absolute paths during configuration:

```bash
cd engines/geant4
rm -rf build
mkdir build && cd build
cmake ..
cmake --build . -j$(nproc)
```

---

## Install ROOT (output format)

Janus uses CERN ROOT as the collision output format.

On Fedora:

```bash
sudo dnf install \
    root \
    python3-root
```

Verify:

```bash
root --version
root-config --version
```

For the Python packaging / validation path:

```bash
pip install -r requirements.txt
pip install uproot awkward particle matplotlib
```

(`particle` is required by `interactions/validation/validate.py` and particle-summary generation.)

---

## Next steps

1. **Run a collision study** — [collision guide](collision_guide.md)
2. **Validate ROOT output** — [collision validation](../validation/collision_validation.md)
3. **Transport seeds** — [transport guide](transport_guide.md)
4. **Pipeline overview** — [architecture](../ARCHITECTURE.md)
