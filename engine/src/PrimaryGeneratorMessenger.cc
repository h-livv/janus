#include "PrimaryGeneratorMessenger.hh"
#include "PrimaryGeneratorAction.hh"

#include "G4UIcmdWithADoubleAndUnit.hh"
#include "G4UIcmdWith3VectorAndUnit.hh"
#include "G4UIcmdWith3Vector.hh"
#include "G4UIcmdWithAString.hh"
#include "G4UIdirectory.hh"

namespace janus
{

PrimaryGeneratorMessenger::PrimaryGeneratorMessenger(PrimaryGeneratorAction* generator)
    : fGenerator(generator)
{
    fJanusDir = new G4UIdirectory("/gun/");
    fJanusDir->SetGuidance("Janus controls");

    fBeamDir = new G4UIdirectory("/gun/beam/");
    fBeamDir->SetGuidance("Beam controls");

    // Profile Type
    fProfileCmd = new G4UIcmdWithAString("/gun/beam/profile", this);
    fProfileCmd->SetGuidance("Set beam profile type (Flat, Gaussian, Point)");
    fProfileCmd->SetCandidates("Flat Gaussian Point");

    // Radius
    fRadiusCmd = new G4UIcmdWithADoubleAndUnit("/gun/beam/radius", this);
    fRadiusCmd->SetGuidance("Set flat beam radius");
    fRadiusCmd->SetUnitCategory("Length");

    // Sigma
    fSigmaCmd = new G4UIcmdWithADoubleAndUnit("/gun/beam/sigma", this);
    fSigmaCmd->SetGuidance("Set gaussian beam sigma");
    fSigmaCmd->SetUnitCategory("Length");

    // Direction
    fDirectionCmd = new G4UIcmdWith3Vector("/gun/beam/direction", this);
    fDirectionCmd->SetGuidance("Set beam momentum direction");

    // Offset
    fOffsetCmd = new G4UIcmdWith3VectorAndUnit("/gun/beam/offset", this);
    fOffsetCmd->SetGuidance("Set beam origin offset");
    fOffsetCmd->SetUnitCategory("Length");

    // Energy Distribution Type
    fEnergyDistCmd = new G4UIcmdWithAString("/gun/beam/energyDist", this);
    fEnergyDistCmd->SetGuidance("Set energy distribution (Mono, Gaussian)");
    fEnergyDistCmd->SetCandidates("Mono Gaussian");

    // Energy Mean
    fEnergyMeanCmd = new G4UIcmdWithADoubleAndUnit("/gun/beam/energyMean", this);
    fEnergyMeanCmd->SetGuidance("Set mean energy");
    fEnergyMeanCmd->SetUnitCategory("Energy");

    // Energy Sigma
    fEnergySigmaCmd = new G4UIcmdWithADoubleAndUnit("/gun/beam/energySigma", this);
    fEnergySigmaCmd->SetGuidance("Set energy spread (sigma)");
    fEnergySigmaCmd->SetUnitCategory("Energy");
}

PrimaryGeneratorMessenger::~PrimaryGeneratorMessenger()
{
    delete fProfileCmd;
    delete fRadiusCmd;
    delete fSigmaCmd;
    delete fDirectionCmd;
    delete fOffsetCmd;
    delete fEnergyDistCmd;
    delete fEnergyMeanCmd;
    delete fEnergySigmaCmd;
    delete fBeamDir;
    delete fJanusDir;
}

void PrimaryGeneratorMessenger::SetNewValue(G4UIcommand* command, G4String newValue)
{
    if (command == fRadiusCmd) {
        fGenerator->SetBeamRadius(fRadiusCmd->GetNewDoubleValue(newValue));
    } else if (command == fSigmaCmd) {
        fGenerator->SetBeamSigma(fSigmaCmd->GetNewDoubleValue(newValue));
    } else if (command == fDirectionCmd) {
        fGenerator->SetBeamDirection(fDirectionCmd->GetNew3VectorValue(newValue));
    } else if (command == fOffsetCmd) {
        fGenerator->SetBeamOffset(fOffsetCmd->GetNew3VectorValue(newValue));
    } else if (command == fProfileCmd) {
        fGenerator->SetBeamProfile(newValue);
    } else if (command == fEnergyMeanCmd) {
        fGenerator->SetEnergyMean(fEnergyMeanCmd->GetNewDoubleValue(newValue));
    } else if (command == fEnergySigmaCmd) {
        fGenerator->SetEnergySigma(fEnergySigmaCmd->GetNewDoubleValue(newValue));
    } else if (command == fEnergyDistCmd) {
        fGenerator->SetEnergyDistribution(newValue);
    }
}

}