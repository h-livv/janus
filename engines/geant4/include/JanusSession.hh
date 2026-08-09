/// \file JanusSession.hh
/// \brief Master controller for the Janus Geant4 Engine

#ifndef JanusSession_h
#define JanusSession_h 1

#include "globals.hh"

class G4RunManager;
class G4VisManager;
class G4UIExecutive;

namespace janus
{

class JanusSession
{
  public:
    JanusSession(int argc, char** argv);
    ~JanusSession();

    // Initializes the physics, geometry, and verbosity
    void Initialize();

    // Executes the macro or launches the interactive UI
    void Run();

  private:
    // Parses the CLI arguments passed by Python
    void ParseArguments();

    G4RunManager* fRunManager = nullptr;
    G4VisManager* fVisManager = nullptr;
    G4UIExecutive* fUI = nullptr;

    G4String fMacroName;
    G4bool fIsInteractive;
    G4String fPhysicsListName;

    int fArgc;
    char** fArgv;
};

}

#endif