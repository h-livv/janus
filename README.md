# Janus

### A computational framework for studying how beamline and collision parameters affect high-energy particle transport and production.

Janus couples Geant4 particle-interaction simulations with Xsuite beam
transport, connecting stochastic particle production at a target to downstream
beam dynamics.

> **Status:** Not currently active. Janus grew out of an exploration of
> Geant4 particle production and Xsuite beam transport. I’m keeping the code
> and notes here in case I return to it.

## System

![Geant4 target bombardment in Janus](docs/assets/bombardment.png)

The case study considered 26 GeV proton bombardment of a high-Z target, with antiproton production as the primary observable.

```text
Geant4 (engines/geant4/, collision/)
        ↓
simulation.root (Seeds) + validation.root
        ↓
transport/config.json  →  Xsuite beamline
        ↓
particle tracking
        ↓
NPZ outputs / diagnostics  (data/transport/run_*/)
```

Geant4 supplies the stochastic interaction and production step. ROOT `Seeds` carry that particle data into transport. Xsuite tracks the beam. The resulting NPZ files and diagnostic plots serve as the primary observables.

## Components

| Component                          | Purpose                                                                  |
| ---------------------------------- | ------------------------------------------------------------------------ |
|Geant4          | Target bombardment and particle production                          |
| ROOT                | Structured collision and particle data                                    |
| Xsuite        | Beam transport and tracking                            |
| Janus     | Configuration, data transfer, orchestration, and analysis) |

Data contracts: [Architecture](docs/ARCHITECTURE.md). Physical models: [Physics](docs/PHYSICS.md).

### Validation

Collision and transport are checked separately. Janus does not revalidate Geant4 hadronic models or Xsuite element physics.

Collision Phases 1–3 test conservation laws on `validation.root`; Phase 4 plots distributions from both ROOT files. These scripts need `awkward` and `particle`, which are not all in `requirements.txt`. [Collision validation](docs/validation/collision_validation.md).

```bash
python collision/validation/validate.py
python collision/validation/physical_validation.py
```

Transport tests cover topology → construct → inherit → track → write. They use synthetic arrays or a small `Seeds` tree and do not need Geant4. [Transport validation](docs/validation/transport_validation.md).

```bash
pytest tests/transport/
```

### Reproducing the Pipeline

Collision needs a built Janus Geant4 engine ([installation](docs/guides/geant4_installation.md)). Transport needs a `data/collision/*/simulation.root` from a collision run. Transport tests need only `pip install -r requirements.txt`.

```bash
pip install -r requirements.txt

python collision/run.py      # → data/collision/<run>/
python transport/run.py      # topology: transport/config.json
pytest tests/transport/
```

- Collision: [`collision/config.json`](collision/config.json) — [guide](docs/guides/collision_guide.md)
- Transport: [`transport/config.json`](transport/config.json) — [guide](docs/guides/transport_guide.md)

Transport writes `data/transport/run_<timestamp>/` (`transported_particles.npz`, `topology.json`, diagnostic PNGs).


## Acknowledgements

Collision uses [Geant4](https://geant4.web.cern.ch/).

>- [Recent Developments in Geant4](https://doi.org/10.1016/j.nima.2016.06.125), J. Allison et al., Nucl. Instrum. Meth. A 835 (2016) 186–225
>- [Geant4 Developments and Applications](https://doi.org/10.1109/TNS.2006.869826), J. Allison et al., IEEE Trans. Nucl. Sci. 53 (2006) 270–278
>- [Geant4 — A Simulation Toolkit](https://doi.org/10.1016/S0168-9002%2803%2901368-8), S. Agostinelli et al., Nucl. Instrum. Meth. A 506 (2003) 250–303

Transport uses [Xsuite](https://xsuite.readthedocs.io/):

> G. Iadarola, R. De Maria, S. Łopaciuk, A. Abramov, X. Buffat, D. Demetriadou, L. Deniau, P. Hermes, P. Kicsiny, P. Kruyt, A. Latina, L. Mether, K. Paraschou, G. Sterbini, F. F. Van Der Veken, P. Belanger, P. Niedermayer, D. Di Croce, T. Pieloni, L. Van Riesen-Haupt, M. Seidel. [“Xsuite: An Integrated Beam Physics Simulation Framework,”](https://inspirehep.net/literature/2705250) JACoW HB2023 (2024), TUA2I1.

## Notes

Janus connects Geant4 output to Xsuite transport. The transport path has tests, while collision
validation is covered by scripts rather than a pytest suite. Running the full
pipeline also requires a separate Geant4 setup.
