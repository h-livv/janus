#ifndef PrimaryGeneratorMessenger_h
#define PrimaryGeneratorMessenger_h

#include "G4UImessenger.hh"

class G4UIcmdWithADoubleAndUnit;
class G4UIcmdWith3VectorAndUnit;
class G4UIcmdWith3Vector;
class G4UIcmdWithAString;
class G4UIdirectory;
class G4UIcommand;
class G4String;

namespace janus
{

class PrimaryGeneratorAction;

class PrimaryGeneratorMessenger : public G4UImessenger
{
  public:
    PrimaryGeneratorMessenger(PrimaryGeneratorAction* generator);
    ~PrimaryGeneratorMessenger() override;

    void SetNewValue(G4UIcommand* command, G4String newValue) override;

  private:
    PrimaryGeneratorAction* fGenerator;

    G4UIdirectory* fJanusDir;
    G4UIdirectory* fBeamDir;

    // Command pointers
    G4UIcmdWithADoubleAndUnit* fRadiusCmd;
    G4UIcmdWithADoubleAndUnit* fSigmaCmd;
    G4UIcmdWith3Vector* fDirectionCmd;
    G4UIcmdWith3VectorAndUnit* fOffsetCmd;
    G4UIcmdWithAString* fProfileCmd;
    
    G4UIcmdWithADoubleAndUnit* fEnergyMeanCmd;
    G4UIcmdWithADoubleAndUnit* fEnergySigmaCmd;
    G4UIcmdWithAString* fEnergyDistCmd;
};

}

#endif