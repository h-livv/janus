#include "CsvWriter.hh"

#include "G4SystemOfUnits.hh"
#include "G4ios.hh"

namespace janus
{

CsvWriter::CsvWriter()
{
    fOutFile.open("../../temp/particle_tracks.csv");

    if (!fOutFile.is_open())
    {
        G4cout << "ERROR: Could not open particle_tracks.csv"
               << G4endl;

        return;
    }

    fOutFile
        << "eventID,"
        << "trackID,"
        << "parentID,"
        << "particle,"
        << "creatorProcess,"
        << "time_ns,"
        << "energy_MeV,"
        << "x_cm,"
        << "y_cm,"
        << "z_cm"
        << "\n";

    fOutFile.flush();
}

CsvWriter::~CsvWriter()
{
    if (fOutFile.is_open())
    {
        fOutFile.close();
    }
}

void CsvWriter::Write(const ParticleRecord& record)
{
    if (!fOutFile.is_open()) return;

    fOutFile
        << record.eventID << ","
        << record.trackID << ","
        << record.parentID << ","
        << record.particleName << ","
        << record.creatorProcess << ","
        << record.globalTime / ns << ","
        << record.kineticEnergy / MeV << ","
        << record.position.x() / cm << ","
        << record.position.y() / cm << ","
        << record.position.z() / cm
        << "\n";
    
    fOutFile.flush();
}

}