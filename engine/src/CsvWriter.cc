#include "CsvWriter.hh"
#include "G4SystemOfUnits.hh"
#include "G4ios.hh"
#include <mutex>

namespace janus
{

// IMPORTANT: This static mutex is shared by ALL instances of CsvWriter
static std::mutex csvMutex;

CsvWriter::CsvWriter()
{
    // Open the single shared file
    fOutFile.open("../../temp/particle_tracks.csv", std::ios::app);

    if (!fOutFile.is_open())
    {
        G4cout << "ERROR: Could not open particle_tracks.csv" << G4endl;
        return;
    }

    // Only write the header if the file is empty/new
    // (This prevents header duplication if you restart a run)
    fOutFile.seekp(0, std::ios::end);
    if (fOutFile.tellp() == 0) {
        fOutFile << "eventID,trackID,parentID,particle,creatorProcess,time_ns,energy_MeV,x_cm,y_cm,z_cm\n";
    }
}

CsvWriter::~CsvWriter()
{
    if (fOutFile.is_open()) fOutFile.close();
}

void CsvWriter::Write(const ParticleRecord& record)
{
    if (!fOutFile.is_open()) return;

    // Use the static mutex to force serial writing
    std::lock_guard<std::mutex> lock(csvMutex);

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
}

}