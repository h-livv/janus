#ifndef B1EventAction_h
#define B1EventAction_h 1

#include "G4UserEventAction.hh"
#include "globals.hh"

class G4Event;

namespace janus
{

class RunAction;

class EventAction : public G4UserEventAction
{
  public:
    EventAction(RunAction* runAction);
    ~EventAction() override = default;

    void BeginOfEventAction(const G4Event* event) override;
    void EndOfEventAction(const G4Event* event) override;

    void AddEdep(G4double edep) { fEdep += edep; }

    void SetInteracted(bool val) { fInteracted = val; }
    bool GetInteracted() const { return fInteracted; }

    void ClearOutgoing();

    // Setters for primary info
    void SetPrimaryKinematics(G4double E, G4double px, G4double py, G4double pz) {
        fInitialE = E;
        fInitialPx = px;
        fInitialPy = py;
        fInitialPz = pz;
    }
    
    void SetBirthKinematics(G4int pdg, G4int q, G4int b, G4double E, G4double px, G4double py, G4double pz) {
        fBirthPdg = pdg;
        fBirthQ = q;
        fBirthB = b;
        fBirthE = E;
        fBirthPx = px;
        fBirthPy = py;
        fBirthPz = pz;
    }

    // Add outgoing secondary
    void AddOutgoingParticle(G4int pdg, G4double E, G4double px, G4double py, G4double pz);

  private:
    RunAction* fRunAction = nullptr;
    G4double fEdep = 0.;

    // Primary initial kinematics
    G4double fInitialE = 0.;
    G4double fInitialPx = 0.;
    G4double fInitialPy = 0.;
    G4double fInitialPz = 0.;
    
    G4double fBirthE = 0.;
    G4double fBirthPx = 0.;
    G4double fBirthPy = 0.;
    G4double fBirthPz = 0.;
    
    G4int fBirthPdg = 2212;
    G4int fBirthQ = 1;
    G4int fBirthB = 1;
    
    bool fInteracted = false;
};

}

#endif
