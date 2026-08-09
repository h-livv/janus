/// \file ActionInitialization.hh
#ifndef ActionInitialization_h
#define ActionInitialization_h 1

#include "G4VUserActionInitialization.hh"
#include "globals.hh"

class G4GenericMessenger;

namespace janus
{

class ActionInitialization : public G4VUserActionInitialization
{
  public:
    ActionInitialization();
    ~ActionInitialization() override;

    void BuildForMaster() const override;
    void Build() const override;

    // Global filter flag accessible by all worker threads
    static G4int fFilterMode;
    static G4bool fLightFilter;

  private:
    G4GenericMessenger* fMessenger = nullptr;
};

}

#endif