/// \file SteppingAction.cc

#include "SteppingAction.hh"
#include "ActionInitialization.hh"
#include "DetectorConstruction.hh"
#include "EventAction.hh"
#include "ParticleRecord.hh"
#include "ParticleRecorder.hh"
#include "CsvWriter.hh"

#include "G4RunManager.hh"
#include "G4Step.hh"
#include "G4StepPoint.hh" // Added for boundary status
#include "G4Track.hh"
#include "G4VProcess.hh"
#include "G4ParticleDefinition.hh"

#include "G4GenericMessenger.hh"
#include "G4SystemOfUnits.hh"

namespace janus
{

static ParticleRecorder recorder;

// Initialize defaults: no tracking cut, save secondaries, only record births
SteppingAction::SteppingAction(EventAction* eventAction)
: fEventAction(eventAction), fTrackingCut(0.0), fSaveSecondaries(true), fRecordMode("Birth")
{
    fMessenger = new G4GenericMessenger(this, "/janus/tracking/", "Custom tracking control");
    fMessenger->DeclarePropertyWithUnit("setEnergyCut", "MeV", fTrackingCut, "Set minimum kinetic energy to track");
    
    // Add the new commands
    fMessenger->DeclareProperty("saveSecondaries", fSaveSecondaries, "Record secondary particles (true/false)");
    fMessenger->DeclareProperty("recordMode", fRecordMode, "Output mode: Birth, Track, or Hit");
}

SteppingAction::~SteppingAction()
{
    delete fMessenger;
}

void SteppingAction::UserSteppingAction(const G4Step* step)
{
    // =======================================================
    // 1. Energy Deposition Logic
    // =======================================================
    if (!fScoringVolume)
    {
        const auto detectorConstruction =
            static_cast<const DetectorConstruction*>(
                G4RunManager::GetRunManager()
                    ->GetUserDetectorConstruction()
            );

        fScoringVolume = detectorConstruction->GetScoringVolume();
    }

    G4LogicalVolume* volume =
        step->GetPreStepPoint()
            ->GetTouchableHandle()
            ->GetVolume()
            ->GetLogicalVolume();

    if (volume == fScoringVolume) 
    {
        G4double edep = step->GetTotalEnergyDeposit();
        fEventAction->AddEdep(edep);
    }

    // =======================================================
    // 2. High-Performance Particle Tracking Logic
    // =======================================================
    G4Track* track = step->GetTrack();

    // APPLY TRACKING CUT: Kill the particle if it falls below the dynamic threshold
    if (fTrackingCut > 0.0 && track->GetKineticEnergy() < fTrackingCut) 
    {
        track->SetTrackStatus(fStopAndKill);
    }

    // --- NEW: Secondary Check ---
    if (!fSaveSecondaries && track->GetParentID() > 0) return;

    // --- NEW: Record Mode Routing ---
    if (fRecordMode == "Birth") 
    {
        if (track->GetCurrentStepNumber() != 1) return;
    }
    else if (fRecordMode == "Hit") 
    {
        // Only record if inside the target/chamber
        if (volume != fScoringVolume) return;
        // Only record the exact step that crosses the boundary into the volume
        if (step->GetPreStepPoint()->GetStepStatus() != fGeomBoundary) return;
    }
    else if (fRecordMode == "Track") 
    {
        // Do nothing. Allow every single step to proceed to recording.
    }

    // Get the ultra-fast integer PDG code
    G4int pdgCode = track->GetDefinition()->GetPDGEncoding();

    // APPLY FILTER: Read the thread-safe global flag from ActionInitialization
    if (ActionInitialization::fFilterMode == 1) 
    {
        if (pdgCode >= 0) return;
        
        if (pdgCode == -11 || pdgCode == -211 || pdgCode == -13 || 
                pdgCode == 14  || pdgCode == -14 || pdgCode == -321) return; 
    }

    // =======================================================
    // 3. Record the Surviving Particle
    // =======================================================
    ParticleRecord record;

    record.eventID =
        G4RunManager::GetRunManager()
            ->GetCurrentEvent()
            ->GetEventID();

    record.trackID = track->GetTrackID();
    record.parentID = track->GetParentID();

    record.particleName = track->GetDefinition()->GetParticleName();

    record.kineticEnergy = track->GetKineticEnergy();
    record.position = track->GetPosition();
    record.globalTime = track->GetGlobalTime();

    if (track->GetCreatorProcess())
    {
        record.creatorProcess =
            track->GetCreatorProcess()->GetProcessName();
    }
    else
    {
        record.creatorProcess = "primary";
    }

    recorder.Record(record);
}

} // End of namespace janus