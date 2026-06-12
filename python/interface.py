def Simulation(particle, energy, num, material):
    par = f"/gun/particle {particle}"
    ev = f"/gun/energy {energy}"
    num_par = f"/run/beamOn {num}"
    
    