from pathlib import Path
import subprocess
import shutil
import json
from datetime import datetime

# =========================================================
# Paths
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
ENGINE_DIR = BASE_DIR.parent / "engine"
PROJECT_ROOT = BASE_DIR.parent

EXECUTABLE = ENGINE_DIR / "build" / "janus"
MACRO_PATH = ENGINE_DIR / "macros" / "run.mac"

# Where the C++ engine hardcodes the output
HARDCODED_CSV = PROJECT_ROOT / "temp" / "particle_tracks.csv"

# The master directory where your packaged runs will be saved
OUTPUT_DIR = PROJECT_ROOT / "outputs"


# =========================================================
# Beam Configuration
# =========================================================

class Beam:
    def __init__(self):
        #Basic
        self.particle = "proton"
        self.count = 1000
        
        # Profile
        self.profile = "Flat"      # "Flat", "Gaussian", or "Point"
        self.radius = "1 cm"       # Used if profile is Flat
        self.sigma = "0.5 cm"      # Used if profile is Gaussian
        
        # Energy
        self.energy_dist = "Mono"  # "Mono" or "Gaussian"
        self.energy_mean = "10 GeV"
        self.energy_sigma = "1 GeV" # Used if energy_dist is Gaussian
        
# =========================================================
# Target Configuration
# =========================================================



# =========================================================
# Simulation Engine
# =========================================================

class Simulation:

    def __init__(self):

        self.beam = Beam()

    # -----------------------------------------------------
    # Macro Generation
    # -----------------------------------------------------

    def generate_macro(self):

        lines = [
            # Verbosity
            "/control/verbose 0",
            "/run/verbose 0",
            "/event/verbose 0",
            "/tracking/verbose 0",

            # Initialize
            "/run/initialize",

            # Particle
            f"/gun/particle {self.beam.particle}",

            # Profile & Position
            f"/gun/beam/profile {self.beam.profile}",
        ]

        if self.beam.profile == "Flat":
            lines.append(f"/gun/beam/radius {self.beam.radius}")
        elif self.beam.profile == "Gaussian":
            lines.append(f"/gun/beam/sigma {self.beam.sigma}")

        # Geometry
        lines.append(f"/gun/beam/direction {self.beam.direction}")
        lines.append(f"/gun/beam/offset {self.beam.offset}")

        # Energy
        lines.append(f"/gun/beam/energyDist {self.beam.energy_dist}")
        lines.append(f"/gun/beam/energyMean {self.beam.energy_mean}")
        
        if self.beam.energy_dist == "Gaussian":
            lines.append(f"/gun/beam/energySigma {self.beam.energy_sigma}")

        # Run
        lines.append(f"/run/beamOn {self.beam.count}")

        return "\n".join(lines)

    # -----------------------------------------------------
    # Write Macro File
    # -----------------------------------------------------

    def write_macro(self):

        macro = self.generate_macro()

        with open(MACRO_PATH, "w") as f:
            f.write(macro)
            
    
    # -----------------------------------------------------
    # Data Packaging
    # -----------------------------------------------------

    def get_run_identifier(self):
        """Generates a unique timestamped name for the run folder."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        energy_str = self.beam.energy_mean.replace(" ", "")
        return f"run_{timestamp}_{self.beam.particle}_{energy_str}"

    def save_metadata(self, run_folder, run_name):
        """Creates the JSON configuration file."""
        metadata = {
            "run_id": run_name,
            "timestamp": datetime.now().isoformat(),
            "beam": {
                "particle": self.beam.particle,
                "events": self.beam.count,
                "profile": self.beam.profile,
                "radius": self.beam.radius if self.beam.profile == "Flat" else None,
                "sigma": self.beam.sigma if self.beam.profile == "Gaussian" else None,
                "direction": self.beam.direction,
                "offset": self.beam.offset,
                "energy_dist": self.beam.energy_dist,
                "energy_mean": self.beam.energy_mean,
                "energy_sigma": self.beam.energy_sigma if self.beam.energy_dist == "Gaussian" else None
            }
            # You can easily add a "target" dictionary here later
        }
        
        json_path = run_folder / f"{run_name}_config.json"
        with open(json_path, "w") as f:
            json.dump(metadata, f, indent=4)

    # -----------------------------------------------------
    # Run Simulation
    # -----------------------------------------------------

    
    def run(self):

        self.write_macro()

        print("\n========== JANUS SIMULATION ==========")
        print(f"Particle    : {self.beam.particle}")
        print(f"Events      : {self.beam.count}")
        print(f"Profile     : {self.beam.profile}")
        
        if self.beam.profile == "Flat":
            print(f"  Radius    : {self.beam.radius}")
        elif self.beam.profile == "Gaussian":
            print(f"  Sigma     : {self.beam.sigma}")
            
        print(f"Direction   : {self.beam.direction}")
        print(f"Offset      : {self.beam.offset}")
        print(f"Energy Dist : {self.beam.energy_dist}")
        print(f"  Mean      : {self.beam.energy_mean}")
        
        if self.beam.energy_dist == "Gaussian":
            print(f"  Spread    : {self.beam.energy_sigma}")
            
        print("======================================\n")

        result = subprocess.run(
            [str(EXECUTABLE), str(MACRO_PATH)],
            cwd=ENGINE_DIR / "build",
            capture_output=True,
            text=True
        )

        # -------------------------------------------------
        # Errors
        # -------------------------------------------------

        if result.returncode != 0:

            print("Simulation failed.\n")

            if result.stderr:
                print(result.stderr)

            return
        
        # -------------------------------------------------
        # Data Packaging & Archiving
        # -------------------------------------------------
        
        if HARDCODED_CSV.exists():
            # 1. Generate unique run name and create the directory
            run_name = self.get_run_identifier()
            run_folder = OUTPUT_DIR / run_name
            run_folder.mkdir(parents=True, exist_ok=True)
            
            # 2. Define the new CSV path inside the created folder
            new_csv_path = run_folder / f"{run_name}_data.csv"
            
            # 3. Move the C++ output file into the folder
            shutil.move(str(HARDCODED_CSV), str(new_csv_path))
            
            # 4. Generate and save the JSON file in the same folder
            self.save_metadata(run_folder, run_name)
            
            print(f"[+] Run packaged successfully in: /outputs/{run_name}/\n")
        else:
            print("[-] Warning: Expected output CSV not found. Data packaging skipped.\n")

        # -------------------------------------------------
        # Output Parsing
        # -------------------------------------------------


        if result.stdout:

            for line in result.stdout.splitlines():

                if "Total deposited energy" in line:
                    print(line)

                elif "Number of events" in line:
                    print(line)

                elif "anti" in line:
                    print(line)

        # -------------------------------------------------
        # stderr
        # -------------------------------------------------

        if result.stderr:
            print(result.stderr)
