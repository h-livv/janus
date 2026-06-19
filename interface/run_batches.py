import time
from pathlib import Path
from dependencies.interface import Simulation

def run_production_batches():
    # Define your validation suite
    # Each dictionary here will override the defaults in config.json
    suite = [
        {
            "name": "Validation_W_Full", 
            "env": {"target_material": "G4_W", "target_position": "0 0 0 cm"}, 
            "out": {"filter": "All", "drop_light_particles": False}
        },
        {
            "name": "Validation_Pb_Full", 
            "env": {"target_material": "G4_Pb", "target_position": "0 0 0 cm"}, 
            "out": {"filter": "All", "drop_light_particles": False}
        },
        {
            "name": "Production_W_Rare", 
            "env": {"target_material": "G4_W", "target_position": "0 0 0 cm"}, 
            "out": {"filter": "Antimatter", "drop_light_particles": True}
        },
        {
            "name": "Geometry_Shift_W", 
            "env": {"target_material": "G4_W", "target_position": "0 0 -2 cm"}, 
            "out": {"filter": "Antimatter", "drop_light_particles": True}
        }
    ]

    events_per_batch = 1000000 # 1 Million per batch

    print(f"[*] Starting Validation Suite: {len(suite)} batches.")
    
    for config_override in suite:
        print(f"\n{'='*20} RUNNING: {config_override['name']} {'='*20}")
        
        sim = Simulation()
        # Load baseline
        sim.load_config("config.json")
        
        # Apply overrides
        sim.environment.target_material = config_override["env"]["target_material"]
        sim.environment.target_position = config_override["env"]["target_position"]
        sim.output_filter = config_override["out"]["filter"]
        sim.drop_light_particles = config_override["out"]["drop_light_particles"]
        sim.beam.count = events_per_batch
        
        # Execute
        sim.run(interactive=False)
        
        print(f"{'='*20} {config_override['name']} COMPLETE {'='*20}")
        time.sleep(5)

if __name__ == "__main__":
    run_production_batches()