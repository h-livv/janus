/// \file PrimaryGeneratorAction.cc
/// \brief Implementation of the janus::PrimaryGeneratorAction class

#include "PrimaryGeneratorAction.hh"

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

  //Primary beam parameters
  G4ParticleTable* particleTable = G4ParticleTable::GetParticleTable();
  G4String particleName;
  G4ParticleDefinition* particle = particleTable->FindParticle(particleName = "proton");
  fParticleGun->SetParticleDefinition(particle);
  fParticleGun->SetParticleMomentumDirection(G4ThreeVector(0., 0., 1.));
  fParticleGun->SetParticleEnergy(500. * GeV);
}

PrimaryGeneratorAction::~PrimaryGeneratorAction()
{
  delete fParticleGun;
}

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* event)
{
  // this function is called at the begining of each event
  //

  // In order to avoid dependence of janusprimarygenerator
  // on janusdetectorconstr class we get chamber volume
  // from G4LogicalVolumeStore.

  G4double chamberSizeXY = 0;
  G4double chamberSizeZ = 0;

  G4Box* chamberBox = nullptr;

  G4LogicalVolume* chamberLV
    = G4LogicalVolumeStore::GetInstance()->GetVolume("Chamber");

if (chamberLV)
{
    chamberBox = dynamic_cast<G4Box*>(chamberLV->GetSolid());
}

if (!chamberBox)
{
    G4ExceptionDescription msg;
    msg << "Chamber geometry not found.\n";
    msg << "Beam origin fallback activated.";

    G4Exception(
        "PrimaryGeneratorAction::GeneratePrimaries()",
        "Janus001",
        JustWarning,
        msg
    );
}

if (chamberBox)
{
    chamberSizeXY = chamberBox->GetXHalfLength() * 2.;
    chamberSizeZ  = chamberBox->GetZHalfLength() * 2.;
}

  else {
    G4ExceptionDescription msg;
    msg << "Chamber geometry not found.\n";
    msg << "Beam origin fallback activated.\n";
    msg << "Primary particles will be generated at world center.";
    G4Exception("PrimaryGeneratorAction::GeneratePrimaries()", "MyCode0002", JustWarning, msg);
  }

// Beam spread radius

  G4double beamRadius = 1.0 * cm;

// Random position INSIDE detector-sized region

  G4double x0 =
    beamRadius * (2.0 * G4UniformRand() - 1.0);

  G4double y0 =
    beamRadius * (2.0 * G4UniformRand() - 1.0); 
    
  G4double z0 = -0.5 * chamberSizeZ + 1 * mm;

  fParticleGun->SetParticlePosition(G4ThreeVector(x0, y0, z0));

  fParticleGun->GeneratePrimaryVertex(event);
}

}
