#include "RunAction.hh"
#include "PrimaryGeneratorAction.hh"

#include "G4ParticleGun.hh"
#include "G4AccumulableManager.hh"
#include "G4Run.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4UnitsTable.hh"
#include "G4AnalysisManager.hh"

namespace janus
{

RunAction::RunAction()
: G4UserRunAction()
{
  G4AccumulableManager* accumulableManager = G4AccumulableManager::Instance();
  accumulableManager->Register(fEdep);
  
  auto analysisManager = G4AnalysisManager::Instance();
  analysisManager->SetDefaultFileType("root");
  analysisManager->SetNtupleMerging(true);
  analysisManager->SetFileName("janus_data");

  // Ntuple 0: "Validation"
  analysisManager->CreateNtuple("Validation", "Event-by-event kinematics");
  analysisManager->CreateNtupleIColumn(0, "event_id");
  analysisManager->CreateNtupleDColumn(0, "initial_E");
  analysisManager->CreateNtupleDColumn(0, "initial_px");
  analysisManager->CreateNtupleDColumn(0, "initial_py");
  analysisManager->CreateNtupleDColumn(0, "initial_pz");
  analysisManager->CreateNtupleIColumn(0, "target_Z");
  analysisManager->CreateNtupleIColumn(0, "target_A");
  analysisManager->CreateNtupleIColumn(0, "beam_pdg");
  analysisManager->CreateNtupleIColumn(0, "num_particles");
  analysisManager->CreateNtupleIColumn(0, "outgoing_pdg", fOutgoingPdg);
  analysisManager->CreateNtupleDColumn(0, "outgoing_E", fOutgoingE);
  analysisManager->CreateNtupleDColumn(0, "outgoing_px", fOutgoingPx);
  analysisManager->CreateNtupleDColumn(0, "outgoing_py", fOutgoingPy);
  analysisManager->CreateNtupleDColumn(0, "outgoing_pz", fOutgoingPz);
  analysisManager->FinishNtuple(0);
  analysisManager->SetNtupleFileName(0, "../../temp/validation");

#if 1

  // Ntuple 1: "Seeds"
  analysisManager->CreateNtuple("Seeds", "t=0 Track initializations");
  analysisManager->CreateNtupleIColumn(1, "event_id");
  analysisManager->CreateNtupleIColumn(1, "track_id");
  analysisManager->CreateNtupleIColumn(1, "pdg_code");
  analysisManager->CreateNtupleDColumn(1, "start_x");
  analysisManager->CreateNtupleDColumn(1, "start_y");
  analysisManager->CreateNtupleDColumn(1, "start_z");
  analysisManager->CreateNtupleDColumn(1, "start_px");
  analysisManager->CreateNtupleDColumn(1, "start_py");
  analysisManager->CreateNtupleDColumn(1, "start_pz");
  analysisManager->FinishNtuple(1);
  analysisManager->SetNtupleFileName(1, "../../temp/simulation");

#endif
}

void RunAction::BeginOfRunAction(const G4Run*)
{
  G4RunManager::GetRunManager()->SetRandomNumberStore(false);
  G4AccumulableManager::Instance()->Reset();

  auto analysisManager = G4AnalysisManager::Instance();
  analysisManager->OpenFile();
}

void RunAction::EndOfRunAction(const G4Run* run)
{
  G4int nofEvents = run->GetNumberOfEvent();
  if (nofEvents == 0) return;

  G4AccumulableManager* accumulableManager = G4AccumulableManager::Instance();
  accumulableManager->Merge();

  auto analysisManager = G4AnalysisManager::Instance();
  analysisManager->Write();
  analysisManager->CloseFile();
}

void RunAction::AddEdep(G4double edep)
{
  fEdep += edep;
}

}