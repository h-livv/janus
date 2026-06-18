import h5py
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

def generate_summary(val_h5_path, output_dir):
    val_h5_path = Path(val_h5_path)
    output_dir = Path(output_dir)
    
    try:
        with h5py.File(val_h5_path, 'r') as f:
            def find_dataset(name, node):
                if isinstance(node, h5py.Dataset) and (name in node.name):
                    return node
                elif isinstance(node, h5py.Group):
                    for key in node:
                        res = find_dataset(name, node[key])
                        if res is not None:
                            return res
                return None
            
            pdg_ds = find_dataset("outgoing_pdg/pages", f)
            if pdg_ds is None:
                # Fallback to older Geant4 HDF5 format
                pdg_ds = find_dataset("outgoing_pdg", f)
                
            if pdg_ds is None:
                with open(output_dir / "particle_summary.txt", "w") as out:
                    out.write("Particle Generation Summary:\nError: outgoing_pdg dataset not found.\n")
                return
                
            pdg_data = pdg_ds[:]
            
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
