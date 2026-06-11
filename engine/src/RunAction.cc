/// \file RunAction.cc
/// \brief Implementation of the janus::RunAction class

#include "RunAction.hh"

#include "PrimaryGeneratorAction.hh"

#include "G4AccumulableManager.hh"
#include "G4ParticleDefinition.hh"
#include "G4ParticleGun.hh"
#include "G4Run.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4UnitsTable.hh"

namespace janus
{

RunAction::RunAction()
{
  // Register accumulable to the accumulable manager
  G4AccumulableManager* accumulableManager =
      G4AccumulableManager::Instance();

  accumulableManager->Register(fEdep);
}

void RunAction::BeginOfRunAction(const G4Run*)
{
  // Disable random seed storage
  G4RunManager::GetRunManager()->SetRandomNumberStore(false);

  // Reset accumulables
  G4AccumulableManager* accumulableManager =
      G4AccumulableManager::Instance();

  accumulableManager->Reset();
}

void RunAction::EndOfRunAction(const G4Run* run)
{
  G4int nofEvents = run->GetNumberOfEvent();

  if (nofEvents == 0) return;

  // Merge accumulables
  G4AccumulableManager* accumulableManager =
      G4AccumulableManager::Instance();

  accumulableManager->Merge();

  // Total deposited energy
  G4double edep = fEdep.GetValue();

  // Run conditions
  const auto generatorAction =
      static_cast<const PrimaryGeneratorAction*>(
          G4RunManager::GetRunManager()
              ->GetUserPrimaryGeneratorAction());

  G4String runCondition;

  if (generatorAction)
  {
    const G4ParticleGun* particleGun =
        generatorAction->GetParticleGun();

    runCondition +=
        particleGun->GetParticleDefinition()->GetParticleName();

    runCondition += " of ";

    G4double particleEnergy =
        particleGun->GetParticleEnergy();

    runCondition +=
        G4BestUnit(particleEnergy, "Energy");
  }

  // Print summary
  if (IsMaster())
  {
    G4cout << G4endl
           << "-------------------- End of Global Run --------------------";
  }
  else
  {
    G4cout << G4endl
           << "-------------------- End of Local Run ---------------------";
  }

  G4cout << G4endl
         << " Number of events: "
         << nofEvents
         << " | "
         << runCondition
         << G4endl
         << G4endl;

  G4cout << " Total deposited energy = "
         << G4BestUnit(edep, "Energy")
         << " ("
         << edep / joule
         << " J)"
         << G4endl;

  G4cout << "-----------------------------------------------------------"
         << G4endl
         << G4endl;
}

void RunAction::AddEdep(G4double edep)
{
    fEdep += edep;
}

}