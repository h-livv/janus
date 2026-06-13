/// \file SteppingAction.hh

#ifndef SteppingAction_h
#define SteppingAction_h 1

#include "G4UserSteppingAction.hh"
#include "globals.hh"

class G4LogicalVolume;
class G4GenericMessenger;

namespace janus
{

class EventAction;

class SteppingAction : public G4UserSteppingAction
{
  public:
    SteppingAction(EventAction* eventAction);
    ~SteppingAction() override;

    void UserSteppingAction(const G4Step*) override;

  private:
    EventAction* fEventAction = nullptr;
    G4LogicalVolume* fScoringVolume = nullptr;

    // --- Output Filtering & Tracking ---
    G4GenericMessenger* fMessenger = nullptr;
    G4int fFilterMode; 
    G4double fTrackingCut;

    G4bool fSaveSecondaries;
    G4String fRecordMode;
};

}

#endif