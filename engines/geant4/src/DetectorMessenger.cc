#include "DetectorMessenger.hh"
#include "DetectorConstruction.hh"

#include "G4UIdirectory.hh"
#include "G4UIcmdWithAString.hh"
#include "G4UIcmdWithADoubleAndUnit.hh"
#include "G4UIcmdWith3VectorAndUnit.hh"
#include "G4UIcmdWithoutParameter.hh"

namespace janus
{

DetectorMessenger::DetectorMessenger(DetectorConstruction* det)
    : fDetectorConstruction(det)
{
    fJanusDir = new G4UIdirectory("/janus/");
    fJanusDir->SetGuidance("UI commands specific to Janus setup.");

    fDetDir = new G4UIdirectory("/janus/det/");
    fDetDir->SetGuidance("Detector construction control.");

    fWorldMatCmd = new G4UIcmdWithAString("/janus/det/setWorldMaterial", this);
    fWorldMatCmd->SetGuidance("Select material of the world.");

    fChamberMatCmd = new G4UIcmdWithAString("/janus/det/setChamberMaterial", this);
    fChamberMatCmd->SetGuidance("Select material of the chamber.");

    fChamberWidthCmd = new G4UIcmdWithADoubleAndUnit("/janus/det/setChamberWidth", this);
    fChamberWidthCmd->SetGuidance("Set the width/height of the chamber.");
    fChamberWidthCmd->SetUnitCategory("Length");

    fChamberLengthCmd = new G4UIcmdWithADoubleAndUnit("/janus/det/setChamberLength", this);
    fChamberLengthCmd->SetGuidance("Set the length (Z) of the chamber.");
    fChamberLengthCmd->SetUnitCategory("Length");

    fTargetMatCmd = new G4UIcmdWithAString("/janus/det/setTargetMaterial", this);
    fTargetMatCmd->SetGuidance("Select material of the target.");

    fTargetShapeCmd = new G4UIcmdWithAString("/janus/det/setTargetShape", this);
    fTargetShapeCmd->SetGuidance("Set the shape of the target (Box, Cylinder, Sphere).");
    fTargetShapeCmd->SetCandidates("Box Cylinder Sphere");

    fTargetWidthCmd = new G4UIcmdWithADoubleAndUnit("/janus/det/setTargetWidth", this);
    fTargetWidthCmd->SetGuidance("Set the width/diameter of the target.");
    fTargetWidthCmd->SetUnitCategory("Length");

    fTargetLengthCmd = new G4UIcmdWithADoubleAndUnit("/janus/det/setTargetLength", this);
    fTargetLengthCmd->SetGuidance("Set the length of the target.");
    fTargetLengthCmd->SetUnitCategory("Length");

    fTargetPosCmd = new G4UIcmdWith3VectorAndUnit("/janus/det/setTargetPosition", this);
    fTargetPosCmd->SetGuidance("Set target position inside the chamber.");
    fTargetPosCmd->SetUnitCategory("Length");

    fUpdateCmd = new G4UIcmdWithoutParameter("/janus/det/update", this);
    fUpdateCmd->SetGuidance("Update detector geometry.");
    fUpdateCmd->SetGuidance("This command MUST be applied before \"beamOn\" ");
    fUpdateCmd->SetGuidance("if you changed geometrical value(s).");
}

DetectorMessenger::~DetectorMessenger()
{
    delete fWorldMatCmd;
    delete fChamberMatCmd;
    delete fChamberWidthCmd;
    delete fChamberLengthCmd;
    delete fTargetMatCmd;
    delete fTargetShapeCmd;
    delete fTargetWidthCmd;
    delete fTargetLengthCmd;
    delete fTargetPosCmd;
    delete fUpdateCmd;
    delete fDetDir;
    delete fJanusDir;
}

void DetectorMessenger::SetNewValue(G4UIcommand* command, G4String newValue)
{
    if (command == fWorldMatCmd) {
        fDetectorConstruction->SetWorldMaterial(newValue);
    } else if (command == fChamberMatCmd) {
        fDetectorConstruction->SetChamberMaterial(newValue);
    } else if (command == fChamberWidthCmd) {
        fDetectorConstruction->SetChamberWidth(fChamberWidthCmd->GetNewDoubleValue(newValue));
    } else if (command == fChamberLengthCmd) {
        fDetectorConstruction->SetChamberLength(fChamberLengthCmd->GetNewDoubleValue(newValue));
    } else if (command == fTargetMatCmd) {
        fDetectorConstruction->SetTargetMaterial(newValue);
    } else if (command == fTargetShapeCmd) {
        fDetectorConstruction->SetTargetShape(newValue);
    } else if (command == fTargetWidthCmd) {
        fDetectorConstruction->SetTargetWidth(fTargetWidthCmd->GetNewDoubleValue(newValue));
    } else if (command == fTargetLengthCmd) {
        fDetectorConstruction->SetTargetLength(fTargetLengthCmd->GetNewDoubleValue(newValue));
    } else if (command == fTargetPosCmd) {
        fDetectorConstruction->SetTargetPosition(fTargetPosCmd->GetNew3VectorValue(newValue));
    } else if (command == fUpdateCmd) {
        fDetectorConstruction->UpdateGeometry();
    }
}

}