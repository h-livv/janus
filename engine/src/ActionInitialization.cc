/// \file ActionInitialization.cc
#include "ActionInitialization.hh"
#include "PrimaryGeneratorAction.hh"
#include "RunAction.hh"
#include "EventAction.hh"
#include "SteppingAction.hh"
#include "TrackingAction.hh"

#include "G4GenericMessenger.hh"

namespace janus
{

// Initialize the static variable (1 = Antimatter, 0 = All)
G4int ActionInitialization::fFilterMode = 1;
G4bool ActionInitialization::fLightFilter = true;

ActionInitialization::ActionInitialization()
 : G4VUserActionInitialization()
{
    // The Master Thread safely registers the command here
    fMessenger = new G4GenericMessenger(this, "/janus/output/", "Output control");
    fMessenger->DeclareProperty("setFilter", fFilterMode, "0:All, 1:Antimatter");
    fMessenger->DeclareProperty("setLightFilter", fLightFilter, "True:Drop e+/pi-/mu+/nu, False:Keep all");
}

ActionInitialization::~ActionInitialization()
{
    delete fMessenger;
}

void ActionInitialization::BuildForMaster() const
{
    SetUserAction(new RunAction());
}

void ActionInitialization::Build() const
{
    SetUserAction(new PrimaryGeneratorAction());
    
    // 1. Create the RunAction and save its pointer
    auto runAction = new RunAction();
    SetUserAction(runAction);
    
    // 2. Pass the RunAction pointer into the EventAction
    auto eventAction = new EventAction(runAction);
    SetUserAction(eventAction);
    
    // 3. Pass the EventAction pointer into the SteppingAction
    SetUserAction(new SteppingAction(eventAction));

    // 4. Pass the TrackingAction
    SetUserAction(new TrackingAction());
}

}