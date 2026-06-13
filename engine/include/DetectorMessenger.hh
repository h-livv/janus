#ifndef DetectorMessenger_h
#define DetectorMessenger_h 1

#include "G4UImessenger.hh"
#include "globals.hh"

class G4UIdirectory;
class G4UIcmdWithAString;
class G4UIcmdWithADoubleAndUnit;
class G4UIcmdWith3VectorAndUnit;
class G4UIcmdWithoutParameter;

namespace janus
{

class DetectorConstruction;

class DetectorMessenger : public G4UImessenger
{
  public:
    DetectorMessenger(DetectorConstruction* det);
    ~DetectorMessenger() override;

    void SetNewValue(G4UIcommand* command, G4String newValue) override;

  private:
    DetectorConstruction* fDetectorConstruction;

    G4UIdirectory* fJanusDir;
    G4UIdirectory* fDetDir;

    G4UIcmdWithAString* fWorldMatCmd;
    G4UIcmdWithAString* fChamberMatCmd;
    G4UIcmdWithAString* fTargetMatCmd;
    G4UIcmdWithAString* fTargetShapeCmd;
    G4UIcmdWithADoubleAndUnit* fTargetWidthCmd;
    G4UIcmdWith3VectorAndUnit* fTargetPosCmd;
    G4UIcmdWithoutParameter* fUpdateCmd;
};

}

#endif