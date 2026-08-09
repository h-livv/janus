#include "EventAction.hh"
#include "RunAction.hh"
#include "G4AnalysisManager.hh"
#include "G4Event.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4NucleiProperties.hh"
#include "G4ParticleTable.hh"
#include "G4LogicalVolumeStore.hh"
#include "G4LogicalVolume.hh"
#include "G4Material.hh"

namespace janus
{

EventAction::EventAction(RunAction* runAction) : fRunAction(runAction) {}

void EventAction::BeginOfEventAction(const G4Event*)
{
  fEdep = 0.;
  
  fInitialE = 0.;
  fInitialPx = 0.;
  fInitialPy = 0.;
  fInitialPz = 0.;

  fRunAction->GetOutgoingPdg().clear();
  fRunAction->GetOutgoingE().clear();
  fRunAction->GetOutgoingPx().clear();
  fRunAction->GetOutgoingPy().clear();
  fRunAction->GetOutgoingPz().clear();
  
  fInteracted = false;
}

void EventAction::AddOutgoingParticle(G4int pdg, G4double E, G4double px, G4double py, G4double pz)
{
  fRunAction->GetOutgoingPdg().push_back(pdg);
  fRunAction->GetOutgoingE().push_back(E);
  fRunAction->GetOutgoingPx().push_back(px);
  fRunAction->GetOutgoingPy().push_back(py);
  fRunAction->GetOutgoingPz().push_back(pz);
}

void EventAction::ClearOutgoing()
{
  fRunAction->GetOutgoingPdg().clear();
  fRunAction->GetOutgoingE().clear();
  fRunAction->GetOutgoingPx().clear();
  fRunAction->GetOutgoingPy().clear();
  fRunAction->GetOutgoingPz().clear();
}

void EventAction::EndOfEventAction(const G4Event* event)
{
  fRunAction->AddEdep(fEdep);

  G4int targetZ = 74;
  G4int targetA = 184;
  auto lv = G4LogicalVolumeStore::GetInstance()->GetVolume("Target");
  if (lv) {
      auto mat = lv->GetMaterial();
      auto elements = mat->GetElementVector();
      if (elements && elements->size() > 0) {
          targetZ = std::round((*elements)[0]->GetZ());
          targetA = std::round((*elements)[0]->GetA() * CLHEP::mole / CLHEP::g);
      }
  }

  auto& pdgs = fRunAction->GetOutgoingPdg();
  if (fInteracted && pdgs.size() == 0) {
      fInteracted = false;
  }

  if (!fInteracted) {
      ClearOutgoing();
      AddOutgoingParticle(fBirthPdg, fBirthE, fBirthPx, fBirthPy, fBirthPz);
      G4double targetMass = G4NucleiProperties::GetNuclearMass(targetA, targetZ);
      fInitialE = fBirthE + targetMass;
      fInitialPx = fBirthPx; fInitialPy = fBirthPy; fInitialPz = fBirthPz;
      AddOutgoingParticle(1000000000 + targetZ * 10000 + targetA * 10, targetMass, 0.0, 0.0, 0.0);
  } else {
      G4double sumE = 0.0, sumPx = 0.0, sumPy = 0.0, sumPz = 0.0;
      G4int maxMass = -1;
      G4int targetIndex = -1;
      
      G4int sumQ = 0;
      G4int sumB = 0;
      
      auto& Es = fRunAction->GetOutgoingE();
      auto& pxs = fRunAction->GetOutgoingPx();
      auto& pys = fRunAction->GetOutgoingPy();
      auto& pzs = fRunAction->GetOutgoingPz();
      
      for (size_t i = 0; i < pdgs.size(); ++i) {
          sumE += Es[i];
          sumPx += pxs[i];
          sumPy += pys[i];
          sumPz += pzs[i];
          
          if (pdgs[i] > 1000000000) {
              sumQ += (pdgs[i] / 10000) % 1000;
              sumB += (pdgs[i] / 10) % 1000;
              G4int A = (pdgs[i] / 10) % 1000;
              if (A > maxMass) {
                  maxMass = A;
                  targetIndex = i;
              }
          } else {
              G4ParticleDefinition* def = G4ParticleTable::GetParticleTable()->FindParticle(pdgs[i]);
              if (def) {
                  sumQ += std::round(def->GetPDGCharge() / CLHEP::eplus);
                  sumB += def->GetBaryonNumber();
              }
          }
      }
      
      targetZ = sumQ - fBirthQ;
      targetA = sumB - fBirthB;
      
      G4double targetMass = G4NucleiProperties::GetNuclearMass(targetA, targetZ);
      fInitialE += targetMass; // fInitialE already holds the pre-step collision energy
      
      if (targetIndex >= 0) {
          Es[targetIndex] += (fInitialE - sumE);
          pxs[targetIndex] += (fInitialPx - sumPx);
          pys[targetIndex] += (fInitialPy - sumPy);
          pzs[targetIndex] += (fInitialPz - sumPz);
      }
  }

  auto analysisManager = G4AnalysisManager::Instance();
  
  G4int numParticles = fRunAction->GetOutgoingPdg().size();

  // Ntuple 0: "Validation"
  analysisManager->FillNtupleIColumn(0, 0, event->GetEventID());
  analysisManager->FillNtupleDColumn(0, 1, fInitialE);
  analysisManager->FillNtupleDColumn(0, 2, fInitialPx);
  analysisManager->FillNtupleDColumn(0, 3, fInitialPy);
  analysisManager->FillNtupleDColumn(0, 4, fInitialPz);
  analysisManager->FillNtupleIColumn(0, 5, targetZ);
  analysisManager->FillNtupleIColumn(0, 6, targetA);
  analysisManager->FillNtupleIColumn(0, 7, fBirthPdg);
  analysisManager->FillNtupleIColumn(0, 8, numParticles);
  // Vectors are automatically written when AddNtupleRow is called since they are bound

  analysisManager->AddNtupleRow(0);
}

}
