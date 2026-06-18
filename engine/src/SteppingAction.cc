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