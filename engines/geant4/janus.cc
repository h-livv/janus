/// \file janus.cc
/// \brief Main program

#include "JanusSession.hh"
#include <exception>
#include <iostream>

using namespace janus;

int main(int argc, char** argv)
{
    try 
    {
        // 1. Instantiate the engine session
        JanusSession session(argc, argv);

        // 2. Initialize Geant4 internals (Physics, Geometry, Actions)
        session.Initialize();

        // 3. Execute batch macro or open interactive UI
        session.Run();
    }
    catch (const std::exception& e) 
    {
        std::cerr << "Janus Engine Fatal Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}