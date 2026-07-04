import cmd
from pathlib import Path
import subprocess
import sys
import json
from datetime import datetime, timedelta, timezone
import glob
import shutil

from matplotlib import interactive, lines

# =========================================================
# Paths
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENGINE_DIR = BASE_DIR.parent / "engine"
PROJECT_ROOT = BASE_DIR.parent

EXECUTABLE = ENGINE_DIR / "build" / "janus"
MACRO_PATH = ENGINE_DIR / "macros" / "run.mac"

HARDCODED_H5_VAL = PROJECT_ROOT / "temp" / "validation.root"
HARDCODED_H5_SIM = PROJECT_ROOT / "temp" / "simulation.root"

OUTPUT_DIR = BASE_DIR / "runs"


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
        
        #Direction & Offset
        self.direction = "0 0 1"
        self.offset = "0 0 -10 cm"
        
        # Energy
        self.energy_dist = "Mono"  # "Mono" or "Gaussian"
        self.energy_mean = "26 GeV"
        self.energy_sigma = "26 GeV" # Used if energy_dist is Gaussian
        
# =========================================================
# Environment Configuration
# =========================================================

class Environment:
    def __init__(self):
        # World / Chamber Settings
        self.world_material = "G4_Galactic"
        self.chamber_material = "G4_AIR"
        self.chamber_width = "40.0 cm"
        self.chamber_length = "120.0 cm"

        # Target Properties
        self.target_shape = "Cylinder"   # "Box", "Cylinder", or "Sphere"
        self.target_material = "G4_Ir"
        self.target_width = "3.0 mm"     # Acts as diameter for Cylinder
        self.target_length = "55.0 cm"   # The length of the target along Z
        self.target_position = "0 0 -27.5 cm"

# =========================================================
# Simulation Engine
# =========================================================

