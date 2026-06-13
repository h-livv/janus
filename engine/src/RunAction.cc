/// \file RunAction.cc
#include "RunAction.hh"
#include "PrimaryGeneratorAction.hh"

#include "G4ParticleGun.hh"
#include "G4AccumulableManager.hh"
#include "G4Run.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4UnitsTable.hh"

namespace janus
{

RunAction::RunAction()
: G4UserRunAction()
{
  // 1. Use Register (not RegisterAccumulable) to satisfy the compiler
  G4AccumulableManager* accumulableManager = G4AccumulableManager::Instance();
  accumulableManager->Register(fEdep);
}

// 2. REMOVED the ~RunAction() definition here because it is handled in the .hh file

void RunAction::BeginOfRunAction(const G4Run*)
{
  G4RunManager::GetRunManager()->SetRandomNumberStore(false);
  G4AccumulableManager::Instance()->Reset();
}

void RunAction::EndOfRunAction(const G4Run* run)
{
  G4int nofEvents = run->GetNumberOfEvent();
  if (nofEvents == 0) return;

  G4AccumulableManager* accumulableManager = G4AccumulableManager::Instance();
  accumulableManager->Merge();

  if (IsMaster()) 
  {
    G4double edep = fEdep.GetValue();

    const auto generatorAction =
        static_cast<const PrimaryGeneratorAction*>(
            G4RunManager::GetRunManager()->GetUserPrimaryGeneratorAction());

    G4String particleName = "Undefined";
    G4double energy = 0.0;

    if (generatorAction)
    {
      particleName = generatorAction->GetParticleGun()->GetParticleDefinition()->GetParticleName();
      energy = generatorAction->GetParticleGun()->GetParticleEnergy();
    }
  }
}

void RunAction::AddEdep(G4double edep)
{
  fEdep += edep;
}

} // end namespace janus