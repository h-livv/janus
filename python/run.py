from interface import Simulation

def main():
    # 1. Initialize the Simulation
    sim = Simulation()

    # 2. Configure Basic Beam Settings
    sim.beam.particle = "proton"
    sim.beam.count = 100

    # 3. Configure Profile (e.g., Gaussian beam)
    sim.beam.profile = "Gaussian"     # "Flat", "Gaussian", or "Point"
    sim.beam.radius = "2 cm"
    sim.beam.sigma = "1 cm" # Used if profile is Gaussian

    # 4. Configure Geometry
    # Firing straight down the Z-axis, starting slightly back
    sim.beam.direction = "0 0 1"
    sim.beam.offset = "0 0 -10 cm"

    # 5. Configure Energy (e.g., Gaussian spread)
    sim.beam.energy_dist = "Mono"  # "Mono" or "Gaussian"
    sim.beam.energy_mean = "50 GeV"
    sim.beam.energy_sigma = "15 MeV" # Used if spread is Gaussian

    # 6. Execute Run
    sim.run()

if __name__ == "__main__":
    main()

#Modifiable parameters to implement:
'''
particle done
energy done
particle count done 
beam width done
beam position
beam dir
target material
target width
target position
target shape
chamber material
surrounding medium
physics_list
production_cut
step_limit
tracking_cut
seed
threads
output_path
save_tracks
save_hits
save_secondaries
enable_vis
trajectory_mode
trajectory_limit
camera_angle
detector_type
scoring_volume
energy_deposition
particle_flux
track_length
'''