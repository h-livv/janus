#ifndef PARTICLE_RECORD_HH
#define PARTICLE_RECORD_HH

#include "globals.hh"
#include "G4ThreeVector.hh"

namespace janus
{

struct ParticleRecord
{
    G4int eventID;

    G4int trackID;
    G4int parentID;

    G4String particleName;
    G4String creatorProcess;

    G4double kineticEnergy;

    G4ThreeVector position;
    G4double globalTime;
};

}

#endif
