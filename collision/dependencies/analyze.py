import uproot
import numpy as np
from pathlib import Path
from collections import Counter
from particle import Particle

def get_particle_name(pdg):
    try:
        part = Particle.from_pdgid(pdg)
        return part.name
    except Exception:
        return f"Unknown ({pdg})"

def generate_summary(val_root_path, output_dir):
    val_root_path = Path(val_root_path)
    output_dir = Path(output_dir)
    
    try:
        with uproot.open(val_root_path) as f:
            if "Validation" not in f:
                with open(output_dir / "particle_summary.txt", "w") as out:
                    out.write("Particle Generation Summary:\nError: Validation tree not found.\n")
                return
            
            tree = f["Validation"]
            if "outgoing_pdg" not in tree:
                with open(output_dir / "particle_summary.txt", "w") as out:
                    out.write("Particle Generation Summary:\nError: outgoing_pdg branch not found.\n")
                return
                
            pdg_data = tree["outgoing_pdg"].array(library="ak")
            
        counts = Counter()
        for val in pdg_data:
            if hasattr(val, '__iter__'):
                for p in val:
                    counts[p] += 1
            else:
                counts[val] += 1
                
        with open(output_dir / "particle_summary.txt", "w") as out:
            out.write("Particle Generation Summary:\n")
            
            named_counts = {}
            for pdg, count in counts.items():
                name = get_particle_name(pdg)
                named_counts[name] = named_counts.get(name, 0) + count
                
            for name, count in sorted(named_counts.items()):
                out.write(f"{name} = {count}\n")
                
    except Exception as e:
        with open(output_dir / "particle_summary.txt", "w") as out:
            out.write(f"Particle Generation Summary:\nError processing file: {str(e)}\n")