class Simulation:

    def __init__(self):

        self.beam = Beam()
        self.environment = Environment()
        
        self.output_filter = "Antimatter" #"All" or "Antimatter"
        self.drop_light_particles = True #True or False
        self.save_secondaries = False #True or False
        self.record_mode = "Birth" # "Birth", "Hit", or "Track"
        
        self.physics_list = "FTFP_BERT" # FTFP_BERT or QGSP_BIC
        self.production_cut = None #Dynamic or None
        self.tracking_cut = None #Dynamic or None
        self.seed = None #Dynamic or None
        self.threads = None # N-1 for safety
        
    # -----------------------------------------------------
    # Configuration Loader
    # -----------------------------------------------------
    def load_config(self, filepath=None):
        """Loads parameters from a JSON file and overrides defaults."""
        if filepath is None:
            filepath = BASE_DIR / "config.json"
        try:
            with open(filepath, "r") as f:
                config = json.load(f)
        except FileNotFoundError:
            print(f"[-] Warning: {filepath} not found. Using default parameters.")
            return False # Default to non-interactive if no config exists

        # Map Environment Settings
        if "environment" in config:
            env = config["environment"]
            self.environment.world_material = env.get("world_material", self.environment.world_material)
            self.environment.chamber_material = env.get("chamber_material", self.environment.chamber_material)
            self.environment.chamber_width = env.get("chamber_width", self.environment.chamber_width)
            self.environment.chamber_length = env.get("chamber_length", self.environment.chamber_length)
            self.environment.target_shape = env.get("target_shape", self.environment.target_shape)
            self.environment.target_material = env.get("target_material", self.environment.target_material)
            self.environment.target_width = env.get("target_width", self.environment.target_width)
            self.environment.target_length = env.get("target_length", self.environment.target_length)
            self.environment.target_position = env.get("target_position", self.environment.target_position)

        # Map Beam Settings
        if "beam" in config:
            beam = config["beam"]
            self.beam.particle = beam.get("particle", self.beam.particle)
            self.beam.count = beam.get("count", self.beam.count)
            self.beam.profile = beam.get("profile", self.beam.profile)
            self.beam.radius = beam.get("radius", self.beam.radius)
            self.beam.sigma = beam.get("sigma", self.beam.sigma)
            self.beam.direction = beam.get("direction", self.beam.direction)
            self.beam.offset = beam.get("offset", self.beam.offset)
            self.beam.energy_dist = beam.get("energy_dist", self.beam.energy_dist)
            self.beam.energy_mean = beam.get("energy_mean", self.beam.energy_mean)
            self.beam.energy_sigma = beam.get("energy_sigma", self.beam.energy_sigma)
            
        # Map Output Settings
        if "output" in config:
            output_cfg = config["output"]
            self.output_filter = output_cfg.get("filter", self.output_filter)
            self.drop_light_particles = output_cfg.get("drop_light_particles", self.drop_light_particles)
            self.save_secondaries = output_cfg.get("save_secondaries", self.save_secondaries)
            self.record_mode = output_cfg.get("record_mode", self.record_mode)
            
        # Map Run Settings
        run_settings = config.get("run_settings", {})
        self.physics_list = run_settings.get("physics_list", self.physics_list)
        self.production_cut = run_settings.get("production_cut", self.production_cut)
        self.tracking_cut = run_settings.get("tracking_cut", self.tracking_cut)
        self.seed = run_settings.get("seed", self.seed)
        self.threads = run_settings.get("threads", self.threads)

        # Return the interactive flag
        return run_settings.get("interactive", False)

    # -----------------------------------------------------
    # Macro Generation
    # -----------------------------------------------------

    def generate_macro(self, interactive=False):

        lines = [
            "/control/verbose 0",
            "/run/verbose 0",
            "/event/verbose 0",
            "/tracking/verbose 0",
            "/process/verbose 0",
            "/material/verbose 0",
            "/run/particle/verbose 0",
        ]

        # ---------------------------------------------
        # Seed Initialization
        # ---------------------------------------------
        # Geant4 requires random seeds to be set BEFORE initialization
        if self.seed is not None:
            lines.append(f"/random/setSeeds {self.seed} {self.seed}")

        # ---------------------------------------------
        # Environment & Geometry
        # ---------------------------------------------
        # Geometry must be defined BEFORE initialization
        lines.extend([
            f"/janus/det/setWorldMaterial {self.environment.world_material}",
            f"/janus/det/setChamberMaterial {self.environment.chamber_material}",
            f"/janus/det/setChamberWidth {self.environment.chamber_width}",
            f"/janus/det/setChamberLength {self.environment.chamber_length}",
            f"/janus/det/setTargetShape {self.environment.target_shape}",
            f"/janus/det/setTargetMaterial {self.environment.target_material}",
            f"/janus/det/setTargetWidth {self.environment.target_width}",
            f"/janus/det/setTargetLength {self.environment.target_length}",
            f"/janus/det/setTargetPosition {self.environment.target_position}",
            f"/janus/output/setFilter 1" if self.output_filter.lower() == "antimatter" else f"/janus/output/setFilter 0",
            f"/janus/output/setLightFilter 1" if self.drop_light_particles else f"/janus/output/setLightFilter 0",
        ])
        
        # Dynamic Thread Count
        if self.threads is not None:
            lines.append(f"/run/numberOfThreads {self.threads}")
            
        lines.append("/run/initialize")

        # ---------------------------------------------
        # Production & Tracking Cuts
        # ---------------------------------------------
        # Cuts MUST be applied AFTER initialization
        if self.production_cut is not None:
            lines.append(f"/run/setCut {self.production_cut}")
            
        if self.tracking_cut is not None:
            lines.append(f"/janus/tracking/setEnergyCut {self.tracking_cut}")
        
        lines.append(f"/janus/tracking/saveSecondaries {'true' if self.save_secondaries else 'false'}")
        lines.append(f"/janus/tracking/recordMode {self.record_mode}")

        # ---------------------------------------------
        # Beam Configuration
        # ---------------------------------------------
        lines.extend([
            f"/gun/particle {self.beam.particle}",
            f"/gun/beam/profile {self.beam.profile}"
        ])

        if self.beam.profile == "Flat":
            lines.append(f"/gun/beam/radius {self.beam.radius}")
        elif self.beam.profile == "Gaussian":
            lines.append(f"/gun/beam/sigma {self.beam.sigma}")

        lines.append(f"/gun/beam/direction {self.beam.direction}")
        lines.append(f"/gun/beam/offset {self.beam.offset}")
        lines.append(f"/gun/beam/energyDist {self.beam.energy_dist}")
        lines.append(f"/gun/beam/energyMean {self.beam.energy_mean}")
        
        if self.beam.energy_dist == "Gaussian":
            lines.append(f"/gun/beam/energySigma {self.beam.energy_sigma}")

        # -------------------------------------------------
        # Visualization
        # -------------------------------------------------
        if interactive:
            lines.extend([
                # --- Initial Setup ---
                "/vis/open OGL",
                "/vis/viewer/set/autoRefresh false",
                "/vis/verbose errors",
                "/vis/drawVolume",

                # --- Camera & Lights Setup ---
                "/vis/viewer/set/viewpointVector -1 0 0",
                "/vis/viewer/set/lightsVector -1 0 0",

                # --- Base Style Setup ---
                "/vis/viewer/set/style wireframe",
                "/vis/viewer/set/auxiliaryEdge true",
                "/vis/viewer/set/lineSegmentsPerCircle 100",

                # --- Trajectory Styling (Particle ID Upgrade) ---
                "/vis/scene/add/trajectories smooth",
                "/vis/modeling/trajectories/create/drawByParticleID",
                "/vis/modeling/trajectories/drawByParticleID-0/default/setDrawStepPts false",
                "/vis/modeling/trajectories/drawByParticleID-0/default/setLineWidth 1",
                
                # --- Paint the Antimatter ---
                "/vis/modeling/trajectories/drawByParticleID-0/set e+ magenta",       # Positrons glow Pink
                "/vis/modeling/trajectories/drawByParticleID-0/set anti_proton red",  # Antiprotons glow Red
                
                # --- Standard Shower Particles ---
                "/vis/modeling/trajectories/drawByParticleID-0/set proton blue",      # Primary Beam
                "/vis/modeling/trajectories/drawByParticleID-0/set e- cyan",          # Electrons
                "/vis/modeling/trajectories/drawByParticleID-0/set gamma gray",       # Gamma Rays
                "/vis/modeling/trajectories/drawByParticleID-0/set neutron green",   # Neutrons
                "/vis/modeling/trajectories/drawByParticleID-0/set pi+ yellow",        # Pions
                "/vis/modeling/trajectories/drawByParticleID-0/set pi- yellow",
                "/vis/modeling/trajectories/drawByParticleID-0/set pi0 white",
                
                # LIMIT TO 1000 EVENTS (Crash Prevention)
                "/vis/scene/endOfEventAction accumulate 1000",

                # --- Decorations ---
                "/vis/set/textColour green",
                "/vis/set/textLayout right",
                "/vis/scene/add/text2D 0.9 -.9 24 ! ! Janus",
                "/vis/set/textLayout",
                "/vis/set/textColour",
                "/vis/scene/add/eventID",

                # --- Specific Geometry Styling ---
                "/vis/geometry/set/visibility World 0 false",
                "/vis/geometry/set/colour Chamber 1 1 1 1 0.1",
                "/vis/geometry/set/colour Target 0.8 0.8 0.8 1.0",

                # --- Final Presentation ---
                "/vis/viewer/set/style surface",
                "/vis/viewer/set/hiddenMarker true",
                "/vis/viewer/set/viewpointThetaPhi 120 150",
                
                # --- Custom GUI Dropdown Menus ---
                "/gui/addMenu run Run",
                "/gui/addButton run \"Run 1 event\" \"/run/beamOn 1\"",
                "/gui/addButton run \"Run 10 events\" \"/run/beamOn 10\"",
                "/gui/addButton run \"Run 100 events\" \"/run/beamOn 100\"",
                "/gui/addButton run \"Run 1000 events\" \"/run/beamOn 1000\"",
                f"/gui/addButton run \"Run Configured Beam ({self.beam.count})\" \"/run/beamOn {self.beam.count}\"",
                "/gui/addButton run \"Clear Screen\" \"/vis/viewer/clear\"",

                # --- Refresh & Flush ---
                "/vis/viewer/set/autoRefresh true",
                "/vis/verbose warnings",
                "/vis/viewer/flush",
            ])
        else:
            # Batch Mode: No visualization, run the full count
            lines.append(f"/run/beamOn {self.beam.count}")
            
        return "\n".join(lines)

    # -----------------------------------------------------
    # Write Macro File
    # -----------------------------------------------------

    def write_macro(self, interactive=False):

        macro = self.generate_macro(interactive)

        with open(MACRO_PATH, "w") as f:
            f.write(macro)
            
    
    # -----------------------------------------------------
    # Data Packaging
    # -----------------------------------------------------

    def get_run_identifier(self):
        """Generates a descriptive folder name: 
           e.g., run_100k_proton_50GeV_Tungsten_20260613_0110"""
           
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        
        now_ist = datetime.now(ist_tz)
        timestamp = now_ist.strftime("%Y%m%d_%H%M")
        
        # 1. Format the count (e.g., 100000 -> 100k)
        count_val = int(self.beam.count)
        if count_val >= 1000000:
            count_str = f"{count_val // 1000000}M"
        elif count_val >= 1000:
            count_str = f"{count_val // 1000}k"
        else:
            count_str = str(count_val)
            
        # 2. Get energy string
        energy_str = self.beam.energy_mean.replace(" ", "")
        
        # 3. Get target material (stripping the "G4_" prefix for cleaner names)
        material = self.environment.target_material.replace("G4_", "")
        
        return f"run_{count_str}_{self.beam.particle}_{energy_str}_{material}_{timestamp}"
    
    def save_metadata(self, run_folder, run_name):
        """Creates the JSON configuration file."""
        
        ist_tz = timezone(timedelta(hours=5, minutes=30))
    
        now_ist = datetime.now(ist_tz)
        
        metadata = {
            "run_id": run_name,
            "timestamp": now_ist.isoformat(),
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
            },
            "environment": {
                "world_material": self.environment.world_material,
                "chamber_material": self.environment.chamber_material,
                "chamber_width": self.environment.chamber_width,
                "chamber_length": self.environment.chamber_length,
                "target_shape": self.environment.target_shape,
                "target_material": self.environment.target_material,
                "target_width": self.environment.target_width,
                "target_length": self.environment.target_length,
                "target_position": self.environment.target_position
            },
            "output settings": {
                "filter": self.output_filter,
                "drop_light_particles": self.drop_light_particles,
                "save_secondaries": self.save_secondaries,
                "record_mode": self.record_mode
            },
            "run_settings": {
                "physics_list": self.physics_list,
                "production_cut": self.production_cut,
                "tracking_cut": self.tracking_cut,
                "seed": self.seed,
                "threads": self.threads
            }
        }
        
        json_path = run_folder / f"{run_name}_config.json"
        with open(json_path, "w") as f:
            json.dump(metadata, f, indent=4)

    # -----------------------------------------------------
    # Run Simulation
    # -----------------------------------------------------

    
    def run(self, interactive=False):
        
        # --- Clean temp files from previous runs ---
        temp_dir = PROJECT_ROOT / "temp"
        if temp_dir.exists():
            for h5_file in temp_dir.glob("*.hdf5"):
                try:
                    h5_file.unlink()
                except OSError:
                    pass
        else:
            temp_dir.mkdir(parents=True, exist_ok=True)
            
        # 1. Write the macro, telling it whether to include Vis commands
        self.write_macro(interactive)
        
        cmd = [str(EXECUTABLE), str(MACRO_PATH), "--physics", self.physics_list]

        # --- INTERACTIVE MODE ---
        if interactive:
            print("\n========== JANUS INTERACTIVE MODE ==========")
            print(f"Physics List: {self.physics_list}")
            print("Launching Geant4 GUI...")
            
            cmd.append("--interactive")
            subprocess.run(cmd, cwd=ENGINE_DIR / "build")
            return

        # --- AUTOMATED MODE ---
        self.write_macro()

        print("\n========== JANUS SIMULATION ==========")
        print(f"Physics     : {self.physics_list}")
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
            cmd,
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
        
        def finalize_root_file(prefix, out_path):
            prefix = Path(prefix)
            p = prefix.parent
            name = prefix.name
            expected_merged_file = p / f"{name}.root"
            out_path = Path(out_path)
            
            if expected_merged_file.exists() and expected_merged_file != out_path:
                shutil.move(str(expected_merged_file), str(out_path))
            
            thread_files = list(p.glob(f"{name}_t*.root"))
            if thread_files:
                print(f"[-] Warning: Thread files {name}_t*.root exist. Geant4 native merging might have failed.")
                if not out_path.exists():
                    shutil.copy(str(thread_files[0]), str(out_path))

        finalize_root_file(PROJECT_ROOT / "temp" / "validation", HARDCODED_H5_VAL)
        finalize_root_file(PROJECT_ROOT / "temp" / "simulation", HARDCODED_H5_SIM)
        
        if HARDCODED_H5_VAL.exists() and HARDCODED_H5_SIM.exists():
            # 1. Generate unique run name and create the directory
            run_name = self.get_run_identifier()
            run_folder = OUTPUT_DIR / run_name
            run_folder.mkdir(parents=True, exist_ok=True)
            
            # 2. Define the new ROOT paths
            new_val_path = run_folder / "validation.root"
            new_sim_path = run_folder / "simulation.root"
            
            # 3. Move the C++ output files
            shutil.move(str(HARDCODED_H5_VAL), str(new_val_path))
            shutil.move(str(HARDCODED_H5_SIM), str(new_sim_path))
            
            # 4. Generate and save the JSON file
            self.save_metadata(run_folder, run_name)
            
            # 5. Run analyze.py to generate summary
            from . import analyze
            analyze.generate_summary(new_val_path, run_folder)
            
            print(f"[+] Run packaged successfully in: interactions/runs/{run_name}/\n")
        else:
            print("[-] Warning: Expected output ROOT files not found. Data packaging skipped.\n")

        # -------------------------------------------------
        # Output Parsing
        # -------------------------------------------------


        if result.stdout:

            for line in result.stdout.splitlines():

                if "Total deposited energy" in line:
                    print(line)

                elif "Number of events" in line:
                    print(line)

        # -------------------------------------------------
        # stderr
        # -------------------------------------------------

        if result.stderr:
            print(result.stderr)
            
