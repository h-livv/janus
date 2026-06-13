/// \file JanusSession.cc
/// \brief Implementation of the JanusSession class

#include "JanusSession.hh"

#include "ActionInitialization.hh"
#include "DetectorConstruction.hh"
#include "G4PhysListFactory.hh" 
#include "G4VModularPhysicsList.hh"

#include "G4EmParameters.hh"
#include "G4HadronicProcessStore.hh"
#include "G4RunManagerFactory.hh"
#include "G4SteppingVerbose.hh"
#include "G4UIExecutive.hh"
#include "G4UImanager.hh"
#include "G4VisExecutive.hh"
#include "Randomize.hh"
#include <ctime>

namespace janus
{

JanusSession::JanusSession(int argc, char** argv)
    : fArgc(argc), fArgv(argv)
{
    ParseArguments();
}

JanusSession::~JanusSession()
{
    // Geant4 handles deletion of user actions, physics list, and geometry internally.
    // We only need to clean up the managers we explicitly created.
    if (fVisManager) delete fVisManager;
    if (fRunManager) delete fRunManager;
    if (fUI) delete fUI;
}

void JanusSession::ParseArguments()
{
    fIsInteractive = false;
    fMacroName = "";
    fPhysicsListName = "FTFP_BERT";

    // Flexible argument parsing loop
    for (int i = 1; i < fArgc; ++i) {
        G4String arg = fArgv[i];
        
        if (arg == "--interactive") {
            fIsInteractive = true;
        } 
        else if (arg == "--physics" && i + 1 < fArgc) {
            fPhysicsListName = fArgv[++i]; // Grab the next argument
        } 
        else if (arg[0] != '-') {
            // If it doesn't start with a flag, assume it's the macro
            fMacroName = arg;
        }
    }
}

void JanusSession::Initialize()
{
    if (fIsInteractive) {
        fUI = new G4UIExecutive(fArgc, fArgv);
    }

    G4Random::setTheEngine(new CLHEP::MTwistEngine);
    G4Random::setTheSeed(time(nullptr));

    G4int precision = 4;
    G4SteppingVerbose::UseBestUnit(precision);

    fRunManager = G4RunManagerFactory::CreateRunManager(G4RunManagerType::Default);
    fRunManager->SetUserInitialization(new DetectorConstruction());

    // --- Dynamic Physics List Injection ---
    G4PhysListFactory physListFactory;
    G4VModularPhysicsList* physicsList = physListFactory.GetReferencePhysList(fPhysicsListName);

    // Fallback in case a typo is sent from Python
    if (!physicsList) {
        G4cerr << "[-] Error: Physics list " << fPhysicsListName << " not found. Falling back to FTFP_BERT." << G4endl;
        physicsList = physListFactory.GetReferencePhysList("FTFP_BERT");
    }

    physicsList->SetVerboseLevel(0);
    G4EmParameters::Instance()->SetVerbose(0);
    G4HadronicProcessStore::Instance()->SetVerbose(0);
    fRunManager->SetUserInitialization(physicsList);

    fRunManager->SetUserInitialization(new ActionInitialization());

    fVisManager = new G4VisExecutive(fArgc, fArgv);
    fVisManager->Initialize();
}

void JanusSession::Run()
{
    auto UImanager = G4UImanager::GetUIpointer();

    if (!fIsInteractive) {
        // --- BATCH MODE ---
        if (!fMacroName.empty()) {
            G4String command = "/control/execute ";
            UImanager->ApplyCommand(command + fMacroName);
        }
    } 
    else {
        // --- INTERACTIVE MODE ---
        if (!fMacroName.empty()) {
            // Execute the Python-generated macro to build the custom setup
            G4String command = "/control/execute ";
            UImanager->ApplyCommand(command + fMacroName);
        } 
        else {
            // Fallback for purely manual launches
            UImanager->ApplyCommand("/control/execute macros/init_vis.mac");
        }
        
        // Start the session to keep the window open
        if (fUI) {
            fUI->SessionStart();
        }
    }
}

}