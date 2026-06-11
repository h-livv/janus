#include "SteppingAction.hh"

#include "DetectorConstruction.hh"
#include "EventAction.hh"

#include "ParticleRecord.hh"
#include "ParticleRecorder.hh"
#include "CsvWriter.hh"

#include "G4RunManager.hh"
#include "G4Step.hh"
#include "G4Track.hh"
#include "G4VProcess.hh"

namespace janus
{

static ParticleRecorder recorder;

SteppingAction::SteppingAction(
    EventAction* eventAction
)
: fEventAction(eventAction)
{}

void SteppingAction::UserSteppingAction(const G4Step* step)
{
    // Original energy deposition logic

    if (!fScoringVolume)
    {
        const auto detectorConstruction =
            static_cast<const DetectorConstruction*>(
                G4RunManager::GetRunManager()
                    ->GetUserDetectorConstruction()
            );

        fScoringVolume =
            detectorConstruction->GetScoringVolume();
    }

    G4LogicalVolume* volume =
        step->GetPreStepPoint()
            ->GetTouchableHandle()
            ->GetVolume()
            ->GetLogicalVolume();

    if (volume != fScoringVolume) return;

    G4double edep = step->GetTotalEnergyDeposit();

    fEventAction->AddEdep(edep);

    // Particle tracking logic

    const G4Track* track = step->GetTrack();

    G4String particleName =
        track->GetDefinition()->GetParticleName();

    if (
        particleName.find("anti") != std::string::npos &&
        track->GetCurrentStepNumber() == 1
    )
    {
        ParticleRecord record;

        record.eventID =
            G4RunManager::GetRunManager()
                ->GetCurrentEvent()
                ->GetEventID();

        record.trackID =
            track->GetTrackID();

        record.parentID =
            track->GetParentID();

        record.particleName =
            particleName;

        record.kineticEnergy =
            track->GetKineticEnergy();

        record.position =
            track->GetPosition();

        record.globalTime =
            track->GetGlobalTime();

        if (track->GetCreatorProcess())
        {
            record.creatorProcess =
                track->GetCreatorProcess()
                    ->GetProcessName();
        }
        else
        {
            record.creatorProcess = "primary";
        }

        recorder.Record(record);
    }
}

}
