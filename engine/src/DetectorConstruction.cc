/// \file DetectorConstruction.cc
/// \brief Implementation of the janus::DetectorConstruction class

#include "DetectorConstruction.hh"
#include "DetectorMessenger.hh"

#include "G4Box.hh"
#include "G4Tubs.hh"
#include "G4Sphere.hh"
#include "G4LogicalVolume.hh"
#include "G4NistManager.hh"
#include "G4PVPlacement.hh"
#include "G4SystemOfUnits.hh"
#include "G4RunManager.hh"
#include "G4GeometryManager.hh"
#include "G4PhysicalVolumeStore.hh"
#include "G4LogicalVolumeStore.hh"
#include "G4SolidStore.hh"

namespace janus
{

DetectorConstruction::DetectorConstruction()
{
    // Initialize Defaults
    fWorldMaterialName = "G4_Galactic";
    fChamberMaterialName = "G4_AIR";
    fTargetMaterialName = "G4_W";
    fTargetShape = "Box";
    fTargetWidth = 10.0 * cm;
    fTargetPosition = G4ThreeVector(0., 0., 0.);

    fMessenger = new DetectorMessenger(this);
}

DetectorConstruction::~DetectorConstruction()
{
    delete fMessenger;
}

G4VPhysicalVolume* DetectorConstruction::Construct()
{
    // Cleanup old geometry before rebuilding
    G4GeometryManager::GetInstance()->OpenGeometry();
    G4PhysicalVolumeStore::GetInstance()->Clean();
    G4LogicalVolumeStore::GetInstance()->Clean();
    G4SolidStore::GetInstance()->Clean();

    G4NistManager* nist = G4NistManager::Instance();

    G4bool checkOverlaps = true;

    // Materials
    G4Material* world_mat = nist->FindOrBuildMaterial(fWorldMaterialName);
    G4Material* chamber_mat = nist->FindOrBuildMaterial(fChamberMaterialName);
    G4Material* target_mat = nist->FindOrBuildMaterial(fTargetMaterialName);

    if (!world_mat || !chamber_mat || !target_mat) {
        G4Exception("DetectorConstruction::Construct()", "Janus002", FatalException, "A specified material was not found in NIST database.");
    }

    // World
    G4double chamber_sizeXY = 20 * cm;
    G4double chamber_sizeZ = 30 * cm;
    G4double world_sizeXY = 1.2 * chamber_sizeXY;
    G4double world_sizeZ = 1.2 * chamber_sizeZ;

    auto solidWorld = new G4Box("World", 0.5 * world_sizeXY, 0.5 * world_sizeXY, 0.5 * world_sizeZ);
    auto logicWorld = new G4LogicalVolume(solidWorld, world_mat, "World");
    auto physWorld = new G4PVPlacement(nullptr, G4ThreeVector(), logicWorld, "World", nullptr, false, 0, checkOverlaps);

    // Chamber
    auto solidChamber = new G4Box("Chamber", 0.5 * chamber_sizeXY, 0.5 * chamber_sizeXY, 0.5 * chamber_sizeZ);
    auto logicChamber = new G4LogicalVolume(solidChamber, chamber_mat, "Chamber");
    new G4PVPlacement(nullptr, G4ThreeVector(), logicChamber, "Chamber", logicWorld, false, 0, checkOverlaps);

    // Target Shape Generation
    G4VSolid* solidTar = nullptr;
    G4double halfWidth = fTargetWidth / 2.0;

    if (fTargetShape == "Box")
    {
        // A perfect cube
        solidTar = new G4Box("Target", halfWidth, halfWidth, halfWidth);
    }
    else if (fTargetShape == "Cylinder")
    {
        // Cylinder pointing down the Z axis
        solidTar = new G4Tubs("Target", 0., halfWidth, halfWidth, 0., 360.*deg);
    }
    else if (fTargetShape == "Sphere")
    {
        solidTar = new G4Sphere("Target", 0., halfWidth, 0., 360.*deg, 0., 180.*deg);
    }
    else
    {
        // Fallback to Box if typo
        solidTar = new G4Box("Target", halfWidth, halfWidth, halfWidth);
    }

    auto logicTar = new G4LogicalVolume(solidTar, target_mat, "Target");

    new G4PVPlacement(nullptr, fTargetPosition, logicTar, "Target", logicChamber, false, 0, checkOverlaps);

    fScoringVolume = logicTar;

    return physWorld;
}

void DetectorConstruction::UpdateGeometry()
{
    G4RunManager::GetRunManager()->ReinitializeGeometry();
}

}