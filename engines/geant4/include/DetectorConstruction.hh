/// \file DetectorConstruction.hh
/// \brief Definition of the janus::DetectorConstruction class

#ifndef DetectorConstruction_h
#define DetectorConstruction_h 1

#include "G4VUserDetectorConstruction.hh"
#include "globals.hh"
#include "G4ThreeVector.hh"

class G4VPhysicalVolume;
class G4LogicalVolume;

namespace janus
{

class DetectorMessenger;

class DetectorConstruction : public G4VUserDetectorConstruction
{
  public:
    DetectorConstruction();
    ~DetectorConstruction() override;

    G4VPhysicalVolume* Construct() override;

    G4LogicalVolume* GetScoringVolume() const { return fScoringVolume; }

    // Setters for the Messenger
    void SetWorldMaterial(G4String name) { fWorldMaterialName = name; }
    void SetChamberMaterial(G4String name) { fChamberMaterialName = name; }
    void SetChamberWidth(G4double width) { fChamberWidth = width; }
    void SetChamberLength(G4double length) { fChamberLength = length; }
    void SetTargetMaterial(G4String name) { fTargetMaterialName = name; }
    void SetTargetShape(G4String shape) { fTargetShape = shape; }
    void SetTargetWidth(G4double width) { fTargetWidth = width; }
    void SetTargetLength(G4double length) { fTargetLength = length; }
    void SetTargetPosition(G4ThreeVector pos) { fTargetPosition = pos; }
    
    // Triggers Geant4 to rebuild the geometry
    void UpdateGeometry();

  private:
    G4LogicalVolume* fScoringVolume = nullptr;

    // Default Environment Parameters
    G4String fWorldMaterialName;
    G4String fChamberMaterialName;
    G4double fChamberWidth;
    G4double fChamberLength;
    G4String fTargetMaterialName;
    G4String fTargetShape;
    G4double fTargetWidth;
    G4double fTargetLength;
    G4ThreeVector fTargetPosition;

    DetectorMessenger* fMessenger = nullptr;
};

}

#endif