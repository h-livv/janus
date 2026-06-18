from platform import node

import h5py
import numpy as np
from pathlib import Path
import sys

def merge_hdf5_files(input_files, output_file):
    if not input_files:
        return
        
    # Open the master file ONCE in write mode
    with h5py.File(output_file, 'w') as f_out:
        
        # Iterate through thread files one by one (Memory Isolation)
        for filepath in input_files:
            with h5py.File(filepath, 'r') as f_in:
                
                def stream_node(node, path=""):
                    if isinstance(node, h5py.Dataset):
                        if node.ndim == 0:
                            data = node[()] 
                        else:
                            data = node[:] 
        
                        if path not in f_out:
                            # 1. FIRST TIME SEEING THIS DATASET: Create it
                            if node.ndim == 0:
                                # It's a scalar (e.g., total entries or run ID)
                                f_out.create_dataset(path, data=data)
                            else:
                                # It's an array (Standard or Variable-Length)
                                # maxshape=(None,) allows us to resize it later!
                                max_shape = tuple([None] + list(node.shape[1:]))
                                f_out.create_dataset(
                                    path, 
                                    data=data, 
                                    maxshape=max_shape, 
                                    chunks=True, 
                                    dtype=node.dtype
                                )
                        else:
                            # 2. DATASET EXISTS: Append directly to disk
                            if node.ndim == 0:
                                # If scalar is numeric, sum it (e.g., total events)
                                if np.issubdtype(node.dtype, np.number):
                                    f_out[path][...] += data
                            else:
                                # Resize the disk dataset and drop the new data at the end
                                ds = f_out[path]
                                old_len = ds.shape[0]
                                ds.resize(old_len + data.shape[0], axis=0)
                                ds[old_len:] = data
                                
                    elif isinstance(node, h5py.Group):
                        for key in node:
                            new_path = f"{path}/{key}" if path else key
                            stream_node(node[key], new_path)
                            
                # Trigger the recursive streaming for this specific thread file
                stream_node(f_in)

if __name__ == "__main__":
    prefix = sys.argv[1]
    out_path = sys.argv[2]
    
    p = Path(prefix).parent
    name = Path(prefix).name
    files = list(p.glob(f"{name}_t*.hdf5"))
    if not files:
        files = list(p.glob(f"{name}.hdf5"))
        
    if files:
        merge_hdf5_files(files, out_path)
        for f in files:
            if str(f) != str(out_path):
                f.unlink() # Clean up thread files