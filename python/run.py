from interface import Simulation

def main():
    sim = Simulation()
    is_interactive = sim.load_config()
    sim.run(interactive=is_interactive)

if __name__ == "__main__":
    main()