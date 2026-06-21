#include "SteppingAction.hh"
#include "G4Step.hh"
#include "G4Track.hh"
#include "G4VProcess.hh"
#include "EventAction.hh"
#include "ActionInitialization.hh"
#include "G4IonTable.hh"
#include "G4SystemOfUnits.hh"
#include "G4GenericMessenger.hh"
#include "G4NucleiProperties.hh"
#include "G4AnalysisManager.hh"
#include "G4RunManager.hh"
#include "G4Event.hh"

namespace janus
{

SteppingAction::SteppingAction(EventAction* eventAction)
  : G4UserSteppingAction(),
    fEventAction(eventAction), fTrackingCut(0.0), fSaveSecondaries(true), fRecordMode("Birth")
{
    fMessenger = new G4GenericMessenger(this, "/janus/tracking/", "Custom tracking control");
    fMessenger->DeclarePropertyWithUnit("setEnergyCut", "MeV", fTrackingCut, "Set minimum kinetic energy to track");
    fMessenger->DeclareProperty("saveSecondaries", fSaveSecondaries, "Record secondary particles");
    fMessenger->DeclareProperty("recordMode", fRecordMode, "Output mode: Birth, Track, or Hit");
}

SteppingAction::~SteppingAction()
{
    delete fMessenger;
}

void SteppingAction::UserSteppingAction(const G4Step* step)
{
    G4Track* track = step->GetTrack();
    
    // Retrieve logical volume safely
    G4LogicalVolume* volume = nullptr;
    if (track->GetVolume() && track->GetVolume()->GetLogicalVolume()) {
        volume = track->GetVolume()->GetLogicalVolume();
    }

    if (!fScoringVolume && volume) 
    {
        if (volume->GetName() == "Detector") fScoringVolume = volume;
    }

    if (volume == fScoringVolume) 
    {
        G4double edep = step->GetTotalEnergyDeposit();
        fEventAction->AddEdep(edep);
    }

    if (fTrackingCut > 0.0 && track->GetKineticEnergy() < fTrackingCut) 
    {
        track->SetTrackStatus(fStopAndKill);
    }

    // --- Boundary Capture for "Hit" Mode ---
    if (fRecordMode == "Hit") {
        auto prePoint = step->GetPreStepPoint();
        auto postPoint = step->GetPostStepPoint();
        
        if (prePoint && postPoint && 
            prePoint->GetPhysicalVolume() && postPoint->GetPhysicalVolume()) 
        {
            if (prePoint->GetPhysicalVolume()->GetName() == "Target" &&
                postPoint->GetPhysicalVolume()->GetName() == "Chamber") 
            {
                auto analysisManager = G4AnalysisManager::Instance();
                
                G4int eventID = G4RunManager::GetRunManager()->GetCurrentEvent()->GetEventID();
                G4int trackID = track->GetTrackID();
                G4int pdgCode = track->GetDefinition()->GetPDGEncoding();
                
                // We want the kinematics exactly at the boundary crossing!
                // The PostStepPoint represents the exact boundary intersection geometry
                G4ThreeVector pos = postPoint->GetPosition();
                G4ThreeVector mom = postPoint->GetMomentum();
                
                analysisManager->FillNtupleIColumn(1, 0, eventID);
                analysisManager->FillNtupleIColumn(1, 1, trackID);
                analysisManager->FillNtupleIColumn(1, 2, pdgCode);
                analysisManager->FillNtupleDColumn(1, 3, pos.x());
                analysisManager->FillNtupleDColumn(1, 4, pos.y());
                analysisManager->FillNtupleDColumn(1, 5, pos.z());
                analysisManager->FillNtupleDColumn(1, 6, mom.x());
                analysisManager->FillNtupleDColumn(1, 7, mom.y());
                analysisManager->FillNtupleDColumn(1, 8, mom.z());
                
                analysisManager->AddNtupleRow(1);
            }
        }
    }

    // --- Primary particle kinematics for Validation ---
    if (track->GetTrackID() == 1) {
        if (step->GetPostStepPoint() && step->GetPostStepPoint()->GetProcessDefinedStep()) {
            G4String procName = step->GetPostStepPoint()->GetProcessDefinedStep()->GetProcessName();
            if (procName == "protonInelastic") {
                // Wipe everything captured before this exact moment!
                fEventAction->ClearOutgoing();
                
                G4double E = step->GetPreStepPoint()->GetTotalEnergy();
                G4ThreeVector mom = step->GetPreStepPoint()->GetMomentum();
                fEventAction->SetPrimaryKinematics(E, mom.x(), mom.y(), mom.z());
                fEventAction->SetInteracted(true);
            }
        }
        
        if (track->GetCurrentStepNumber() == 1 && track->GetParentID() == 0) {
            G4int pdg = track->GetDefinition()->GetPDGEncoding();
            G4int q = std::round(track->GetDefinition()->GetPDGCharge() / CLHEP::eplus);
            G4int b = track->GetDefinition()->GetBaryonNumber();
            G4double E = track->GetTotalEnergy();
            G4ThreeVector mom = track->GetMomentum();
            fEventAction->SetBirthKinematics(pdg, q, b, E, mom.x(), mom.y(), mom.z());
        }
    }
}

}