# =========================================================
# Data Export as numpy arrays
# =========================================================

def get_validation_data(filepath):
    import uproot
    import awkward as ak
    import numpy as np
    
    data = {}
    with uproot.open(filepath) as f:
        # Check if the "Validation" tree exists
        if "Validation" in f:
            tree = f["Validation"]
            for key in tree.keys():
                branch = tree[key]
                # Try to use awkward library for jagged arrays and np for flat arrays
                arr = branch.array(library="ak")
                
                # If it's a jagged array of vectors, we can convert it to a list of numpy arrays
                # to maintain exact backward compatibility with h5py outputs
                if str(arr.type).startswith("var *"):
                    data[key] = [np.asarray(x) for x in arr]
                else:
                    data[key] = np.asarray(arr)
        else:
            print(f"[-] Warning: 'Validation' tree not found in {filepath}")
    return data

def get_simulation_data(filepath):
    import uproot
    import awkward as ak
    import numpy as np
    
    data = {}
    with uproot.open(filepath) as f:
        if "Seeds" in f:
            tree = f["Seeds"]
            for key in tree.keys():
                branch = tree[key]
                arr = branch.array(library="np")
                data[key] = np.asarray(arr)
        else:
            print(f"[-] Warning: 'Seeds' tree not found in {filepath}")
    return data
            
