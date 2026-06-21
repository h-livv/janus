/// \file PrimaryGeneratorAction.cc
/// \brief Implementation of the janus::PrimaryGeneratorAction class

#include "PrimaryGeneratorAction.hh"
#include "PrimaryGeneratorMessenger.hh"

#include "G4Box.hh"
#include "G4LogicalVolume.hh"
#include "G4LogicalVolumeStore.hh"
#include "G4ParticleGun.hh"
#include "G4ParticleTable.hh"
#include "G4SystemOfUnits.hh"
#include "Randomize.hh"

namespace janus
{

PrimaryGeneratorAction::PrimaryGeneratorAction()
{
    G4int n_particle = 1;
    fParticleGun = new G4ParticleGun(n_particle);

    G4ParticleTable* particleTable = G4ParticleTable::GetParticleTable();
    G4ParticleDefinition* particle = particleTable->FindParticle("proton");
    fParticleGun->SetParticleDefinition(particle);

    // Initial Defaults
    fBeamRadius = 1.0 * mm;
    fBeamSigma = 0.5 * mm;
    fBeamDirection = G4ThreeVector(0., 0., 1.);
    fBeamOffset = G4ThreeVector(0., 0., 0.);
    fBeamProfile = "Flat"; // "Flat", "Gaussian", or "Point"
    
    fEnergyMean = 500. * GeV;
    fEnergySigma = 5. * GeV;
    fEnergyDist = "Mono"; // "Mono" or "Gaussian"

    fMessenger = new PrimaryGeneratorMessenger(this);
}

PrimaryGeneratorAction::~PrimaryGeneratorAction()
{
    delete fParticleGun;
    delete fMessenger;
}

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* event)
{
    G4double chamberSizeZ = 0;
    G4Box* chamberBox = nullptr;
    G4LogicalVolume* chamberLV = G4LogicalVolumeStore::GetInstance()->GetVolume("Chamber");

    if (chamberLV) {
        chamberBox = dynamic_cast<G4Box*>(chamberLV->GetSolid());
    }

    if (!chamberBox) {
        G4ExceptionDescription msg;
        msg << "Chamber geometry not found.\nBeam origin fallback activated.";
        G4Exception("PrimaryGeneratorAction::GeneratePrimaries()", "Janus001", JustWarning, msg);
    } else {
        chamberSizeZ = chamberBox->GetZHalfLength() * 2.;
    }

    // --- 1. Position & Profile ---
    G4double x0 = 0.;
    G4double y0 = 0.;
    G4double z0 = -0.5 * chamberSizeZ; // Base Z start

    if (fBeamProfile == "Flat") {
        G4double r = fBeamRadius * std::sqrt(G4UniformRand());
        G4double theta = CLHEP::twopi * G4UniformRand();
        x0 = r * std::cos(theta);
        y0 = r * std::sin(theta);
    } 
    else if (fBeamProfile == "Gaussian") {
        x0 = G4RandGauss::shoot(0., fBeamSigma);
        y0 = G4RandGauss::shoot(0., fBeamSigma);
    }
    // If "Point", x0 and y0 remain 0.

    // Apply User Offset
    x0 += fBeamOffset.x();
    y0 += fBeamOffset.y();
    z0 += fBeamOffset.z();

    fParticleGun->SetParticlePosition(G4ThreeVector(x0, y0, z0));

    // --- 2. Direction ---
    fParticleGun->SetParticleMomentumDirection(fBeamDirection);

    // --- 3. Energy Distribution ---
    G4double currentEnergy = fEnergyMean;
    if (fEnergyDist == "Gaussian") {
        currentEnergy = G4RandGauss::shoot(fEnergyMean, fEnergySigma);
        // Prevent negative energy
        if (currentEnergy < 0.) currentEnergy = 0.; 
    }
    
    fParticleGun->SetParticleEnergy(currentEnergy);

    // --- Generate ---
    fParticleGun->GeneratePrimaryVertex(event);
}

}