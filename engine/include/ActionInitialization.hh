/// \file ActionInitialization.hh
/// \brief Definition of the janus::ActionInitialization class

#ifndef B1ActionInitialization_h
#define B1ActionInitialization_h 1

#include "G4VUserActionInitialization.hh"

namespace janus
{

/// Action initialization class.

class ActionInitialization : public G4VUserActionInitialization
{
  public:
    ActionInitialization() = default;
    ~ActionInitialization() override = default;

    void BuildForMaster() const override;
    void Build() const override;
};

}

#endif
