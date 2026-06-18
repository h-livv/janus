#ifndef B1RunAction_h
#define B1RunAction_h 1

#include "G4UserRunAction.hh"
#include "G4Accumulable.hh"
#include "globals.hh"
#include <vector>

class G4Run;

namespace janus
{

class RunAction : public G4UserRunAction
{
  public:
    RunAction();
    ~RunAction() override = default;

    void BeginOfRunAction(const G4Run*) override;
    void EndOfRunAction(const G4Run*) override;

    void AddEdep(G4double edep);

    // Getters for the bound vectors
    std::vector<int>& GetOutgoingPdg() { return fOutgoingPdg; }
    std::vector<double>& GetOutgoingE() { return fOutgoingE; }
    std::vector<double>& GetOutgoingPx() { return fOutgoingPx; }
    std::vector<double>& GetOutgoingPy() { return fOutgoingPy; }
    std::vector<double>& GetOutgoingPz() { return fOutgoingPz; }

  private:
    G4Accumulable<G4double> fEdep = 0.;
    G4Accumulable<G4double> fEdep2 = 0.;

    std::vector<int> fOutgoingPdg;
    std::vector<double> fOutgoingE;
    std::vector<double> fOutgoingPx;
    std::vector<double> fOutgoingPy;
    std::vector<double> fOutgoingPz;
};

}

#endif
