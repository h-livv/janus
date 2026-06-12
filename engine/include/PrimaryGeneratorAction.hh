/// \file PrimaryGeneratorAction.hh
/// \brief Definition of the janus::PrimaryGeneratorAction class

#ifndef B1PrimaryGeneratorAction_h
#define B1PrimaryGeneratorAction_h 1

#include "G4VUserPrimaryGeneratorAction.hh"
#include "globals.hh"
#include "G4ThreeVector.hh" // Added for 3Vectors

class G4ParticleGun;
class G4Event;
class G4Box;

namespace janus
{

class PrimaryGeneratorMessenger;

class PrimaryGeneratorAction : public G4VUserPrimaryGeneratorAction
{
  public:
    PrimaryGeneratorAction();
    ~PrimaryGeneratorAction() override;

    void GeneratePrimaries(G4Event*) override;

    const G4ParticleGun* GetParticleGun() const { return fParticleGun; }

    // Setters for UI commands
    void SetBeamRadius(G4double radius) { fBeamRadius = radius; }
    void SetBeamSigma(G4double sigma) { fBeamSigma = sigma; }
    void SetBeamDirection(G4ThreeVector dir) { fBeamDirection = dir.unit(); }
    void SetBeamOffset(G4ThreeVector offset) { fBeamOffset = offset; }
    void SetBeamProfile(G4String profile) { fBeamProfile = profile; }
    void SetEnergyMean(G4double mean) { fEnergyMean = mean; }
    void SetEnergySigma(G4double sigma) { fEnergySigma = sigma; }
    void SetEnergyDistribution(G4String dist) { fEnergyDist = dist; }

  private:
    G4ParticleGun* fParticleGun = nullptr;
    G4Box* fEnvelopeBox = nullptr;

    // Beam parameters
    G4double fBeamRadius;
    G4double fBeamSigma;
    G4ThreeVector fBeamDirection;
    G4ThreeVector fBeamOffset;
    G4String fBeamProfile;

    // Energy parameters
    G4double fEnergyMean;
    G4double fEnergySigma;
    G4String fEnergyDist;

    PrimaryGeneratorMessenger* fMessenger = nullptr;
};

}

#endif