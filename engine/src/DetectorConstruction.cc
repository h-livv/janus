/// \file DetectorConstruction.cc
/// \brief Implementation of the janus::DetectorConstruction class

#include "DetectorConstruction.hh"

#include "G4Box.hh"
#include "G4Cons.hh"
#include "G4LogicalVolume.hh"
#include "G4NistManager.hh"
#include "G4PVPlacement.hh"
#include "G4SystemOfUnits.hh"
#include "G4Box.hh"

namespace janus
{

G4VPhysicalVolume* DetectorConstruction::Construct()
{
  // Get nist material manager
  G4NistManager* nist = G4NistManager::Instance();

  // Chamber parameters
  //
  G4double chamber_sizeXY = 20 * cm, chamber_sizeZ = 30 * cm;
  G4Material* chamber_mat = nist->FindOrBuildMaterial("G4_AIR");

  // Option to switch on/off checking of volumes overlaps
  //
  G4bool checkOverlaps = true;

  //
  // World
  //
  G4double world_sizeXY = 1.2 * chamber_sizeXY;
  G4double world_sizeZ = 1.2 * chamber_sizeZ;
  G4Material* world_mat = nist->FindOrBuildMaterial("G4_AIR");

  auto solidWorld =
    new G4Box("World",  // its name
              0.5 * world_sizeXY, 0.5 * world_sizeXY, 0.5 * world_sizeZ);  // its size

  auto logicWorld = new G4LogicalVolume(solidWorld,  // its solid
                                        world_mat,  // its material
                                        "World");  // its name

  auto physWorld = new G4PVPlacement(nullptr,  // no rotation
                                     G4ThreeVector(),  // at (0,0,0) (default)
                                     logicWorld,  // its logical volume
                                     "World",  // its name
                                     nullptr,  // its mother  volume
                                     false,  // no boolean operation
                                     0,  // copy number
                                     checkOverlaps);  // overlaps checking

  //
  // Chamber
  //
  auto solidChamber = new G4Box("Chamber",  // its name
                            0.5 * chamber_sizeXY, 0.5 * chamber_sizeXY, 0.5 * chamber_sizeZ);  // its size

  auto logicChamber = new G4LogicalVolume(solidChamber,  // its solid
                                      chamber_mat,  // its material
                                      "Chamber");  // its name

  new G4PVPlacement(nullptr,  // no rotation
                    G4ThreeVector(),  // at (0,0,0)
                    logicChamber,  // its logical volume
                    "Chamber",  // its name
                    logicWorld,  // its mother  volume
                    false,  // no boolean operation
                    0,  // copy number
                    checkOverlaps);  // overlaps checking

  //
  // Target
  //
  G4Material* tar_mat = nist->FindOrBuildMaterial("G4_W");
  G4ThreeVector pos = G4ThreeVector(0, -1 * cm, 7 * cm);

  // Cuboid target
  G4double tar_dx = 15 * cm;
  G4double tar_dy = 15 * cm;
  G4double tar_dz = 15 * cm;
  auto solidTar =
    new G4Box("Target",  // its name
              0.5 * tar_dx, 0.5 * tar_dy, 0.5 * tar_dz);  // its size

  auto logicTar = new G4LogicalVolume(solidTar,  // its solid
                                         tar_mat,  // its material
                                         "Target");  // its name

  new G4PVPlacement(nullptr,  // no rotation
                    pos,  // at position
                    logicTar,  // its logical volume
                    "Target",  // its name
                    logicChamber,  // its mother  volume
                    false,  // no boolean operation
                    0,  // copy number
                    checkOverlaps);  // overlaps checking

  // Set Shape as scoring volume
  //
  fScoringVolume = logicTar;

  //
  // always return the physical World
  //
  return physWorld;
}

}
