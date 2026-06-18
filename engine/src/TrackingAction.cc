#include "TrackingAction.hh"
#include "G4AnalysisManager.hh"
#include "G4Track.hh"
#include "G4Event.hh"
#include "G4RunManager.hh"
#include "EventAction.hh"
#include "G4VProcess.hh"
#include "G4NucleiProperties.hh"
#include "G4Ions.hh"

namespace janus
{

TrackingAction::TrackingAction() : G4UserTrackingAction() {}

void TrackingAction::PreUserTrackingAction(const G4Track* track)
{
    // Capture seeds at exactly step 0 / t=0
    if (track->GetCurrentStepNumber() == 0) {
    
#if 1
        auto analysisManager = G4AnalysisManager::Instance();
        
        G4int eventID = G4RunManager::GetRunManager()->GetCurrentEvent()->GetEventID();
        G4int trackID = track->GetTrackID();
        G4int pdgCode = track->GetDefinition()->GetPDGEncoding();
        
        G4ThreeVector pos = track->GetPosition();
        G4ThreeVector mom = track->GetMomentum();
        
        // Ntuple 1: "Seeds"
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

#endif
    }
    
    // Unfiltered Validation Capture (Ntuple 0 data)
    auto eventAction = const_cast<EventAction*>(
        static_cast<const EventAction*>(
            G4RunManager::GetRunManager()->GetUserEventAction()));
            
    if (eventAction) {
        // Only capture the true initial secondary cascade to avoid decay chain double counting
        // We only care about particles explicitly created by the first interaction!
        if (track->GetParentID() == 1 && track->GetCreatorProcess() != nullptr) {
            G4String procName = track->GetCreatorProcess()->GetProcessName();
            if (procName == "protonInelastic") {
                G4int pdgCode = track->GetDefinition()->GetPDGEncoding();
                G4double E = track->GetTotalEnergy();
                
                if (pdgCode > 1000000000) {
                    G4int Z = (pdgCode / 10000) % 1000;
                    G4int A = (pdgCode / 10) % 1000;
                    G4double nuclearMass = G4NucleiProperties::GetNuclearMass(A, Z);
                    G4double excitation = 0.0;
                    if (auto ion = dynamic_cast<const G4Ions*>(track->GetDefinition())) {
                        excitation = ion->GetExcitationEnergy();
                    }
                    E = nuclearMass + excitation + track->GetKineticEnergy();
                }

                G4ThreeVector mom = track->GetMomentum();
                eventAction->AddOutgoingParticle(pdgCode, E, mom.x(), mom.y(), mom.z());
            }
        }
    }
}

void TrackingAction::PostUserTrackingAction(const G4Track*)
{
    // Deliberately empty! The primary proton's final state is now handled
    // exactly at the interaction point in SteppingAction.cc
}

}
